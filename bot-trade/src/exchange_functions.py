import ccxt
import pandas as pd
import logging
import os
from datetime import datetime, timezone
from functools import reduce
from typing import Any # Necesario para los type hints


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

def calculate_rsi(df:pd.DataFrame, rsi_period: int) -> None:
    delta = df['Close'].diff(1)
    gain = delta.clip(lower=0)
    
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=rsi_period - 1, min_periods=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, min_periods=rsi_period, adjust=False).mean()

    rs = avg_gain / avg_loss

    df['RSI'] = 100 - (100 / (1 + rs))
    
    df.to_csv("rsi.csv", index=True)

def find_divergences_and_set_signals(df: pd.DataFrame, 
                                     pivot_lookback_window: int, 
                                     confirmation_wait_candles: int, 
                                     min_distance_between_pivots: int,
                                     volume_search_window: int = 20) -> None:

    # --- Paso 1: Pre-cálculo vectorizado de los candidatos a pivote (muy rápido) ---
    is_rsi_lookback_min = df['RSI'] == df['RSI'].rolling(
        window=pivot_lookback_window, 
        min_periods=pivot_lookback_window).min()
    
    conditions_list = [df['RSI'] < df['RSI'].shift(-i) for i in range(1, confirmation_wait_candles + 1)]
    is_rsi_forward_confirmed = reduce(lambda a, b: a & b, conditions_list)
    
    df['rsi_pivot_low'] = is_rsi_lookback_min & is_rsi_forward_confirmed

    # --- Paso 2: Iteración única sobre los pivotes para encontrar divergencias ---
    
    df['bullish_divergence_signal'] = False
    
    potential_pivot_indices = df.index[df['rsi_pivot_low']]

    # Guard Clause: Salir si no hay suficientes pivotes para formar una divergencia.
    if len(potential_pivot_indices) < 2:
        df.drop('rsi_pivot_low', axis=1, inplace=True)
        logger.warning("No hay suficientes pivotes para formar una divergencia")
        return

    # Inicialización: El primer pivote se trata por separado para simplificar el bucle.
    last_pivot_idx = potential_pivot_indices[0]

    # El bucle ahora empieza desde el SEGUNDO pivote.
    for i in range(1, len(potential_pivot_indices)):
        current_pivot_idx = potential_pivot_indices[i]
        
        # Guard Clause: Verificar la distancia mínima.
        distance = df.index.get_loc(current_pivot_idx) - df.index.get_loc(last_pivot_idx) # type: ignore
        
        if distance < min_distance_between_pivots:
            # Si un pivote está muy cerca pero tiene un RSI más bajo, se convierte
            # en el nuevo punto de partida, ya que es un "mínimo más relevante".
            if df.loc[current_pivot_idx, 'RSI'] < df.loc[last_pivot_idx, 'RSI']: # type: ignore
                last_pivot_idx = current_pivot_idx
            continue

        # Usamos # type: ignore para decirle a Pylance que confíe en nosotros.
        # Sabemos que 'Close' y 'RSI' son numéricos y comparables.
        price_makes_lower_low = df.loc[current_pivot_idx, 'Close'] < df.loc[last_pivot_idx, 'Close'] # type: ignore
        rsi_makes_higher_low = df.loc[current_pivot_idx, 'RSI'] > df.loc[last_pivot_idx, 'RSI'] # type: ignore
        
        if not (price_makes_lower_low and rsi_makes_higher_low):
            # Si no hay divergencia, este pivote se convierte en el nuevo punto de partida y pasamos al siguiente.
            last_pivot_idx = current_pivot_idx
            continue
        
        # Calculamos la posición de la vela donde la señal sería procesable.
        pivot_pos = df.index.get_loc(current_pivot_idx)
        signal_pos = pivot_pos + confirmation_wait_candles # type: ignore
        
        # Guard Clause 3: La vela de señal no debe salirse del DataFrame.
        if signal_pos >= len(df.index):
            # No podemos confirmar esta señal, así que actualizamos el pivote y continuamos.
            last_pivot_idx = current_pivot_idx
            continue

        # #######################################################################
        # ### INICIO CAMBIO: Implementación del Filtro de Volumen (Filtro 3)   ###
        # #######################################################################
        
        # 1. Definir la ventana de confirmación (velas entre el pivote y la señal)
        confirmation_window_df = df.iloc[pivot_pos + 1 : signal_pos + 1] # type: ignore

        # 2. Identificar velas alcistas en la ventana de confirmación.
        green_candles_in_window = confirmation_window_df[confirmation_window_df['Close'] > confirmation_window_df['Open']]

        # 3. Guard Clause 4: Si no hay velas verdes, el filtro de volumen falla.
        if green_candles_in_window.empty:
            logger.info(f"Divergencia en {current_pivot_idx} RECHAZADA: Sin velas de confirmación verdes.")
            last_pivot_idx = current_pivot_idx
            continue

        # define la ventana en la que se va a buscar basa en volume_search_window por default es 20
        start_pos = max(0, pivot_pos - volume_search_window) # type: ignore
        search_df = df.iloc[start_pos:pivot_pos]
        
        # 4. Encontrar las velas rojas DENTRO de esta ventana optimizada.
        red_candles_in_search_window = search_df[search_df['Close'] < search_df['Open']]
        
        # 5. Guard Clause 5: Si no hay 5 velas rojas en la ventana de búsqueda, el filtro falla.
        if len(red_candles_in_search_window) < 5:
            logger.debug(f"Divergencia en {current_pivot_idx} RECHAZADA: No se encontraron 5 velas rojas en las últimas {volume_search_window} velas.")
            last_pivot_idx = current_pivot_idx
            continue
            
        # 6. Calcular el promedio usando las ÚLTIMAS 5 velas rojas encontradas en la ventana.
        avg_red_volume = red_candles_in_search_window.tail(5)['Volume'].mean()
        volume_threshold = 1.5 * avg_red_volume

        # 6. Comprobar si ALGUNA de las velas verdes supera el umbral. `any()` es más eficiente.
        volume_spike_found = any(green_candles_in_window['Volume'] > volume_threshold)

        # 7. Guard Clause 6: Si ninguna vela verde supera el umbral, el filtro falla.
        if not volume_spike_found:
            logger.info(f"Divergencia en {current_pivot_idx} RECHAZADA por filtro de volumen (Umbral: {volume_threshold:.2f}).")
            last_pivot_idx = current_pivot_idx
            continue

        # #######################################################################
        # ### FIN CAMBIO: Implementación del Filtro de Volumen (Filtro 3)      ###
        # #######################################################################

        # --- ¡CAMINO FELIZ! ---
        # Si la ejecución llega a este punto, todas las condiciones y filtros se han cumplido.
        # El código está limpio y sin anidamiento.
        signal_idx = df.index[signal_pos]
        df.loc[signal_idx, 'bullish_divergence_signal'] = True
        logger.info(f"==> SENIAL DE COMPRA generada en {signal_idx}. "
            f"Basada en la divergencia del pivote {current_pivot_idx}, confirmada con volumen.")
        
        # El pivote actual siempre se convierte en el nuevo punto de referencia.
        last_pivot_idx = current_pivot_idx

    df.to_csv("pivotes.csv", index=True)
    