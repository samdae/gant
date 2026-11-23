"""Date checks for vendors that only expose the latest fundamental snapshot."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


def market_today(ticker: str) -> date:
    ticker = ticker.upper()
    if ticker.endswith((".KS", ".KQ")):
        zone = "Asia/Seoul"
    elif ticker.endswith("-USD"):
        zone = "UTC"
    else:
        zone = "America/New_York"
    return datetime.now(ZoneInfo(zone)).date()


def unavailable_snapshot(ticker: str, curr_date: str | None, subject: str = "fundamentals") -> str | None:
    if curr_date and date.fromisoformat(curr_date) != market_today(ticker):
        return (f"Point-in-time {subject} unavailable for {ticker} on {curr_date}. "
                "This vendor exposes current data without publication-time history.")
    return None
