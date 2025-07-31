import pandas as pd
import logging
from functools import reduce
import numpy as np
from src.backtesting.utils_backtesting import calculate_rsi, calculate_bollinger_bands, calculate_atr

logger = logging.getLogger(__name__)

# --- 1. FUNCIONES DE CÁLCULO DE INDICADORES ---

def calculate_indicators(df: pd.DataFrame, rsi_period=14, bb_period=20, bb_std_dev=2, atr_period=14) -> None:
    """Calcula todos los indicadores necesarios de forma vectorizada."""
    # RSI
    calculate_rsi(df, period=rsi_period)

    # Bandas de Bollinger
    calculate_bollinger_bands(df, period=bb_period, std_dev=bb_std_dev)

    # ATR
    calculate_atr(df, period=atr_period)

def find_divergence_signals(df: pd.DataFrame, pivot_lookback_window, confirmation_wait_candles, min_distance_between_pivots):
    """
    Funcion optimizada para PRE-CALCULAR todas las potenciales seniales de divergencia.
    Ahora devuelve el DataFrame modificado.
    """
    is_rsi_lookback_min = df['RSI'] == df['RSI'].rolling(window=pivot_lookback_window).min()
    conditions_list = [df['RSI'] < df['RSI'].shift(-i) for i in range(1, confirmation_wait_candles + 1)]
    is_rsi_forward_confirmed = reduce(lambda a, b: a & b, conditions_list)
    df['rsi_pivot_low'] = is_rsi_lookback_min & is_rsi_forward_confirmed
    
    df['bullish_divergence_signal'] = False
    potential_pivot_indices = df.index[df['rsi_pivot_low']]

    if len(potential_pivot_indices) < 2:
        return df

    last_pivot_idx = potential_pivot_indices[0]
    for i in range(1, len(potential_pivot_indices)):
        current_pivot_idx = potential_pivot_indices[i]
        
        distance = df.index.get_loc(current_pivot_idx) - df.index.get_loc(last_pivot_idx) # type: ignore
        if distance < min_distance_between_pivots:
            if df.loc[current_pivot_idx, 'RSI'] < df.loc[last_pivot_idx, 'RSI']: # type: ignore
                last_pivot_idx = current_pivot_idx
            continue

        price_makes_lower_low = df.loc[current_pivot_idx, 'Close'] < df.loc[last_pivot_idx, 'Close'] # type: ignore
        rsi_makes_higher_low = df.loc[current_pivot_idx, 'RSI'] > df.loc[last_pivot_idx, 'RSI'] # type: ignore
        
        if price_makes_lower_low and rsi_makes_higher_low:
            pivot_pos = df.index.get_loc(current_pivot_idx)
            signal_pos = pivot_pos + confirmation_wait_candles
            if signal_pos < len(df.index):
                signal_idx = df.index[signal_pos]
                # En lugar de comprobar el volumen aquí, solo marcamos la senial potencial.
                # La gestion de riesgo se hará en el bucle de simulacion.
                df.loc[signal_idx, 'bullish_divergence_signal'] = True
                df.loc[signal_idx, 'generating_pivot_idx'] = current_pivot_idx
        
        last_pivot_idx = current_pivot_idx
        
    return df

def precalculate_entry_filters(df: pd.DataFrame, volume_search_window: int, fee_rate: float, volume_threshold_multiplier: float = 1.5) -> pd.DataFrame:
    """
    PRE-CALCULA los filtros de entrada (Volumen, R/R) para cada señal de divergencia.
    """
    # --- Columna 3: volume_confirmation ---
    df['volume_confirmation'] = pd.NA
    
    # --- Columna 4: risk_reward_ratio ---
    df['risk_reward_ratio'] = np.nan

    # Iteramos solo por las velas que tienen una señal de divergencia
    signal_indices = df.index[df['bullish_divergence_signal']]
    
    for signal_idx in signal_indices:
        signal_row = df.loc[signal_idx]
        signal_pos = df.index.get_loc(signal_idx)
        
        # --- Lógica de Filtro de Volumen ---
        pivot_idx = signal_row['generating_pivot_idx']
        pivot_pos = df.index.get_loc(pivot_idx)
        
        confirmation_window = df.iloc[pivot_pos + 1 : signal_pos + 1] # type: ignore
        green_candles = confirmation_window[confirmation_window['Close'] > confirmation_window['Open']]

        volume_confirmed = False
        if not green_candles.empty:
            start_pos = max(0, pivot_pos - volume_search_window) # type: ignore
            search_df = df.iloc[start_pos:pivot_pos]
            red_candles = search_df[search_df['Close'] < search_df['Open']]
            
            if len(red_candles) >= 5:
                avg_red_volume = red_candles.tail(5)['Volume'].mean()
                volume_threshold = 1.5 * avg_red_volume
                if any(green_candles['Volume'] > volume_threshold):
                    volume_confirmed = True
        
        df.loc[signal_idx, 'volume_confirmation'] = volume_confirmed

        # --- Lógica de Ratio Riesgo/Beneficio ---
        precio_entrada = signal_row['Close']
        precio_sl_teorico = signal_row['Low'] - signal_row['ATR']
        precio_tp1_teorico = signal_row['BB_Mid']
        
        costo_total_entrada = precio_entrada * (1 + fee_rate)
        ingreso_neto_sl = precio_sl_teorico * (1 - fee_rate)
        riesgo_real_unitario = costo_total_entrada - ingreso_neto_sl
        
        if riesgo_real_unitario > 0:
            ingreso_neto_tp1 = precio_tp1_teorico * (1 - fee_rate)
            recompensa_real_unitaria = ingreso_neto_tp1 - costo_total_entrada
            
            if recompensa_real_unitaria > 0:
                ratio_rr_real = recompensa_real_unitaria / riesgo_real_unitario
                df.loc[signal_idx, 'risk_reward_ratio'] = ratio_rr_real

    # Limpiamos columnas auxiliares
    df.drop(columns=['generating_pivot_idx'], inplace=True, errors='ignore')
    return df

