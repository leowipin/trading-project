import sys
import ccxt
from exchange_functions import get_candles_data, prepare_data, calculate_rsi, find_divergences_and_set_signals
from validators import assert_output_file_does_not_exist
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def run_backtesting() -> None:
    pivot_lookback_window = 12
    confirmation_wait_candles = 3
    rsi_period = 14
    min_distance_between_pivots = 20
    volume_search_window = 20
    logger.info(f"Leyendo el archivo")
    df = pd.read_csv("binance_BTCUSDT_1h_2021.csv", index_col='TimeStamp', parse_dates=True)
    logger.info(f"calculando rsi")
    calculate_rsi(df, rsi_period)
    # limpiar los rsi con NaN
    df.dropna(inplace=True)
    logger.info(f"buscando senial de bullish divergence")
    find_divergences_and_set_signals(
        df,
        pivot_lookback_window,
        confirmation_wait_candles,
        min_distance_between_pivots,
        volume_search_window,
        )
    logger.info(f"busqueda finalizada")


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

def define_logging() -> None:
    logging.basicConfig(
        level = logging.INFO,
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("log.txt"),
            logging.StreamHandler()
        ] 
    )

if __name__ == "__main__":
    define_logging()
    run_backtesting()
    #download_year_data()