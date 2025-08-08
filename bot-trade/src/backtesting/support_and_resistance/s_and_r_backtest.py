import logging
import pandas as pd
from src.backtesting.utils_backtesting import calculate_bollinger_bands, calculate_rsi
from src.utils import define_logging

logger = logging.getLogger(__name__)

def run_s_and_r_backtest():
    timeframe = "1h"
    year = 2021
    rsi_period = 14
    bb_period = 20
    bb_std_dev = 2

    logger.info("Leyendo el archivo de datos...")
    df = pd.read_csv(f"binance_BTCUSDT_{timeframe}_{year}.csv", index_col='TimeStamp', parse_dates=True)
    logger.info("Calculando indicadores...")
    calculate_rsi(df, period=rsi_period)
    calculate_bollinger_bands(df, period=bb_period, std_dev=bb_std_dev)
    
    output_filename = f"s_and_r_backtest_annotated_data_{timeframe}_{year}.csv"
    logger.info(f"Guardando datos anotados en '{output_filename}'...")
    df.to_csv(output_filename)
    df.dropna(subset=['RSI', 'BB_Mid'], inplace=True)
    logger.info("Datos preparados y guardados correctamente.")

    initial_capital = 10000.0
    fee_rate = 0.001          # 0.1%
    risk_per_trade_pct = 0.1  # 10%
    psychological_level = 5000.0
    tolerance_percentage = 0.015  # 1.5%
    max_open_position = 3

if __name__ == '__main__':
    define_logging("s_and_r_backtest_log.txt")
    run_s_and_r_backtest()