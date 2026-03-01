"""Portfolio decision repository."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


class PortfolioDecisionRepository:
    """Repository for `portfolio_decisions` table."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _normalize_date(value: Any) -> str:
        if isinstance(value, date):
            return value.isoformat()
        text = str(value or "").strip()
        if not text:
            return datetime.now().date().isoformat()
        return text[:10]

    @staticmethod
    def _to_json(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def create(
        self,
        portfolio_config_id: int,
        decision_date: Any,
        briefing_summary: Optional[Dict[str, Any]],
        allocation_plan: List[Dict[str, Any]],
        rationale: Optional[str],
        total_fund_snapshot: float,
        available_cash_snapshot: float,
        exchange_rate_snapshot: Optional[float],
        status: str = "pending",
        error_message: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        created_at = datetime.now().isoformat()
        normalized_date = self._normalize_date(decision_date)
        status = (
            status
            if status in {"pending", "executing", "completed", "partial_failed", "failed"}
            else "pending"
        )
        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO portfolio_decisions (
                portfolio_config_id, decision_date, briefing_summary, allocation_plan,
                rationale, total_fund_snapshot, available_cash_snapshot,
                exchange_rate_snapshot, status, error_message, created_at
            ) VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (portfolio_config_id, decision_date)
            DO UPDATE SET
                briefing_summary = excluded.briefing_summary,
                allocation_plan = excluded.allocation_plan,
                rationale = excluded.rationale,
                total_fund_snapshot = excluded.total_fund_snapshot,
                available_cash_snapshot = excluded.available_cash_snapshot,
                exchange_rate_snapshot = excluded.exchange_rate_snapshot,
                status = excluded.status,
                error_message = excluded.error_message
            RETURNING id
            """,
            (
                portfolio_config_id,
                normalized_date,
                self._to_json(briefing_summary or {}),
                self._to_json(allocation_plan or []),
                rationale,
                float(total_fund_snapshot),
                float(available_cash_snapshot),
                float(exchange_rate_snapshot) if exchange_rate_snapshot is not None else None,
                status,
                error_message,
                created_at,
            ),
        )
        if commit:
            connection.commit()
        row = cursor.fetchone()
        decision_id = int(row["id"]) if row else 0
        logger.info(
            "Upserted portfolio_decision %s for config=%s date=%s status=%s",
            decision_id,
            portfolio_config_id,
            normalized_date,
            status,
        )
        return decision_id

    def update_status(
        self,
        decision_id: int,
        status: str,
        error_message: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> None:
        status = (
            status
            if status in {"pending", "executing", "completed", "partial_failed", "failed"}
            else "failed"
        )
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE portfolio_decisions
            SET status = %s, error_message = %s
            WHERE id = %s
            """,
            (status, error_message, decision_id),
        )
        if commit:
            connection.commit()

    def get_by_id(self, decision_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.get_connection().execute(
            """
            SELECT id, portfolio_config_id, decision_date, briefing_summary, allocation_plan,
                   rationale, total_fund_snapshot, available_cash_snapshot,
                   exchange_rate_snapshot, status, error_message, created_at
            FROM portfolio_decisions
            WHERE id = %s
            LIMIT 1
            """,
            (decision_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_by_date(self, config_id: int, decision_date: Any) -> Optional[Dict[str, Any]]:
        row = self.db.get_connection().execute(
            """
            SELECT id, portfolio_config_id, decision_date, briefing_summary, allocation_plan,
                   rationale, total_fund_snapshot, available_cash_snapshot,
                   exchange_rate_snapshot, status, error_message, created_at
            FROM portfolio_decisions
            WHERE portfolio_config_id = %s AND decision_date = %s
            LIMIT 1
            """,
            (config_id, self._normalize_date(decision_date)),
        ).fetchone()
        return dict(row) if row else None

    def list_recent(
        self,
        config_id: int,
        cursor: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT id, portfolio_config_id, decision_date, briefing_summary, allocation_plan,
                   rationale, total_fund_snapshot, available_cash_snapshot,
                   exchange_rate_snapshot, status, error_message, created_at
            FROM portfolio_decisions
            WHERE portfolio_config_id = %s
        """
        params: List[Any] = [config_id]
        if cursor:
            query += " AND id < %s"
            params.append(cursor)
        query += " ORDER BY id DESC LIMIT %s"
        params.append(limit)
        rows = self.db.get_connection().execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_by_week(
        self,
        config_id: int,
        week_start_date: Any,
        week_end_date: Any,
    ) -> List[Dict[str, Any]]:
        rows = self.db.get_connection().execute(
            """
            SELECT id, portfolio_config_id, decision_date, briefing_summary, allocation_plan,
                   rationale, total_fund_snapshot, available_cash_snapshot,
                   exchange_rate_snapshot, status, error_message, created_at
            FROM portfolio_decisions
            WHERE portfolio_config_id = %s
              AND decision_date BETWEEN %s AND %s
            ORDER BY decision_date ASC, id ASC
            """,
            (
                config_id,
                self._normalize_date(week_start_date),
                self._normalize_date(week_end_date),
            ),
        ).fetchall()
        return [dict(row) for row in rows]
