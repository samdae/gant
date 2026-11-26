"""Collect the optional archive before the research observation or trade report is frozen."""

import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from .bounded_process import bounded_run

logger = logging.getLogger(__name__)
COLLECTOR_ROOT = "GANT_LAST30DAYS_COLLECTOR_ROOT"
COLLECTION_TIMEOUT = 110
MODEL_TURN_RESERVE = 300
READ_TIMEOUT = 12
NEWS_PER_SOURCE = 40  # The v3 archive's result limit for each source.
# Trade schedules also accept Yahoo's hyphenated dollar pairs (e.g. BTC-USD).
SYMBOL_PATTERNS = {"us": r"[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,5})?", "kr": r"[0-9]{6}\.(?:KS|KQ)"}


def _archive_command(ticker, market, module, arguments, timeout, label):
    root_setting = os.environ.get(COLLECTOR_ROOT)
    pattern = SYMBOL_PATTERNS.get(market)
    if not root_setting or pattern is None or not re.fullmatch(pattern, ticker):
        raise ValueError("Missing collector setting or unsupported instrument")
    root = Path(root_setting)
    if not root.is_absolute() or root.drive.startswith("\\\\"):
        raise ValueError("Local absolute collector root required")
    python = root / ".venv" / "Scripts" / "python.exe"
    command = [str(python), "-I", "-X", "utf8", "-m", module, "--ticker", ticker, *arguments]
    # The archive resolves its own settings; pass no model, database or console credentials.
    env = {k: os.environ[k] for k in (
        "SystemRoot", "WINDIR", "APPDATA", "LOCALAPPDATA", "USERPROFILE",
        "TEMP", "TMP", "ProgramFiles", "ProgramFiles(x86)", "ProgramData",
    ) if k in os.environ}
    env["PATH"] = str(Path(env["SystemRoot"]) / "System32")
    env["GANT_LAST30DAYS_SCHEDULED_HANDSHAKE"] = "1"
    return bounded_run(command, "start\n", timeout, label, env=env, cwd=root)


def collect_scheduled_issues(ticker, market, *, seconds_to_entry=None):
    if not os.environ.get(COLLECTOR_ROOT):
        return
    # Leave time for the original inference path when a delayed run approaches entry.
    if seconds_to_entry is not None and seconds_to_entry < COLLECTION_TIMEOUT + MODEL_TURN_RESERVE:
        logger.info("last30days deferred for %s near forecast entry", ticker)
        return
    try:
        _archive_command(ticker, market, "tradingagents.forecast_lab.scheduled_issues",
                         ["--market", market], COLLECTION_TIMEOUT, "last30days collector")
        logger.info("last30days collection checked for %s", ticker)
    except Exception as exc:
        # Search/archive availability cannot determine whether an otherwise valid case is issued.
        logger.warning("last30days collection unavailable for %s (%s)", ticker, type(exc).__name__)


def _utc(value):
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise ValueError("Trading news requires an explicit decision time")
    return parsed.astimezone(UTC)


def _trade_news_rows(packet, cutoff):
    sources = {"Google News RSS": 0, "last30days agent export": 0}
    urls = set()
    items = packet["items"]
    if not isinstance(items, list) or len(items) > NEWS_PER_SOURCE * len(sources):
        raise ValueError("Invalid news archive size")
    for index, row in enumerate(items, 1):
        if not isinstance(row, dict) or set(row) - {
            "ref", "source", "title", "publisher", "url", "published_at", "first_seen_at", "published_day",
        }:
            raise ValueError("Invalid news archive item")
        source = row["source"]
        url = urlsplit(row["url"])
        if (row["ref"] != f"N{index}" or source not in sources or sources[source] >= NEWS_PER_SOURCE
                or not isinstance(row["title"], str) or not 0 < len(row["title"].strip()) <= 500
                or not isinstance(row["publisher"], str) or not 0 < len(row["publisher"].strip()) <= 160
                or url.scheme != "https" or not url.hostname or url.username or url.password
                or row["url"] in urls or len(row["url"]) > 3000):
            raise ValueError("Invalid news archive item")
        published = _utc(row["published_at"])
        if not cutoff - timedelta(days=30) <= published <= _utc(row["first_seen_at"]) < cutoff:
            raise ValueError("News outside the decision window")
        if "published_day" in row:
            day = row["published_day"]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                raise ValueError("Invalid publication day")
            start = datetime.fromisoformat(day).replace(tzinfo=UTC)
            if (source != "last30days agent export" or published != start + timedelta(hours=36)
                    or start - timedelta(hours=14) < cutoff - timedelta(days=30)):
                raise ValueError("Publication day outside the decision window")
        sources[source] += 1
        urls.add(row["url"])
    return items


def read_trade_news(ticker, market, as_of):
    """Read the exact pre-inference archive; an unavailable reader never blocks trading."""
    cutoff = _utc(as_of)
    result = {"version": 1, "ticker": ticker, "as_of": cutoff.isoformat(), "status": "unavailable", "items": []}
    if not os.environ.get(COLLECTOR_ROOT):
        return result
    try:
        if cutoff > datetime.now(UTC):
            raise ValueError("Future decision time")
        raw = _archive_command(ticker, market, "tradingagents.forecast_lab.trade_news",
                               ["--as-of", result["as_of"]], READ_TIMEOUT, "trade news archive")
        if len(raw.encode("utf8")) > 1024 * 1024:
            raise ValueError("Oversized news archive")
        packet = json.loads(raw)
        if (type(packet["version"]) is not int or packet["version"] != 1
                or packet["ticker"] != ticker or _utc(packet["as_of"]) != cutoff
                or packet["status"] not in ("available", "partial", "empty", "unavailable")):
            raise ValueError("Unexpected news archive")
        items = _trade_news_rows(packet, cutoff)
        if ((packet["status"] == "available" and not items)
                or (packet["status"] in ("empty", "unavailable") and items)):
            raise ValueError("Inconsistent news archive status")
        return {**result, "status": packet["status"], "items": items}
    except Exception as exc:
        logger.warning("trade news read unavailable for %s (%s)", ticker, type(exc).__name__)
        return result
