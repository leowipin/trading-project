import sys
import ccxt
from exchange_functions import get_candles_data, prepare_data
from validators import assert_output_file_does_not_exist
import logging
import os

logger = logging.getLogger(__name__)

def run_bot() -> None:
    binance = ccxt.binance()
    symbol:str = "BTCUSDT"
    timeframe:str = "1h"
    limit:int = 168
    file_name:str = "exchange_ohlcv.csv"
    try:
        assert_output_file_does_not_exist(file_name)
        ohlcv_array = get_candles_data(binance, symbol, timeframe, limit)
        df_ohlcv = prepare_data(ohlcv_array)
        df_ohlcv.to_csv(file_name, index=True)
        logger.info("escritura completada")
    except FileExistsError:
        logger.info(f"Archivo ya existe (ABORTANDO)")
        sys.exit(0)
    except (ccxt.NetworkError, ccxt.ExchangeError):
        logger.critical(f"Error ccxt (ABORTANDO)")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Error inesperado (ABORTANDO): {e}", exc_info=True)
        sys.exit(1)

def define_logging() -> None:
    logging.basicConfig(
        level = logging.INFO,
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("log.txt"),
            logging.StreamHandler()
        ] 
    )

def file_exist(file_name) -> None:
    if os.path.exists(file_name):
        logger.info("Archivo ya existe (ABORTANDO)")    
        sys.exit(1)

if __name__ == "__main__":
    define_logging()
    run_bot()