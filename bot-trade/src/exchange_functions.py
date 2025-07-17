import ccxt
import pandas as pd
import logging
import os
from datetime import datetime, timezone
from functools import reduce
import numpy as np


logger = logging.getLogger(__name__)

def get_candles_data( exchange:ccxt.Exchange, symbol:str, timeframe:str, start_year:int, limit:int) -> list[list[float]]:
    logger.info(f"Iniciando descarga de velas para {symbol} en timeframe {timeframe} para el anio {start_year}.")
    
    since:int = int(datetime(start_year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end_timestamp:int = int(datetime(start_year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)    
    
    all_ohlcv = []

    try:
        while since < end_timestamp:
            logger.info(f"Obteniendo {limit} velas desde {datetime.fromtimestamp(since/1000, tz=timezone.utc)}")
            ohlcv_array = exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
            if not ohlcv_array:
                logger.info("No se recibieron mas datos de la API. Finalizando bucle.")
                break
            all_ohlcv.extend(ohlcv_array)
            # Actualizamos el 'since' para la siguiente iteración.
            # Será el timestamp de la última vela obtenida + 1 milisegundo.
            # Esto evita obtener la misma vela dos veces.
            since = ohlcv_array[-1][0] + 1

        logger.info(f"Descarga completada. Total de velas obtenidas: {len(all_ohlcv)}")
        # Filtramos para asegurarnos de que no tenemos datos del año siguiente
        # a veces la última petición puede traer velas del siguiente año.
        filtered_ohlcv = [candle for candle in all_ohlcv if candle[0] < end_timestamp]
        logger.info(f"Velas despues de filtrar por anio {start_year}: {len(filtered_ohlcv)}")
        
        return filtered_ohlcv

    except (ccxt.NetworkError, ccxt.ExchangeError) as ne:
        logger.error(f"Error al obtener ohlcv (ccxt): {ne}")
        raise

def prepare_data(ohlcv_array:list[list[float]]) -> pd.DataFrame:
    df_ohlcv = pd.DataFrame(ohlcv_array, columns=["TimeStamp", "Open", "High", "Low", "Close", "Volume"])
    df_ohlcv["TimeStamp"] = pd.to_datetime(df_ohlcv["TimeStamp"], unit="ms")
    df_ohlcv.set_index("TimeStamp", inplace=True)
    return df_ohlcv

def write_to_csv(df_ohlcv:pd.DataFrame, file_name:str) -> None:
    if os.path.exists(file_name):
        return
    df_ohlcv.to_csv(file_name, index=True)

# --- 1. FUNCIONES DE CÁLCULO DE INDICADORES ---

def calculate_indicators(df: pd.DataFrame, rsi_period=14, bb_period=20, bb_std_dev=2, atr_period=14) -> None:
    """Calcula todos los indicadores necesarios de forma vectorizada."""
    # RSI
    delta = df['Close'].diff(1)
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Usa ewm (EMA) que es el método estándar para RSI, no SMA.
    avg_gain = gain.ewm(com=rsi_period - 1, min_periods=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, min_periods=rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Bandas de Bollinger
    df['BB_Mid'] = df['Close'].rolling(window=bb_period).mean()
    df['BB_Std'] = df['Close'].rolling(window=bb_period).std()
    df['BB_High'] = df['BB_Mid'] + (df['BB_Std'] * bb_std_dev)
    df['BB_Low'] = df['BB_Mid'] - (df['BB_Std'] * bb_std_dev)

    # ATR
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1) # type: ignore
    df['ATR'] = tr.ewm(alpha=1/atr_period, adjust=False).mean()

def find_divergence_signals(df: pd.DataFrame, pivot_lookback_window, confirmation_wait_candles, min_distance_between_pivots):
    """
    Función optimizada para PRE-CALCULAR todas las potenciales señales de divergencia.
    Ahora devuelve el DataFrame modificado.
    """
    # Esta es una versión simplificada de tu función anterior. Su único objetivo
    # es marcar las velas donde una señal de divergencia es VÁLIDA para ser evaluada.
    is_rsi_lookback_min = df['RSI'] == df['RSI'].rolling(window=pivot_lookback_window).min()
    conditions_list = [df['RSI'] < df['RSI'].shift(-i) for i in range(1, confirmation_wait_candles + 1)]
    is_rsi_forward_confirmed = reduce(lambda a, b: a & b, conditions_list)
    df['rsi_pivot_low'] = is_rsi_lookback_min & is_rsi_forward_confirmed
    
    df['bullish_divergence_signal'] = False
    potential_pivot_indices = df.index[df['rsi_pivot_low']]

    if len(potential_pivot_indices) < 2:
        df.drop('rsi_pivot_low', axis=1, inplace=True)
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
                # En lugar de comprobar el volumen aquí, solo marcamos la señal potencial.
                # La gestión de riesgo se hará en el bucle de simulación.
                df.loc[signal_idx, 'bullish_divergence_signal'] = True
        
        last_pivot_idx = current_pivot_idx
        
    df.drop('rsi_pivot_low', axis=1, inplace=True)
    return df

# --- 2. BUCLE PRINCIPAL DE SIMULACIÓN ---

def run_simulation(
        df: pd.DataFrame,
        initial_capital,
        fee_rate,
        risk_per_trade_pct,
        rr_min_ratio,
        max_candles_open,
        confirmation_wait_candles,
        volume_search_window):
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
        current_date = df.index[i].date()

        # --- A. GESTIÓN DE LA OPERACIÓN ACTIVA ---
        if in_trade:
            # Comprobar Stop Loss
            if current_row['Low'] <= active_trade['sl_price']:
                exit_price = active_trade['sl_price']
                capital += active_trade['position_size'] * exit_price * (1 - fee_rate)
                trade_log.append({'entry': active_trade['entry_price'], 'exit': exit_price, 'reason': 'SL'})
                logger.warning(f"CIERRE por SL en {current_date}: Capital final ${capital:,.2f}")
                in_trade = False
                active_trade = {}
                continue

            # Comprobar Fase 2: Take Profit 2
            if active_trade.get('is_phase_2') and current_row['High'] >= active_trade['tp2_price']:
                exit_price = active_trade['tp2_price']
                capital += active_trade['position_size'] * exit_price * (1 - fee_rate)
                trade_log.append({'entry': active_trade['entry_price'], 'exit': exit_price, 'reason': 'TP2'})
                logger.info(f"CIERRE por TP2 en {current_date}: Capital final ${capital:,.2f}")
                in_trade = False
                active_trade = {}
                continue

            # Comprobar Fase 1: Take Profit 1
            if not active_trade.get('is_phase_2') and current_row['High'] >= active_trade['tp1_price']:
                # Vender 50% de la posición
                exit_price_tp1 = active_trade['tp1_price']
                half_position = active_trade['position_size'] / 2
                capital += half_position * exit_price_tp1 * (1 - fee_rate)
                
                # Actualizar la operación a Fase 2
                active_trade['position_size'] = half_position
                active_trade['is_phase_2'] = True
                sl_breakeven = (active_trade['entry_price'] * (1 + fee_rate)) / (1 - fee_rate)
                active_trade['sl_price'] = sl_breakeven
                active_trade['tp2_price'] = current_row['BB_High'] # Objetivo dinámico

                logger.info(f"ALCANZADO TP1 en {current_date}: SL movido a breakeven (${sl_breakeven:.2f})")

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
        if not in_trade and current_row['bullish_divergence_signal']:
            
            # #######################################################################
            # ### INICIO CORRECCIÓN: Filtro de Volumen Reincorporado              ###
            # #######################################################################
            
            # La señal en 'i' confirma un pivote que ocurrió 'confirmation_wait_candles' atrás.
            pivot_pos = i - confirmation_wait_candles
            if pivot_pos < 0: continue # Seguridad para el inicio del dataframe
            
            # 1. Ventana de confirmación: las velas entre el pivote y la señal.
            confirmation_window = df.iloc[pivot_pos + 1 : i + 1]
            green_candles = confirmation_window[confirmation_window['Close'] > confirmation_window['Open']]

            # 2. Guard Clause: Si no hay velas verdes, el filtro falla.
            if green_candles.empty:
                logger.warning(f"Senial en {current_date} RECHAZADA: Sin vela verde de confirmación.")
                continue

            # 3. Ventana de busqueda eficiente para las velas rojas ANTERIORES al pivote.
            start_pos = max(0, pivot_pos - volume_search_window)
            search_df = df.iloc[start_pos:pivot_pos]
            red_candles = search_df[search_df['Close'] < search_df['Open']]

            # 4. Guard Clause: Si no hay 5 velas rojas para el promedio, el filtro falla.
            if len(red_candles) < 5:
                logger.warning(f"Senial en {current_date} RECHAZADA: No se encontraron 5 velas rojas en la ventana de busqueda.")
                continue
            
            # 5. Calcular umbral y comprobar si se supera.
            avg_red_volume = red_candles.tail(5)['Volume'].mean()
            volume_threshold = 1.5 * avg_red_volume
            volume_spike_found = any(green_candles['Volume'] > volume_threshold)

            # 6. Guard Clause: Si no hay pico de volumen, el filtro falla.
            if not volume_spike_found:
                logger.warning(f"Senial en {current_date} RECHAZADA por filtro de volumen (Umbral: {volume_threshold:.2f}).")
                continue
            
            logger.info(f"Senial en {current_date} SUPERO filtro de volumen. Evaluando R/R...")
            # #######################################################################
            # ### FIN CORRECCIÓN: Filtro de Volumen Reincorporado                 ###
            # #######################################################################
            
            # Filtro de Calidad (Ratio Riesgo/Beneficio)
            precio_entrada = current_price
            precio_sl_teorico = current_row['Low'] - current_row['ATR']
            precio_tp1_teorico = current_row['BB_Mid']

            # Cálculos con comisiones
            costo_total_entrada = precio_entrada * (1 + fee_rate)
            ingreso_neto_sl = precio_sl_teorico * (1 - fee_rate)
            riesgo_real_unitario = costo_total_entrada - ingreso_neto_sl
            
            # Guard Clause: Evitar entrar si el riesgo no es calculable o SL > Entrada
            if riesgo_real_unitario <= 0:
                logger.warning(f"Senial en {current_date} RECHAZADA: Riesgo inválido (SL ${precio_sl_teorico:.2f} >= Entrada ${precio_entrada:.2f}).")
                continue

            ingreso_neto_tp1 = precio_tp1_teorico * (1 - fee_rate)
            recompensa_real_unitaria = ingreso_neto_tp1 - costo_total_entrada
            
            # Guard Clause: Evitar entrar si el TP1 es menor que la entrada
            if recompensa_real_unitaria <= 0:
                logger.warning(f"Senial en {current_date} RECHAZADA: Recompensa nula o negativa (TP1 ${precio_tp1_teorico:.2f} <= Entrada ${precio_entrada:.2f}).")
                continue
            
            ratio_rr_real = recompensa_real_unitaria / riesgo_real_unitario

            # Decisión Final de Entrada
            # IGNORANDO FILTRO R/R
            # if ratio_rr_real < rr_min_ratio:
            #     logger.warning(f"Senial en {current_date} RECHAZADA: Ratio R/R ({ratio_rr_real:.2f}) no cumple el minimo de {rr_min_ratio}.")
            #     continue
            # Calcular Tamaño de Posición
            riesgo_en_usd = capital * risk_per_trade_pct
            tamanio_posicion_btc = riesgo_en_usd / riesgo_real_unitario
            costo_operacion = tamanio_posicion_btc * precio_entrada * (1 + fee_rate)
            
            # Guard Clause: No arriesgar más capital del que se tiene
            if costo_operacion > capital:
                logger.warning(f"Senial en {current_date} ignorada: capital insuficiente.")
                continue
            # Ejecutar la operación
            capital -= costo_operacion
            in_trade = True
            active_trade = {
                'entry_index': i,
                'entry_price': precio_entrada,
                'position_size': tamanio_posicion_btc,
                'sl_price': precio_sl_teorico,
                'tp1_price': precio_tp1_teorico,
                'is_phase_2': False,
            }
            logger.info(f"NUEVA OPERACION en {current_date} a ${precio_entrada:,.2f} | "
                        f"SL: ${precio_sl_teorico:,.2f} | TP1: ${precio_tp1_teorico:,.2f} | "
                        f"RR: {ratio_rr_real:.2f}")

    # Si la simulación termina con una operación abierta, la cerramos al último precio
    if in_trade:
        exit_price = df.iloc[-1]['Close']
        capital += active_trade['position_size'] * exit_price * (1 - fee_rate)
        logger.warning(f"CIERRE FORZADO al final del backtest. Capital final: ${capital:,.2f}")

    return capital, trade_log
    