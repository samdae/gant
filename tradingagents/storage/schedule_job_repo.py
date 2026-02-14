"""Schedule job repository for error/retry history."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class ScheduleJobRepository:
    """Repository for schedule_jobs table CRUD operations."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        schedule_id: int,
        error_type: str,
        error_message: str,
        error_detail: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        created_at = datetime.now().isoformat()
        connection = conn or self.conn
        cursor = connection.execute(
            """
            INSERT INTO schedule_jobs (schedule_id, error_type, error_message, error_detail, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (schedule_id, error_type, error_message, error_detail, created_at)
        )
        if commit:
            connection.commit()

        job_id = cursor.lastrowid
        logger.info(
            f"Created schedule_job {job_id} for schedule {schedule_id} ({error_type})"
        )
        return int(job_id) if job_id is not None else 0

    def list_by_schedule(self, schedule_id: int) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            """
            SELECT id, schedule_id, error_type, error_message, error_detail, created_at
            FROM schedule_jobs
            WHERE schedule_id = ?
            ORDER BY created_at ASC
            """,
            (schedule_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
