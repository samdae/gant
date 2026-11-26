"""Freeze trade news at the price used for the simulated execution."""
import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars

from tradingagents.forecast_lab.engine import MARKETS, _validate_market
from tradingagents.forecast_lab.scheduled_sources import read_trade_news

logger = logging.getLogger(__name__)


def trade_news_for_close(ticker, market, trade_date, quote_metadata, now):
    try:
        day = date.fromisoformat(trade_date)
        if ticker.endswith("-USD"):
            if (market != "us" or quote_metadata.get("instrumentType") != "CRYPTOCURRENCY"
                    or quote_metadata.get("exchangeTimezoneName") != "UTC"
                    or quote_metadata.get("currency") != "USD" or quote_metadata.get("symbol") != ticker
                    or day > now.astimezone(UTC).date()):
                raise ValueError("Unverified UTC crypto bar")
            close = datetime.combine(day + timedelta(days=1), time.min, UTC)
        else:
            _validate_market(quote_metadata, ticker, market)
            calendar, zone, _, _ = MARKETS[market]
            if day > now.astimezone(ZoneInfo(zone)).date():
                raise ValueError("Future price session")
            close = exchange_calendars.get_calendar(calendar).session_close(day).to_pydatetime()
    except (KeyError, ValueError, TypeError, OverflowError):
        logger.warning("Archive input unavailable for %s: unverified price session", ticker)
        return {"version": 1, "ticker": ticker, "as_of": now.isoformat(), "status": "unavailable", "items": []}
    return read_trade_news(ticker, market, min(now, close))
