"""Opt-in capture of already published probabilities from the fixed loopback reports endpoint."""

import http.client
import json
import logging
import time
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import exchange_calendars

LOG = logging.getLogger(__name__)
MARKETS = {"us": ("XNYS", "America/New_York"), "kr": ("XKRX", "Asia/Seoul")}
LIMIT_BYTES = 2 * 1024 * 1024


def read_reports(ticker):
    conn = http.client.HTTPConnection("127.0.0.1", 8001, timeout=1.5)
    try:
        path = "/reports?" + urlencode({"ticker": ticker, "limit": 3})
        conn.request("GET", path, headers={"Accept": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            raise OSError(f"Report endpoint returned HTTP {response.status}")
        body = response.read(LIMIT_BYTES + 1)
        if len(body) > LIMIT_BYTES:
            raise ValueError("Report response too large")
        payload = json.loads(body)
        if not isinstance(payload, list):
            raise TypeError("Expected public report list")
        return payload[:3]
    finally:
        conn.close()


def match(case, report, clock):
    if not isinstance(report, dict) or report.get("ticker") != case["ticker"]:
        return None
    source_id = report.get("id")
    if type(source_id) is not int or source_id < 1 or case["market"] not in MARKETS:
        return None
    strategy = report.get("pipeline_strategy")
    if isinstance(strategy, str):
        try:
            strategy = json.loads(strategy)
        except ValueError:
            return None
    forecast = strategy.get("forecast_5s") if isinstance(strategy, dict) else None
    if not isinstance(forecast, dict):
        return None
    prob, model = forecast.get("p_up"), forecast.get("judge_model")
    if (
        type(prob) not in (float, int)
        or not 0 <= prob <= 1
        or not isinstance(model, str)
        or not model.strip()
    ):
        return None
    session = str(case["data_session"])
    if forecast.get("market_data_date") != session:
        return None
    try:
        published = datetime.fromisoformat(report["created_at"])
    except (TypeError, ValueError, KeyError):
        return None
    if published.utcoffset() is None:
        return None
    cal_name, zone = MARKETS[case["market"]]
    cal = exchange_calendars.get_calendar(cal_name)
    local_day = published.astimezone(ZoneInfo(zone)).date()
    first_session = cal.date_to_session(local_day + timedelta(days=1), direction="next")
    entry = case["entry_open_at"]
    if isinstance(entry, str):
        entry = datetime.fromisoformat(entry)
    if not cal.session_close(date.fromisoformat(session)) <= published <= clock < entry:
        return None
    if cal.session_open(first_session) != entry:
        return None
    return {
        "source_report_id": source_id,
        "ticker": case["ticker"],
        "probability": prob,
        "model": model.strip(),
        "source_published_at": published,
        "data_session": session,
    }


class IncumbentCollector:
    def __init__(self, store, fetch=read_reports, clock=None):
        self.store = store
        self.fetch = fetch
        self.retry_after = 0.0
        self.clock = clock or (lambda: datetime.now(UTC))

    def capture(self, cases):
        if time.monotonic() < self.retry_after:
            return 0
        saved = 0
        for case in cases:
            try:
                reports = self.fetch(case["ticker"])
            except (OSError, TypeError, ValueError, http.client.HTTPException) as exc:
                self.retry_after = time.monotonic() + 60
                LOG.info("Public reference source unavailable: %s", type(exc).__name__)
                break
            valid = [
                candidate
                for r in reports
                if (candidate := match(case, r, self.clock()))
            ]
            if valid:
                # Keep the newest publication visible at capture, then freeze it permanently.
                latest = max(
                    valid,
                    key=lambda p: (p["source_published_at"], p["source_report_id"]),
                )
                saved += int(self.store.record_reference(case["id"], **latest))
        return saved
