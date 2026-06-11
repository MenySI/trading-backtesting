import os
import yfinance as yf
import backtrader as bt
import pandas as pd


def get_dataframe(ticker: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    cache_path = os.path.join("data", f"{ticker}_{start}_{end}_{interval}.csv".replace(":", "-"))
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
    else:
        df = yf.download(ticker, start=start, end=end, interval=interval,
                         auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No data returned for '{ticker}'. Check the ticker symbol.")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.to_csv(cache_path)
    return df


def get_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
    return bt.feeds.PandasData(dataname=df.copy())
