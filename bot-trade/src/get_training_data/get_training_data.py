import sys
import ccxt
from .get_training_data_functions import get_candles_data, prepare_data
from src.validators import assert_output_file_does_not_exist
import logging
from src.utils import define_logging

logger = logging.getLogger(__name__)

def download_year_data() -> None:
    binance = ccxt.binance({
        'enableRateLimit': True,
    })
    symbol:str = "BTC/USDT"
    timeframe:str = "1h"
    limit:int = 1000
    start_year:int = 2021
    file_name: str = f"binance_{symbol.replace('/', '')}_{timeframe}_{start_year}.csv"
    try:
        assert_output_file_does_not_exist(file_name)
        ohlcv_array = get_candles_data(binance, symbol, timeframe, start_year, limit)
        df_ohlcv = prepare_data(ohlcv_array)
        df_ohlcv.to_csv(file_name, index=True)
        logger.info(f"Escritura completada en el archivo: {file_name}")
    except FileExistsError:
        logger.info(f"El archivo '{file_name}' ya existe. (ABORTANDO)")
        sys.exit(0)
    except (ccxt.NetworkError, ccxt.ExchangeError):
        logger.critical("Error de red o del exchange al contactar con la API. (ABORTANDO)")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Error inesperado (ABORTANDO): {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    define_logging("training_data_log.txt")
    download_year_data()