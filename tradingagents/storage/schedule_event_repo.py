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
