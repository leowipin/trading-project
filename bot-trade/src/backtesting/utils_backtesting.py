import pandas as pd

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> None:
    delta = df['Close'].diff(1)
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Usa ewm (EMA) que es el método estándar para RSI, no SMA.
    avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> None:
    df['BB_Mid'] = df['Close'].rolling(window=period).mean()
    df['BB_Upper'] = df['BB_Mid'] + (df['Close'].rolling(window=period).std() * std_dev)
    df['BB_Lower'] = df['BB_Mid'] - (df['Close'].rolling(window=period).std() * std_dev)

def calculate_atr(df: pd.DataFrame, period: int = 14) -> None:
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift(1)).abs()
    low_close = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(alpha=1/period, adjust=False).mean()

def calculate_multiplier(default_timeframe: str, actual_timeframe: str, alpha: float) -> float:
    multiplier: float = 0
    if actual_timeframe.endswith("m"):
        unit:str = default_timeframe[-1]
        if unit == "m":
            multiplier = int(default_timeframe[:-1])/int(actual_timeframe[:-1])
        elif unit == "h":
            multiplier = (int(default_timeframe[:-1])*60)/int(actual_timeframe[:-1])
        elif unit == "d":
            multiplier = (int(default_timeframe[:-1])*1440)/int(actual_timeframe[:-1])
        else:
            raise ValueError(f"Invalid default timeframe: {unit}")
    elif actual_timeframe.endswith("h"):
        unit:str = default_timeframe[-1]
        if unit == "m":
            multiplier = int(default_timeframe[:-1])/(int(actual_timeframe[:-1])*60)
        elif unit == "h":
            multiplier = int(default_timeframe[:-1])/int(actual_timeframe[:-1])
        elif unit == "d":
            multiplier = ((int(default_timeframe[:-1])*24)/int(actual_timeframe[:-1]))
        else:
            raise ValueError(f"Invalid default timeframe: {unit}")
    else:
        unit:str = default_timeframe[-1]
        if unit == "m":
            multiplier = int(default_timeframe[:-1])/(int(actual_timeframe[:-1])*1440)
        elif unit == "h":
            multiplier = int(default_timeframe[:-1])/(int(actual_timeframe[:-1])*24)
        elif unit == "d":
            multiplier = int(default_timeframe[:-1])/int(actual_timeframe[:-1])
        else:
            raise ValueError(f"Invalid default timeframe: {unit}")
    
    if multiplier <= 0:
        raise ValueError("Multiplier cannot be 0 or negative")
    
    return alpha * multiplier