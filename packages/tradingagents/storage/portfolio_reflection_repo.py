"""Portfolio weekly reflection repository."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


class PortfolioReflectionRepository:
    """Repository for `portfolio_reflections` table."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _normalize_date(value: Any) -> str:
        if isinstance(value, date):
            return value.isoformat()
        text = str(value or "").strip()
        return text[:10] if text else date.today().isoformat()

    def create(
        self,
        config_id: int,
        week_start_date: Any,
        week_end_date: Any,
        reflection_content: str,
        allocation_accuracy: Optional[int],
        total_return_pct: Optional[float],
        key_lessons: Optional[str],
        commit: bool = True,
        conn=None,
    ) -> int:
        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO portfolio_reflections (
                portfolio_config_id, week_start_date, week_end_date,
                reflection_content, allocation_accuracy, total_return_pct,
                key_lessons
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (portfolio_config_id, week_start_date)
            DO UPDATE SET
                week_end_date = excluded.week_end_date,
                reflection_content = excluded.reflection_content,
                allocation_accuracy = excluded.allocation_accuracy,
                total_return_pct = excluded.total_return_pct,
                key_lessons = excluded.key_lessons
            RETURNING id
            """,
            (
                config_id,
                self._normalize_date(week_start_date),
                self._normalize_date(week_end_date),
                reflection_content,
                int(allocation_accuracy) if allocation_accuracy is not None else None,
                float(total_return_pct) if total_return_pct is not None else None,
                key_lessons,
            ),
        )
        if commit:
            connection.commit()
        row = cursor.fetchone()
        reflection_id = int(row["id"]) if row else 0
        logger.info(
            "Upserted portfolio_reflection %s (config=%s, week_start=%s)",
            reflection_id,
            config_id,
            self._normalize_date(week_start_date),
        )
        return reflection_id

    def get_by_id(self, reflection_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.get_connection().execute(
            """
            SELECT id, portfolio_config_id, week_start_date, week_end_date,
                   reflection_content, allocation_accuracy, total_return_pct,
                   key_lessons, created_at
            FROM portfolio_reflections
            WHERE id = %s
            LIMIT 1
            """,
            (reflection_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_by_week(self, config_id: int, week_start_date: Any) -> Optional[Dict[str, Any]]:
        row = self.db.get_connection().execute(
            """
            SELECT id, portfolio_config_id, week_start_date, week_end_date,
                   reflection_content, allocation_accuracy, total_return_pct,
                   key_lessons, created_at
            FROM portfolio_reflections
            WHERE portfolio_config_id = %s AND week_start_date = %s
            LIMIT 1
            """,
            (config_id, self._normalize_date(week_start_date)),
        ).fetchone()
        return dict(row) if row else None

    def list_recent(
        self,
        config_id: int,
        cursor: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT id, portfolio_config_id, week_start_date, week_end_date,
                   reflection_content, allocation_accuracy, total_return_pct,
                   key_lessons, created_at
            FROM portfolio_reflections
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
