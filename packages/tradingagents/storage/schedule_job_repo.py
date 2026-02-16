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
        status: str,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_detail: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        created_at = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        safe_error_type = error_type if error_type is not None else ""
        safe_error_message = error_message if error_message is not None else ""

        cursor = connection.execute(
            """
            INSERT INTO schedule_jobs (
                schedule_id,
                status,
                error_type,
                error_message,
                error_detail,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                schedule_id,
                status,
                safe_error_type,
                safe_error_message,
                error_detail,
                created_at,
            )
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        job_id = row["id"] if row else None
        logger.info(
            f"Created schedule_job {job_id} for schedule {schedule_id} (status={status})"
        )
        return int(job_id) if job_id is not None else 0

    def update_status(
        self,
        job_id: int,
        status: str,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_detail: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> None:
        connection = conn or self.db.get_connection()
        safe_error_type = error_type if error_type is not None else ""
        safe_error_message = error_message if error_message is not None else ""

        connection.execute(
            """
            UPDATE schedule_jobs
            SET status = %s, error_type = %s, error_message = %s, error_detail = %s
            WHERE id = %s
            """,
            (status, safe_error_type, safe_error_message, error_detail, job_id)
        )
        if commit:
            connection.commit()

        logger.info(f"Updated schedule_job {job_id} status to {status}")

    def update_by_schedule(
        self,
        schedule_id: int,
        status: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_detail: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> None:
        connection = conn or self.db.get_connection()
        fields = []
        values: List[Any] = []

        if status is not None:
            fields.append("status = %s")
            values.append(status)
        if error_type is not None or status is not None:
            fields.append("error_type = %s")
            values.append(error_type)
        if error_message is not None or status is not None:
            fields.append("error_message = %s")
            values.append(error_message)
        if error_detail is not None or status is not None:
            fields.append("error_detail = %s")
            values.append(error_detail)

        if not fields:
            return

        values.append(schedule_id)
        connection.execute(
            f"UPDATE schedule_jobs SET {', '.join(fields)} WHERE schedule_id = %s",
            tuple(values)
        )
        if commit:
            connection.commit()

    def update_latest_by_schedule(
        self,
        schedule_id: int,
        status: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_detail: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> None:
        latest = self.get_latest_by_schedule(schedule_id)
        if not latest:
            return

        current_status = latest.get("status") or ""
        current_error_type = latest.get("error_type") or ""
        current_error_message = latest.get("error_message") or ""
        current_error_detail = latest.get("error_detail")

        next_status = status if status is not None else current_status
        next_error_type = error_type if error_type is not None else current_error_type
        next_error_message = (
            error_message if error_message is not None else current_error_message
        )
        next_error_detail = (
            error_detail if error_detail is not None else current_error_detail
        )

        self.update_status(
            latest["id"],
            next_status,
            error_type=next_error_type,
            error_message=next_error_message,
            error_detail=next_error_detail,
            commit=commit,
            conn=conn,
        )

    def list_by_schedule(self, schedule_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, schedule_id, status, error_type, error_message, error_detail, created_at
            FROM schedule_jobs
            WHERE schedule_id = %s
            ORDER BY created_at ASC
            """,
            (schedule_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_latest_by_schedule(self, schedule_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, schedule_id, status, error_type, error_message, error_detail, created_at
            FROM schedule_jobs
            WHERE schedule_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (schedule_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_latest_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT sj.id, sj.schedule_id, sj.status, sj.error_type, sj.error_message,
                   sj.error_detail, sj.created_at
            FROM schedule_jobs sj
            JOIN schedules s ON s.id = sj.schedule_id
            WHERE s.ticker = %s
            ORDER BY s.created_at DESC
            LIMIT 1
            """,
            (ticker,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def has_done_today_for_ticker(self, ticker: str, today: str) -> bool:
        cursor = self.db.get_connection().execute(
            """
            SELECT 1
            FROM schedule_jobs sj
            JOIN schedules s ON s.id = sj.schedule_id
            WHERE s.ticker = %s
              AND sj.status = 'done'
              AND date(sj.created_at) = %s
            LIMIT 1
            """,
            (ticker, today)
        )
        return cursor.fetchone() is not None
