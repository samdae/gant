"""Position repository for CRUD operations on positions table."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class PositionRepository:
    """Repository for positions table CRUD operations."""

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def create(self, ticker: str, commit: bool = True, conn=None) -> int:
        """Create a new active position.

        Args:
            ticker: Ticker symbol

        Returns:
            Position ID
        """
        now = datetime.now().isoformat()

        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO positions (ticker, status, shares, opened_at, created_at)
            VALUES (%s, 'active', 0, %s, %s)
            RETURNING id
            """,
            (ticker, now, now)
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        position_id = row["id"] if row else 0
        logger.info(f"Created position {position_id} for {ticker}")
        return position_id

    def get_active(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get active position for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Position dict or None if no active position
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT id, ticker, status, shares, avg_cost, return_pct,
                   opened_at, closed_at, created_at
            FROM positions
            WHERE ticker = %s AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (ticker,)
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    def get_by_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        """Get position by ID.

        Args:
            position_id: Position ID

        Returns:
            Position dict or None if not found
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT id, ticker, status, shares, avg_cost, return_pct,
                   opened_at, closed_at, created_at
            FROM positions
            WHERE id = %s
            """,
            (position_id,)
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    def update_shares(
        self,
        position_id: int,
        shares: float,
        avg_cost: float,
        commit: bool = True,
        conn=None,
    ) -> None:
        """Update position shares and average cost.

        Args:
            position_id: Position ID
            shares: New total shares
            avg_cost: New average cost per share
        """
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE positions
            SET shares = %s, avg_cost = %s
            WHERE id = %s
            """,
            (shares, avg_cost, position_id)
        )
        if commit:
            connection.commit()

        logger.info(
            f"Updated position {position_id}: shares={shares:.2f}, avg_cost=${avg_cost:.2f}"
        )

    def close_position(
        self,
        position_id: int,
        return_pct: float,
        commit: bool = True,
        conn=None,
    ) -> None:
        """Close a position (mark as closed).

        Args:
            position_id: Position ID
            return_pct: Realized return percentage
        """
        closed_at = datetime.now().isoformat()

        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE positions
            SET status = 'closed', return_pct = %s, closed_at = %s
            WHERE id = %s
            """,
            (return_pct, closed_at, position_id)
        )
        if commit:
            connection.commit()

        logger.info(
            f"Closed position {position_id}: return {return_pct:.2f}%"
        )


if __name__ == "__main__":
    # Test position repository
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

        repo = PositionRepository(db)

        # Test create
        print("\n1. Creating position...")
        position_id = repo.create("NVDA")
        print(f"   Created position ID: {position_id}")

        # Test get_active
        print("\n2. Getting active position...")
        position = repo.get_active("NVDA")
        print(f"   Found position: {position['id']}, shares={position['shares']}")

        # Test update_shares
        print("\n3. Updating shares...")
        repo.update_shares(position_id, shares=10, avg_cost=250.0)
        position = repo.get_by_id(position_id)
        print(f"   Updated: shares={position['shares']}, avg_cost=${position['avg_cost']:.2f}")

        # Test close_position
        print("\n4. Closing position...")
        repo.close_position(position_id, return_pct=15.5)
        position = repo.get_by_id(position_id)
        print(f"   Closed: status={position['status']}, return={position['return_pct']}%")

        # Test get_active after close
        print("\n5. Checking active position after close...")
        active = repo.get_active("NVDA")
        print(f"   Active position: {active}")
        assert active is None, "Expected no active position after close"

        print("\n✅ PositionRepository test passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")
