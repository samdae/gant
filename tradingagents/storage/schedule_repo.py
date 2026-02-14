"""Schedule repository for CRUD operations on schedules table."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class ScheduleRepository:
    """Repository for schedules table CRUD operations."""

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def create(self, ticker: str, cycle: int, interval_days: int = 4, commit: bool = True, conn=None) -> int:
        """Create a new schedule entry.

        Args:
            ticker: Ticker symbol
            cycle: Schedule cycle number

        Returns:
            Schedule ID
        """
        created_at = datetime.now().isoformat()

        connection = conn or self.conn
        cursor = connection.execute(
            """
            INSERT INTO schedules (ticker, interval_days, scheduled_cycle, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (ticker, interval_days, cycle, created_at)
        )
        if commit:
            connection.commit()

        schedule_id = cursor.lastrowid
        if schedule_id is None:
            raise RuntimeError("Failed to create schedule entry")
        schedule_id = int(schedule_id)
        logger.info(f"Created schedule {schedule_id} for {ticker} (cycle {cycle})")
        return schedule_id

    def update_status(
        self,
        schedule_id: int,
        status: str,
        error_message: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> None:
        """Update schedule status.

        Args:
            schedule_id: Schedule ID
            status: New status (pending/running/done/failed)
            error_message: Optional error message (for failed status)
        """
        connection = conn or self.conn
        connection.execute(
            """
            UPDATE schedules
            SET status = ?, error_message = ?
            WHERE id = ?
            """,
            (status, error_message, schedule_id)
        )
        if commit:
            connection.commit()

        logger.info(f"Updated schedule {schedule_id} status to {status}")

    def get_by_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        """Get all schedules for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            List of schedule dicts
        """
        cursor = self.conn.execute(
            """
            SELECT id, ticker, interval_days, scheduled_cycle, status, error_message, created_at
            FROM schedules
            WHERE ticker = ?
            ORDER BY created_at DESC
            """,
            (ticker,)
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_latest_cycle(self, ticker: str) -> int:
        """Get the latest cycle number for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Latest cycle number (0 if no schedules exist)
        """
        cursor = self.conn.execute(
            """
            SELECT MAX(scheduled_cycle) as max_cycle
            FROM schedules
            WHERE ticker = ?
            """,
            (ticker,)
        )

        result = cursor.fetchone()
        max_cycle = result[0] if result[0] is not None else 0

        return max_cycle

    def get_by_status(self, statuses: List[str]) -> List[Dict[str, Any]]:
        """Get schedules by status (for recovery on server restart).

        Args:
            statuses: List of status values (e.g., ['pending', 'running'])

        Returns:
            List of schedule dicts
        """
        placeholders = ', '.join(['?'] * len(statuses))
        query = f"""
            SELECT id, ticker, interval_days, scheduled_cycle, status, error_message, created_at
            FROM schedules
            WHERE status IN ({placeholders})
            ORDER BY created_at ASC
        """

        cursor = self.conn.execute(query, statuses)
        return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    # Test schedule repository
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        import os
        from .database import Database

        db_path = os.path.join(temp_dir, "test_trading.db")
        db = Database(db_path)
        db.init_schema()

        repo = ScheduleRepository(db)

        # Test create
        print("\n1. Creating schedules...")
        schedule_id_1 = repo.create("NVDA", 1)
        schedule_id_2 = repo.create("NVDA", 2)
        schedule_id_3 = repo.create("AAPL", 1)
        print(f"   Created schedule IDs: {schedule_id_1}, {schedule_id_2}, {schedule_id_3}")

        # Test get_latest_cycle
        print("\n2. Getting latest cycle for NVDA...")
        latest_cycle = repo.get_latest_cycle("NVDA")
        print(f"   Latest cycle: {latest_cycle}")
        assert latest_cycle == 2, f"Expected 2, got {latest_cycle}"

        # Test update_status
        print("\n3. Updating status...")
        repo.update_status(schedule_id_1, "done")
        repo.update_status(schedule_id_2, "failed", "Test error message")

        # Test get_by_ticker
        print("\n4. Getting schedules for NVDA...")
        schedules = repo.get_by_ticker("NVDA")
        print(f"   Found {len(schedules)} schedules")
        for s in schedules:
            print(f"   - Schedule {s['id']}: cycle={s['scheduled_cycle']}, status={s['status']}")

        # Test get_by_status
        print("\n5. Getting schedules by status...")
        pending_schedules = repo.get_by_status(['pending', 'running'])
        print(f"   Found {len(pending_schedules)} pending/running schedules")

        print("\n✅ ScheduleRepository test passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")
