import pandas as pd
import logging

logger = logging.getLogger(__name__)

def run_simulation(df: pd.DataFrame,
                   initial_capital: float,
                   fee_rate: float,
                   risk_per_trade_pct: float,
                   psychological_level: float,
                   tolerance_percentage: float,
                   max_open_position: int) -> None:
    for index, row in df.iterrows():
        closed_price = row['Close']
        # Guard clauses
        if pd.isna(row['BB_Mid']) or pd.isna(row['RSI']):
            continue
        if closed_price > row['BB_Mid']:
            continue
        if closed_price > 100000: # Adjust tolerance for high prices
            tolerance_percentage = 0.01
        if (closed_price % psychological_level) > closed_price * tolerance_percentage:
            continue
        if max_open_position >= 3:
            # Close positions conditions
            logger.info("There are 3 or more open positions.")
            continue
        # Take the row and start a new position
        pass