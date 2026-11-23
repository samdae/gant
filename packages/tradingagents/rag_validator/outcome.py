"""Measure a cited memory's paired paper decisions over the next five exchange sessions."""

import logging
from datetime import date, datetime, timedelta
from math import isclose, isfinite
from sys import float_info
from zoneinfo import ZoneInfo

import exchange_calendars
from psycopg.types.json import Jsonb
import yfinance as yf

logger = logging.getLogger(__name__)

MARKETS = {
    "us": ("XNYS", "America/New_York"),
    "kr": ("XKRX", "Asia/Seoul"),
}


def _nonnegative(value):
    return type(value) in (int, float) and 0 <= value <= float_info.max


def _decision_pair(payload):
    if not isinstance(payload, dict):
        return None
    pair = payload.get("decision_pair_v1")
    if not isinstance(pair, dict):
        return None
    reflection_id = pair.get("reflection_id")
    if type(reflection_id) is not int or not 0 < reflection_id <= 2**63 - 1:
        return None
    memories = payload.get("memories")
    applied = payload.get("applied_reflection_ids")
    if not isinstance(memories, list) or len(memories) != 1 or not isinstance(memories[0], dict):
        return None
    doc = memories[0]
    lesson = doc.get("matched_situation")
    if (type(doc.get("reflection_id")) is not int or doc["reflection_id"] != reflection_id
            or not isinstance(lesson, str) or not lesson.strip()):
        return None
    if (not isinstance(applied, list) or len(applied) != 1
            or type(applied[0]) is not int or applied[0] != reflection_id):
        return None
    if not all(_nonnegative(pair.get(field)) for field in ("cash", "holdings")):
        return None
    for key in ("before", "after"):
        decision = pair.get(key)
        if not isinstance(decision, dict) or decision.get("action") not in ("BUY", "SELL", "HOLD"):
            return None
        if not _nonnegative(decision.get("shares")):
            return None
    return pair


def _signed_shares(decision, cash, holdings, price):
    if decision["action"] == "BUY":
        return min(decision["shares"], cash / price)
    if decision["action"] == "SELL":
        return -min(decision["shares"], holdings)
    return 0.0


def _load_bars(ticker, sessions, expected_timezone):
    instrument = yf.Ticker(ticker)
    data = instrument.history(
        start=sessions[0].isoformat(), end=(sessions[-1] + timedelta(days=1)).isoformat(),
        interval="1d", auto_adjust=False, actions=True, raise_errors=True, timeout=15,
    )
    # yfinance's public history_metadata requests extra intraday bars to populate
    # tradingPeriods. Read the metadata of this exact daily chart response instead.
    history = getattr(instrument, "_price_history", None)
    meta = getattr(history, "_history_metadata", None) or {}
    if (meta.get("instrumentType") not in ("EQUITY", "ETF")
            or meta.get("exchangeTimezoneName") != expected_timezone):
        return {}, {}
    venue = {key: meta.get(key) for key in ("instrumentType", "exchangeTimezoneName", "exchangeName")}
    if data.empty or not data.index.is_unique or not {"Open", "Close", "Stock Splits"} <= set(data.columns):
        return {}, venue
    return {stamp.date(): (row["Open"], row["Close"], row["Stock Splits"])
            for stamp, row in data.iterrows()}, venue