# --- 2. BUCLE PRINCIPAL DE SIMULACIoN ---

def run_simulation(
        df: pd.DataFrame,
        initial_capital,
        fee_rate,
        risk_per_trade_pct,
        rr_min_ratio,
        max_candles_open,):
    """
    Recorre el DataFrame vela a vela, gestionando operaciones y capital.
    """
    capital = initial_capital
    in_trade = False
    active_trade = {}
    trade_log = []

    logger.info(f"Iniciando simulacion con Capital: ${capital:,.2f}")

    # Iteramos por cada vela del DataFrame
    for i in range(len(df)):
        current_row = df.iloc[i]
        current_price = current_row['Close']
        current_date = df.index[i]

        # --- A. GESTIoN DE LA OPERACIoN ACTIVA ---
        if in_trade:
            # Comprobar Stop Loss (antes de TP1)
            if not active_trade.get('is_phase_2') and current_row['Low'] <= active_trade['sl_price']:
                exit_price = active_trade['sl_price']
                pnl = (active_trade['position_size'] * exit_price * (1 - fee_rate)) - active_trade['total_cost']
                capital += active_trade['position_size'] * exit_price * (1 - fee_rate)
                trade_log.append({'entry': active_trade['entry_price'], 'exit': exit_price, 'reason': 'SL'})
                logger.warning(f"CIERRE por SL en {current_date}\n"
                               f"    - SL: ${exit_price:,.2f}.\n"
                               f"    - P&L: ${pnl:,.2f}.\n"
                               f"    - Capital final: ${capital:,.2f}")
                in_trade = False
                active_trade = {}
                continue

            # Comprobar Stop Loss (después de TP1 - Breakeven)
            if active_trade.get('is_phase_2') and current_row['Low'] <= active_trade['sl_price']:
                exit_price = active_trade['sl_price']
                # ### MODIFICADO ### Cálculo de P&L de la segunda mitad
                cash_in_part2 = active_trade['position_size'] * exit_price * (1 - fee_rate)
                pnl_part2 = cash_in_part2 - active_trade['cost_part2']
                capital += cash_in_part2
                trade_log.append({'entry': active_trade['entry_price'], 'exit': exit_price, 'reason': 'SL@BE'})
                logger.warning(f"CIERRE por SL en Breakeven en {current_date}\n"
                               f"    - Breakeven SL: ${exit_price:,.2f}.\n"
                               f"    - P&L Parte 2: ${pnl_part2:,.2f}.\n"
                               f"    - Capital final: ${capital:,.2f}")
                in_trade = False
                active_trade = {}
                continue

            # Comprobar Fase 2: Take Profit 2
            if active_trade.get('is_phase_2') and current_row['High'] >= active_trade['tp2_price']:
                exit_price = active_trade['tp2_price']
                # Cálculo de P&L de la segunda mitad
                cash_in_part2 = active_trade['position_size'] * exit_price * (1 - fee_rate)
                pnl_part2 = cash_in_part2 - active_trade['cost_part2']
                capital += cash_in_part2
                # Calcular P&L y ROI total
                pnl_total = (active_trade['pnl_part1'] + pnl_part2) # Necesitamos guardar pnl_part1
                costo_total = active_trade['total_cost']
                roi_pct = (pnl_total / costo_total) * 100
                trade_log.append({'entry': active_trade['entry_price'], 'exit': exit_price, 'reason': 'TP2'})
                # Logger
                logger.info(f"ALCANZADO TP2 y CIERRE en {current_date} a ${exit_price:,.2f}.\n"
                    f"    - P&L Parte 2: ${pnl_part2:,.2f}\n"
                    f"    - P&L Total Op.: ${pnl_total:,.2f} ({roi_pct:.2f}% ROI)\n"
                    f"    - Capital final: ${capital:,.2f}")
                in_trade = False
                active_trade = {}
                continue # Importante para no seguir procesando en esta vela

            # Comprobar Fase 1: Take Profit 1
            if not active_trade.get('is_phase_2') and current_row['High'] >= active_trade['tp1_price']:
                exit_price_tp1 = active_trade['tp1_price']
                half_position = active_trade['position_size'] / 2
                
                # ### MODIFICADO ### Cálculo de P&L de la primera mitad
                cash_in_part1 = half_position * exit_price_tp1 * (1 - fee_rate)
                pnl_part1 = cash_in_part1 - active_trade['cost_part1']
                capital += cash_in_part1
                
                # Actualizar la operacion a Fase 2
                active_trade['position_size'] = half_position
                active_trade['is_phase_2'] = True
                active_trade['pnl_part1'] = pnl_part1
                # Movemos SL a un breakeven real, considerando comisiones
                sl_breakeven = active_trade['cost_part2'] / (half_position * (1 - fee_rate))
                active_trade['sl_price'] = sl_breakeven
                active_trade['tp2_price'] = current_row['BB_Upper']  # TP2 es la banda superior de Bollinger

                # ### MODIFICADO ### Logger mejorado
                logger.info(f"ALCANZADO TP1 en {current_date} a ${exit_price_tp1:,.2f}. \n"
                            f"    - P&L Parte 1: ${pnl_part1:,.2f}.\n"
                            f"    - SL movido a breakeven ${sl_breakeven:.2f}\n"
                            f"    - tp2 fijado en ${active_trade['tp2_price']:.2f}.")

                continue

            # Comprobar Time Stop
            if i - active_trade['entry_index'] >= max_candles_open:
                exit_price = current_price
                capital += active_trade['position_size'] * exit_price * (1 - fee_rate)
                trade_log.append({'entry': active_trade['entry_price'], 'exit': exit_price, 'reason': 'Time Stop'})
                logger.warning(f"CIERRE por Time Stop en {current_date}: Capital final ${capital:,.2f}")
                in_trade = False
                active_trade = {}
                continue

        # --- B. busqueda DE NUEVAS ENTRADAS ---
        if not in_trade and current_row['bullish_divergence_signal'] and current_row['volume_confirmation'] == True:
            
            logger.info(f"Senial CONFIRMADA en {current_date}. Evaluando entrada...")

            # Filtro R/R (si lo quieres activar)
            # if pd.isna(current_row['risk_reward_ratio']) or current_row['risk_reward_ratio'] < rr_min_ratio:
            #     logger.warning(f"Senial en {current_date} RECHAZADA: Ratio R/R no válido o insuficiente.")
            #     continue
            
            # --- Lógica de cálculo de tamaño y entrada (casi igual a la anterior) ---
            precio_entrada = current_price
            precio_sl_teorico = current_row['Low'] - current_row['ATR']
            precio_tp1_teorico = current_row['BB_Mid']

            costo_total_entrada = precio_entrada * (1 + fee_rate)
            ingreso_neto_sl = precio_sl_teorico * (1 - fee_rate)
            riesgo_real_unitario = costo_total_entrada - ingreso_neto_sl

            if riesgo_real_unitario <= 0: continue
            
            riesgo_en_usd = capital * risk_per_trade_pct
            tamanio_posicion_btc = riesgo_en_usd / riesgo_real_unitario
            costo_bruto_posicion = tamanio_posicion_btc * precio_entrada
            costo_total_con_comision = costo_bruto_posicion * (1 + fee_rate)

            if costo_total_con_comision > capital:
                logger.warning(f"Senial en {current_date} ignorada: capital insuficiente.")
                continue

            # Ejecutar la operación
            capital -= costo_total_con_comision
            in_trade = True

            active_trade = {
                'entry_index': i,
                'entry_price': precio_entrada,
                'position_size': tamanio_posicion_btc, #btc
                'sl_price': precio_sl_teorico,
                'tp1_price': precio_tp1_teorico,
                'is_phase_2': False,
                'total_cost': costo_total_con_comision, #usdt
                'cost_part1': costo_total_con_comision / 2,
                'cost_part2': costo_total_con_comision / 2,
            }

            rr_from_df = current_row['risk_reward_ratio']

            logger.info(f"NUEVA OPERACION en {current_date}\n"
            f"    - Precio Entrada: ${precio_entrada:,.2f}\n"
            f"    - Capital en Riesgo (1%): ${riesgo_en_usd:,.2f}\n"
            f"    - Tamanio Posicion (Bruto): ${costo_bruto_posicion:,.2f}\n"
            f"    - Costo Total (c/comision): ${costo_total_con_comision:,.2f}\n"
            f"    - SL: ${precio_sl_teorico:,.2f} | TP1: ${precio_tp1_teorico:,.2f} | RR (TP1): {rr_from_df:.2f}")

    # Si la simulacion termina con una operacion abierta, la cerramos al último precio
    if in_trade:
        exit_price = df.iloc[-1]['Close']
        capital += active_trade['position_size'] * exit_price * (1 - fee_rate)
        logger.warning(f"CIERRE FORZADO al final del backtest. Capital final: ${capital:,.2f}")

    return capital, trade_log
    