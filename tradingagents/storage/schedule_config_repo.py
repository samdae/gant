"""Schedule configuration repository for persistent schedules."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class ScheduleConfigRepository:
    """Repository for schedule_configs table CRUD operations."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        ticker: str,
        interval_days: int,
        commit: bool = True,
        conn=None,
    ) -> int:
        created_at = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO schedule_configs (ticker, interval_days, created_at)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (ticker, interval_days, created_at),
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        schedule_id = row["id"] if row else None
        if schedule_id is None:
            raise RuntimeError("Failed to create schedule config")
        logger.info(f"Created schedule_config {schedule_id} for {ticker}")
        return int(schedule_id)

    def upsert(
        self,
        ticker: str,
        interval_days: int,
        commit: bool = True,
        conn=None,
    ) -> int:
        created_at = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            INSERT INTO schedule_configs (ticker, interval_days, created_at)
            VALUES (%s, %s, %s)
            ON CONFLICT(ticker)
            DO UPDATE SET interval_days = excluded.interval_days
            """,
            (ticker, interval_days, created_at),
        )
        if commit:
            connection.commit()

        row = connection.execute(
            "SELECT id FROM schedule_configs WHERE ticker = %s",
            (ticker,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to read schedule config")
        return int(row["id"])

    def get_all(self) -> List[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, ticker, interval_days, last_data_date, created_at
            FROM schedule_configs
            ORDER BY created_at ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, ticker, interval_days, last_data_date, created_at
            FROM schedule_configs
            WHERE ticker = %s
            LIMIT 1
            """,
            (ticker,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def delete(self, ticker: str, commit: bool = True, conn=None) -> None:
        connection = conn or self.db.get_connection()
        connection.execute(
            "DELETE FROM schedule_configs WHERE ticker = %s",
            (ticker,),
        )
        if commit:
            connection.commit()

        logger.info(f"Deleted schedule_config for {ticker}")

    def update_last_data_date(
        self,
        ticker: str,
        last_data_date: str,
        commit: bool = True,
        conn=None,
    ) -> None:
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE schedule_configs
            SET last_data_date = %s
            WHERE ticker = %s
            """,
            (last_data_date, ticker),
        )
        if commit:
            connection.commit()
