"""Schedule repository for CRUD operations on schedules table."""

import logging
from typing import List, Dict, Any
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

        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO schedules (ticker, interval_days, scheduled_cycle, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (ticker, interval_days, cycle, created_at)
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        schedule_id = row["id"] if row else None
        if schedule_id is None:
            raise RuntimeError("Failed to create schedule entry")
        schedule_id = int(schedule_id)
        logger.info(f"Created schedule {schedule_id} for {ticker} (cycle {cycle})")
        return schedule_id

    def get_by_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        """Get all schedules for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            List of schedule dicts
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT id, ticker, interval_days, scheduled_cycle, created_at
            FROM schedules
            WHERE ticker = %s
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
        cursor = self.db.get_connection().execute(
            """
            SELECT MAX(scheduled_cycle) as max_cycle
            FROM schedules
            WHERE ticker = %s
            """,
            (ticker,)
        )

        result = cursor.fetchone()
        max_cycle = result["max_cycle"] if result and result["max_cycle"] is not None else 0

        return max_cycle

if __name__ == "__main__":
    # Test schedule repository
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        import os
        from .database import Database

        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            print("SUPABASE_DB_URL not set; skipping test")
            raise SystemExit(0)

        db = Database(db_url)
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

        # Test get_by_ticker
        print("\n3. Getting schedules for NVDA...")
        schedules = repo.get_by_ticker("NVDA")
        print(f"   Found {len(schedules)} schedules")
        for s in schedules:
            print(f"   - Schedule {s['id']}: cycle={s['scheduled_cycle']}")

        print("\n✅ ScheduleRepository test passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")
