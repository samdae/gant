import pandas as pd
import yfinance as yf
from stockstats import wrap
from typing import Annotated
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote
from .config import get_config


def _bounded_prices(data, start, end):
    dates = pd.to_datetime(data["Date"], errors="coerce").dt.tz_localize(None)
    return (data.assign(Date=dates).loc[dates.between(start, end)]
            .sort_values("Date").drop_duplicates("Date", keep="last"))


def load_price_window(symbol: str, end: pd.Timestamp, days: int, config: dict) -> pd.DataFrame:
    """Read a complete published cache file or fetch the requested historical window."""
    end = end.normalize()
    start = end - pd.Timedelta(days=days)
    directory = Path(config["data_cache_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    # Encode the symbol as a single filename component (some vendor symbols contain '/').
    file = directory / f"{quote(symbol, safe='')}-YFin-{days}d-{end:%Y%m%d}.csv"
    if file.is_file():
        try:
            cached = pd.read_csv(file, parse_dates=["Date"])
            if not cached.empty and {"Open", "High", "Low", "Close", "Volume"} <= set(cached):
                age = time.time() - file.stat().st_mtime
                if age < int(config.get("stock_cache_stale_days", 3)) * 86400:
                    bounded = _bounded_prices(cached, start, end)
                    if not bounded.empty:
                        return bounded
        except (ValueError, OSError, pd.errors.ParserError):
            pass

    data = yf.download(
        symbol, start=start.strftime("%Y-%m-%d"),
        end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        multi_level_index=False, progress=False, auto_adjust=True,
    )
    if data.empty:
        raise ValueError(f"No price history for {symbol} through {end.date()}")
    data = data.reset_index()
    data = _bounded_prices(data, start, end)
    if data.empty:
        raise ValueError(f"No price history for {symbol} through {end.date()}")
    with NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        data.to_csv(temporary, index=False)
        os.replace(temporary, file)
    finally:
        temporary.unlink(missing_ok=True)
    return data


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        config = get_config()

        curr_date_dt = pd.to_datetime(curr_date)
        data = load_price_window(symbol, curr_date_dt, int(config.get("stock_download_days", 330)), config)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        curr_date_str = curr_date_dt.strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
