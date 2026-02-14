"""Trade repository for CRUD operations on trades table."""

import logging
from typing import Dict, Any, List
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class TradeRepository:
    """Repository for trades table CRUD operations."""

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        position_id: int,
        report_id: int,
        action: str,
        shares: int,
        price: float,
        commit: bool = True,
        conn=None,
    ) -> int:
        """Create a new trade record.

        Args:
            position_id: Position ID
            report_id: Report ID (which analysis triggered this trade)
            action: 'BUY' or 'SELL'
            shares: Number of shares traded
            price: Price per share

        Returns:
            Trade ID
        """
        executed_at = datetime.now().isoformat()

        connection = conn or self.conn
        cursor = connection.execute(
            """
            INSERT INTO trades (position_id, report_id, action, shares, price, executed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (position_id, report_id, action, shares, price, executed_at)
        )
        if commit:
            connection.commit()

        trade_id = int(cursor.lastrowid)
        logger.info(
            f"Created trade {trade_id}: {action} {shares} shares @ ${price:.2f} "
            f"(position={position_id})"
        )
        return trade_id

    def get_by_position(self, position_id: int) -> List[Dict[str, Any]]:
        """Get all trades for a position (ordered by execution time).

        Args:
            position_id: Position ID

        Returns:
            List of trade dicts (ordered oldest to newest)
        """
        cursor = self.conn.execute(
            """
            SELECT id, position_id, report_id, action, shares, price, executed_at
            FROM trades
            WHERE position_id = ?
            ORDER BY executed_at ASC
            """,
            (position_id,)
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_history(self, ticker: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trade history for a ticker.

        Args:
            ticker: Ticker symbol
            limit: Maximum number of trades to return (default 50)

        Returns:
            List of trade dicts with position info (ordered newest to oldest)
        """
        cursor = self.conn.execute(
            """
            SELECT t.id, t.position_id, t.report_id, t.action, t.shares, t.price, t.executed_at,
                   p.ticker
            FROM trades t
            JOIN positions p ON t.position_id = p.id
            WHERE p.ticker = ?
            ORDER BY t.executed_at DESC
            LIMIT ?
            """,
            (ticker, limit)
        )

        return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    # Test trade repository
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        import os
        from .database import Database
        from .schedule_repo import ScheduleRepository
        from .position_repo import PositionRepository
        from .report_repo import ReportRepository

        db_path = os.path.join(temp_dir, "test_trading.db")
        db = Database(db_path)
        db.init_schema()

        # Create dependencies
        schedule_repo = ScheduleRepository(db)
        position_repo = PositionRepository(db)
        report_repo = ReportRepository(db)

        schedule_id = schedule_repo.create("NVDA", 1)
        position_id = position_repo.create("NVDA")
        report_id = report_repo.create(schedule_id, position_id, {
            "market_report": "Test",
            "pa_opinion": "Test PA"
        })

        repo = TradeRepository(db)

        # Test create
        print("\n1. Creating trades...")
        trade_id_1 = repo.create(position_id, report_id, "BUY", shares=10, price=250.0)
        trade_id_2 = repo.create(position_id, report_id, "BUY", shares=5, price=260.0)
        trade_id_3 = repo.create(position_id, report_id, "SELL", shares=15, price=280.0)
        print(f"   Created trade IDs: {trade_id_1}, {trade_id_2}, {trade_id_3}")

        # Test get_by_position
        print("\n2. Getting trades by position...")
        trades = repo.get_by_position(position_id)
        print(f"   Found {len(trades)} trades:")
        for t in trades:
            print(f"   - Trade {t['id']}: {t['action']} {t['shares']} @ ${t['price']:.2f}")

        # Test get_history
        print("\n3. Getting trade history for NVDA...")
        history = repo.get_history("NVDA", limit=10)
        print(f"   Found {len(history)} trades in history")

        print("\n✅ TradeRepository test passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")
