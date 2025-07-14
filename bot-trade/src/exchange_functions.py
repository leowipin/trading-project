import ccxt
import pandas as pd
import logging
import os

logger = logging.getLogger(__name__)

def get_candles_data( exchange:ccxt.Exchange, symbol:str, timeframe:str, limit:int) -> list[list[float]]:
    try:
        ohlcv_array = exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        return ohlcv_array
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