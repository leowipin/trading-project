import ccxt
import pandas as pd
from datetime import datetime, timezone
import os
import logging

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
            # Actualizamos el 'since' para la siguiente iteracion.
            # Será el timestamp de la última vela obtenida + 1 milisegundo.
            # Esto evita obtener la misma vela dos veces.
            since = ohlcv_array[-1][0] + 1

        logger.info(f"Descarga completada. Total de velas obtenidas: {len(all_ohlcv)}")
        # Filtramos para asegurarnos de que no tenemos datos del anio siguiente
        # a veces la última peticion puede traer velas del siguiente anio.
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