def _evidence(row, pair, as_of, bars_cache):
    market = MARKETS.get(str(row["market"]).strip().lower())
    if not market or not row["ticker"] or str(row["ticker"]).strip().upper().endswith("-USD"):
        return None
    calendar, tz = market
    publication = row["created_at"].astimezone(ZoneInfo(tz)).date()
    cutoff = as_of.astimezone(ZoneInfo(tz)).date() if isinstance(as_of, datetime) else as_of
    if (cutoff - publication).days < 6:
        return None
    start = publication + timedelta(days=1)
    end = min(cutoff - timedelta(days=1), start + timedelta(days=28))
    dates = exchange_calendars.get_calendar(calendar).sessions_in_range(start, end)
    if len(dates) < 5:
        return None
    sessions = tuple(s.date() for s in dates[:5])
    cache_key = (row["ticker"], sessions, tz)
    if cache_key not in bars_cache:
        bars_cache[cache_key] = _load_bars(row["ticker"], sessions, tz)
    bars, venue = bars_cache[cache_key]
    for session in sessions:
        if session not in bars:
            return None
        op, close, split = bars[session]
        if not (isfinite(op) and isfinite(close) and op > 0 and close > 0 and split == 0):
            return None
    entry, exit_price = float(bars[sessions[0]][0]), float(bars[sessions[-1]][1])
    args = (pair["cash"], pair["holdings"], entry)
    before = _signed_shares(pair["before"], *args)
    after = _signed_shares(pair["after"], *args)
    difference = (after - before) * (exit_price - entry)
    if not isfinite(difference):
        return None
    if isclose(before, after, rel_tol=0, abs_tol=1e-12) or isclose(difference, 0, rel_tol=0, abs_tol=1e-12):
        delta = 0
    else:
        delta = 1 if difference > 0 else -1
    return delta, {
        "method": "next_open_fifth_close_gross_v1", "ticker": row["ticker"], "market": row["market"],
        "calendar": calendar, "venue": venue, "published_at": row["created_at"].isoformat(), "pair": pair,
        "source": "yfinance_daily_auto_adjust_false", "sessions": [
            {"date": day.isoformat(), "open": float(bars[day][0]), "close": float(bars[day][1])}
            for day in sessions
        ],
        "before_signed_shares": before, "after_signed_shares": after, "gross_difference": difference,
    }


def evaluate_pending(db, as_of):
    """Score mature windows once. A date is an exclusive local-market cutoff."""
    if not isinstance(as_of, date) or (isinstance(as_of, datetime) and as_of.utcoffset() is None):
        raise ValueError("as_of must be a date or timezone-aware datetime")
    last_id = scored = 0
    cache = {}
    while True:
        conn = db.get_connection()
        rows = conn.execute(
            """
            SELECT r.id, r.created_at, r.rag_docs, c.ticker, c.market
            FROM reports r JOIN schedule_jobs j ON j.id = r.schedule_job_id
            JOIN schedule_configs c ON c.id = j.schedule_config_id
            WHERE r.id > %s AND r.rag_used AND r.rag_docs ? 'decision_pair_v1'
              AND NOT EXISTS (SELECT 1 FROM rag_outcome_evaluations o WHERE o.report_id = r.id)
            ORDER BY r.id LIMIT 64
            """, (last_id,)
        ).fetchall()
        conn.commit()
        if not rows:
            return scored
        last_id = rows[-1]["id"]
        for row in rows:
            pair = _decision_pair(row["rag_docs"])
            if not pair:
                continue
            try:
                result = _evidence(row, pair, as_of, cache)
            except Exception as exc:
                logger.warning("Outcome window unavailable for report %s: %s", row["id"], exc)
                continue
            if result is None:
                continue
            delta, evidence = result
            evidence["supplied_memory"] = row["rag_docs"]["memories"][0]
            evidence["applied_reflection_ids"] = row["rag_docs"]["applied_reflection_ids"]
            try:
                saved = conn.execute(
                    """
                    INSERT INTO rag_outcome_evaluations(report_id,reflection_id,score_delta,evidence)
                    SELECT r.id, m.id, %s, %s FROM reports r JOIN reflections m ON m.id=%s
                    WHERE r.id=%s AND r.rag_used AND r.rag_docs=%s
                    ON CONFLICT (report_id) DO NOTHING RETURNING report_id
                    """, (delta, Jsonb(evidence), pair["reflection_id"], row["id"], Jsonb(row["rag_docs"]))
                ).fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            scored += int(saved is not None)
