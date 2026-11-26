"""Bounded SELECTs for supplemental data missing from the V2 HTTP representation."""
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import BoundedSemaphore

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from .forecast_directory import published_tickers
from .issue_collector import case_issues, SOURCE, EXPORT
from .public_projection import news_evidence_projection
from .shared_view import empty_archive

DATABASES = {
    "v2_research": ("55434", "forecast_lab_research"),
    "v2_console": ("55434", "forecast_lab_console"),
    "v3_archive": ("55436", "forecast_lab_research"),
}
ROLE = "gant_v3_shared_reader"


class LocalSupplement:
    def __init__(self, config):
        self.passwords = json.loads(config.read_text(encoding="utf-8"))
        if set(self.passwords) != set(DATABASES) or not all(
            isinstance(x, str) and len(x) >= 24 for x in self.passwords.values()
        ):
            raise ValueError("Shared reader credentials are incomplete")
        self.slots = BoundedSemaphore(6)

    @contextmanager
    def connect(self, key):
        if not self.slots.acquire(timeout=1):
            raise HTTPException(503, "Shared data busy")
        port, db = DATABASES[key]
        try:
            with psycopg.connect(host="127.0.0.1", port=port, dbname=db,
                                 user=ROLE, password=self.passwords[key],
                                 connect_timeout=2, row_factory=dict_row,
                                 options="-c default_transaction_read_only=on -c statement_timeout=3000 -c timezone=UTC") as conn:
                yield conn
        except psycopg.Error:
            raise HTTPException(503, "Shared data temporarily unavailable") from None
        finally:
            self.slots.release()

    def forecast_tickers(self):
        with self.connect("v2_research") as conn:
            return published_tickers(conn)

    def probabilities(self, ids):
        with self.connect("v2_research") as conn:
            rows = conn.execute(
                """SELECT c.id,c.ticker,c.data_session,
                   COALESCE(jsonb_object_agg(a.method,a.probability)
                      FILTER (WHERE a.method IS NOT NULL),'{}') AS probabilities
                   FROM lab_cases c LEFT JOIN lab_arms a ON a.case_id=c.id
                    AND a.status='published' AND a.published_at<c.entry_at
                    AND a.published_at<=statement_timestamp()
                   WHERE c.id=ANY(%s) GROUP BY c.id,c.ticker,c.data_session""", (ids,)).fetchall()
        return {str(x["id"]): {**x, "data_session": x["data_session"].isoformat()} for x in rows}

    def evidence(self, kind, record_id):
        if kind == "case":
            key = "v2_research"
            query = """SELECT ticker,(snapshot->>'observed_at')::timestamptz AS cutoff
                       FROM lab_cases WHERE id=%s"""
        elif kind == "report":
            key = "v2_console"
            query = """SELECT sc.ticker,r.created_at AS cutoff,r.news_evidence FROM reports r
                JOIN schedule_jobs sj ON sj.id=r.schedule_job_id
                JOIN schedule_configs sc ON sc.id=sj.schedule_config_id WHERE r.id=%s"""
        else:
            raise HTTPException(404)
        with self.connect(key) as conn:
            identity = conn.execute(query, (record_id,)).fetchone()
        if not identity or not identity["cutoff"] or identity["cutoff"] > datetime.now(UTC):
            raise HTTPException(404)
        ticker, cutoff = identity["ticker"], identity["cutoff"]
        groups = empty_archive(cutoff.isoformat(), "failed")
        try:
            with self.connect("v3_archive") as conn:
                for name, source in (("issues", SOURCE), ("last30days", EXPORT)):
                    group = case_issues(conn, ticker, cutoff, source=source)
                    if group:
                        groups[name] = {**group, "provenance": "v3_archive_as_of"}
        except HTTPException:
            pass
        result = {"ticker": ticker, "as_of": cutoff.isoformat(), "id": record_id, **groups}
        if kind == "report":
            result["news_evidence"] = news_evidence_projection(identity["news_evidence"], ticker, result["as_of"])
        return result
