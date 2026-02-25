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
        shares: float,
        price: float,
        currency: str = "USD",
        executed_at: str = None,
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
            currency: Trade currency
            executed_at: Execution timestamp (defaults to now)

        Returns:
            Trade ID
        """
        if executed_at is None:
            executed_at = datetime.now().isoformat()

        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO trades (position_id, report_id, action, shares, price,
                                currency, executed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (position_id, report_id, action, shares, price, currency, executed_at),
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        trade_id = int(row["id"]) if row else 0
        logger.info(
            f"Created trade {trade_id}: {action} {shares:.2f} shares @ {price:.2f} "
            f"{currency} (position={position_id})"
        )
        return trade_id

    def get_by_position(self, position_id: int) -> List[Dict[str, Any]]:
        """Get all trades for a position (ordered by execution time).

        Args:
            position_id: Position ID

        Returns:
            List of trade dicts (ordered oldest to newest)
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT id, position_id, report_id, action, shares, price, executed_at
            FROM trades
            WHERE position_id = %s
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
        cursor = self.db.get_connection().execute(
            """
            SELECT t.id, t.position_id, t.report_id, t.action, t.shares, t.price, t.executed_at,
                   p.ticker
            FROM trades t
            JOIN positions p ON t.position_id = p.id
            WHERE p.ticker = %s
            ORDER BY t.executed_at DESC
            LIMIT %s
            """,
            (ticker, limit)
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_cash_balance(self, ticker: str, initial_capital: float) -> float:
        """Calculate available cash balance for the current active position.

        Only considers trades belonging to the active position for this ticker.
        cash = initial_capital - BUY total + SELL total (for the active position only).
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN t.action = 'SELL' THEN t.shares * t.price
                        WHEN t.action = 'BUY' THEN -t.shares * t.price
                        ELSE 0
                    END
                ),
                0
            ) AS net_cash
            FROM trades t
            JOIN positions p ON t.position_id = p.id
            WHERE p.ticker = %s AND p.status = 'active'
            """,
            (ticker,),
        )
        row = cursor.fetchone()
        net_cash = float(row["net_cash"]) if row and row.get("net_cash") is not None else 0.0
        return float(initial_capital) + net_cash


