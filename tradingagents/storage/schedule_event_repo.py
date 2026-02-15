"""Schedule job event repository."""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


class ScheduleEventRepository:
    """Repository for schedule_job_events table."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        ticker: str,
        agent: str,
        status: str,
        message: str,
        schedule_id: Optional[int] = None,
        schedule_job_id: Optional[int] = None,
        step: Optional[int] = None,
        phase: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        created_at = datetime.now().isoformat()
        connection = conn or self.db.get_connection()

        if schedule_job_id and agent:
            cursor = connection.execute(
                """
                INSERT INTO schedule_job_events (
                    schedule_job_id, schedule_id, ticker, agent, status,
                    message, step, phase, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (schedule_job_id, agent)
                DO UPDATE SET
                    status = excluded.status,
                    message = excluded.message,
                    step = excluded.step,
                    phase = excluded.phase,
                    created_at = excluded.created_at
                RETURNING id
                """,
                (
                    schedule_job_id,
                    schedule_id,
                    ticker,
                    agent,
                    status,
                    message,
                    step,
                    phase,
                    created_at,
                ),
            )
        else:
            cursor = connection.execute(
                """
                INSERT INTO schedule_job_events (
                    schedule_job_id, schedule_id, ticker, agent, status,
                    message, step, phase, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    schedule_job_id,
                    schedule_id,
                    ticker,
                    agent,
                    status,
                    message,
                    step,
                    phase,
                    created_at,
                ),
            )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        event_id = int(row["id"]) if row else 0
        logger.info(
            "Stored schedule event %s for %s (%s %s)",
            event_id,
            ticker,
            agent,
            status,
        )
        return event_id

    def list_by_ticker(self, ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, schedule_job_id, schedule_id, ticker, agent, status,
                   message, step, phase, created_at
            FROM schedule_job_events
            WHERE ticker = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (ticker, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_latest_by_ticker(self, ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        row = conn.execute(
            """
            SELECT schedule_job_id
            FROM schedule_job_events
            WHERE ticker = %s AND schedule_job_id IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (ticker,),
        ).fetchone()

        if not row:
            return []

        schedule_job_id = row["schedule_job_id"]
        cursor = conn.execute(
            """
            SELECT id, schedule_job_id, schedule_id, ticker, agent, status,
                   message, step, phase, created_at
            FROM schedule_job_events
            WHERE schedule_job_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (schedule_job_id, limit),
        )
        return [dict(r) for r in cursor.fetchall()]
