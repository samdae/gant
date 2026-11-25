"""Collect last30days evidence for an eligible instrument in the v2 scheduler."""

import argparse
import json
import os
import re
import sys
from datetime import timedelta
from functools import partial
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row

from .console import checked_dsn
from .issue_collector import EXPORT, parse_export, record_observation

FRESH_FOR = timedelta(hours=6)
RETRY_AFTER = timedelta(minutes=15)


def collect_scheduled(connect, ticker, market, run_export):
    """A session owns the instrument until storage commits, including on concurrent retries."""
    from .scheduled_engine import has_source_failure

    ticker = ticker.strip().upper()
    if market not in ("us", "kr") or not re.fullmatch(
        r"[A-Z0-9][A-Z0-9.-]{0,15}", ticker
    ):
        raise ValueError("Invalid instrument")
    with connect() as conn:
        conn.autocommit = True
        conn.execute("SET statement_timeout = '5s'")
        # Archive identities are (source, ticker). A session lock releases on process
        # exit and lets us run the network request outside a database transaction.
        lock = (EXPORT + "/" + ticker,)
        leader = conn.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired", lock
        ).fetchone()["acquired"]
        if not leader:
            with conn.transaction():
                conn.execute("SET LOCAL statement_timeout = '95s'")
                conn.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", lock)
        recent = conn.execute(
            """SELECT id,status,item_count,collected_at FROM v3_issue_runs
               WHERE ticker=%s AND source=%s
               ORDER BY collected_at DESC,id DESC LIMIT 1""",
            (ticker, EXPORT),
        ).fetchone()
        now = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
        if recent:
            ttl = RETRY_AFTER if recent["status"] == "failed" else FRESH_FOR
            if now - ttl <= recent["collected_at"] <= now:
                return {**recent, "disposition": "reused"}
        if not leader:
            # The process we waited for exited without committing. Do not run a
            # second 90-second request in the scheduler's remaining time budget.
            return {"status": "deferred", "disposition": "incomplete_peer"}

        try:
            export = run_export(ticker, market)
            payload = json.dumps(export, ensure_ascii=False, allow_nan=False).encode()
            observed = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
            rows = parse_export(payload, observed, ticker)
            status, query = ("available" if rows else "empty"), export["query"]
            if has_source_failure(export):
                # Preserve verified items from responding sources, and retry the
                # incomplete collection on the failure schedule.
                status = "failed"
        except psycopg.Error:
            raise
        except Exception:  # A failed upstream/invalid export is a recorded attempt.
            observed = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
            status, query, rows = "failed", ticker, []
        with conn.transaction():
            run = record_observation(conn, ticker, EXPORT, query, observed, status, rows)
        return {**run, "disposition": "collected"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--market", choices=("us", "kr"), required=True)
    args = parser.parse_args()
    # The Windows caller attaches a kill-on-close job before releasing the child.
    if os.environ.get("GANT_LAST30DAYS_SCHEDULED_HANDSHAKE") == "1":
        if sys.stdin.readline() != "start\n":
            return 1
    from .scheduled_engine import run_export

    try:
        env = Path(os.environ["LOCALAPPDATA"]) / "TradingAgentsV3" / "lab.env"
        raw = dotenv_values(env, interpolate=False).get("FORECAST_LAB_DSN")
        checked_dsn(raw, "forecast_lab_research")
        connect = partial(
            psycopg.connect, raw, row_factory=dict_row, connect_timeout=3,
            options="-c timezone=UTC",
        )
        result = collect_scheduled(connect, args.ticker, args.market, run_export)
    except (OSError, ValueError, KeyError, psycopg.Error):
        result = {"status": "storage_failed"}
    print(json.dumps({"ticker": args.ticker, "source": EXPORT, **result}, default=str))
    return 0 if result["status"] in ("available", "empty") else 1


if __name__ == "__main__":
    raise SystemExit(main())
