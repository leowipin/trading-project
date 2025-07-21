import logging
import pandas as pd
from .bullish_backtest_functions import calculate_indicators, find_divergence_signals, precalculate_entry_filters, run_simulation
from utils import define_logging

logger = logging.getLogger(__name__)


def run_backtesting() -> None:
    # --- Parámetros de la Estrategia ---
    initial_capital = 10000.0
    fee_rate = 0.001          # 0.1%
    risk_per_trade_pct = 0.01 # 1%
    rr_min_ratio = 1.5
    max_candles_open = 48     # 48 velas de 1h = 2 días

    # --- Parámetros de Indicadores, Señales y Filtros---
    pivot_lookback_window = 10
    confirmation_wait_candles = 3
    min_distance_between_pivots = 20
    volume_search_window = 100
    
    # --- Ejecución ---
    logger.info("Leyendo el archivo de datos...")
    df = pd.read_csv("binance_BTCUSDT_1h_2021.csv", index_col='TimeStamp', parse_dates=True)
    
    logger.info("Calculando indicadores...")
    calculate_indicators(df)
    
    logger.info("Buscando pivotes y seniales de divergencia...")
    df = find_divergence_signals(df, pivot_lookback_window, confirmation_wait_candles, min_distance_between_pivots)
    
    logger.info("Pre-calculando filtros de Volumen y R/R para cada señal...")
    df = precalculate_entry_filters(df, volume_search_window, fee_rate)

    output_filename = "backtest_annotated_data_2021.csv"
    logger.info(f"Guardando datos anotados en '{output_filename}'...")
    df.to_csv(output_filename)
    
    df.dropna(subset=['RSI', 'BB_Mid', 'ATR'], inplace=True)

    #df.dropna(inplace=True) # Limpiar NaNs después de todos los cálculos

    # Correr la simulación principal
    final_capital, trades = run_simulation(
        df, 
        initial_capital, 
        fee_rate, 
        risk_per_trade_pct, 
        rr_min_ratio, 
        max_candles_open,
        )
    
    # --- Reporte Final ---
    logger.info("-------------------------------------------")
    logger.info("          RESULTADOS DEL BACKTEST          ")
    logger.info("-------------------------------------------")
    logger.info(f"Capital Inicial:    ${initial_capital:,.2f}")
    logger.info(f"Capital Final:      ${final_capital:,.2f}")
    pnl = final_capital - initial_capital
    pnl_pct = (pnl / initial_capital) * 100
    logger.info(f"Ganancia/Perdida:   ${pnl:,.2f} ({pnl_pct:.2f}%)")
    logger.info(f"Total de operaciones cerradas: {len(trades)}")
    logger.info("-------------------------------------------")

if __name__ == '__main__':
    define_logging("bullish_backtest_log.txt")
    run_backtesting()