"""Portfolio holding snapshot repository."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


class PortfolioHoldingRepository:
    """Repository for `portfolio_holdings` table."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _normalize_date(value: Any) -> str:
        if isinstance(value, date):
            return value.isoformat()
        text = str(value or "").strip()
        return text[:10] if text else date.today().isoformat()

    def create_snapshot(
        self,
        config_id: int,
        snapshot_date: Any,
        ticker: str,
        shares: float,
        avg_cost: float,
        currency: str,
        current_value_krw: float,
        allocation_pct: float,
        commit: bool = True,
        conn=None,
    ) -> int:
        connection = conn or self.db.get_connection()
        normalized_date = self._normalize_date(snapshot_date)
        cursor = connection.execute(
            """
            INSERT INTO portfolio_holdings (
                portfolio_config_id, snapshot_date, ticker, shares, avg_cost,
                currency, current_value_krw, allocation_pct
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (portfolio_config_id, ticker, snapshot_date)
            DO UPDATE SET
                shares = excluded.shares,
                avg_cost = excluded.avg_cost,
                currency = excluded.currency,
                current_value_krw = excluded.current_value_krw,
                allocation_pct = excluded.allocation_pct
            RETURNING id
            """,
            (
                config_id,
                normalized_date,
                str(ticker).upper(),
                float(shares),
                float(avg_cost),
                str(currency).upper(),
                float(current_value_krw),
                float(allocation_pct),
            ),
        )
        if commit:
            connection.commit()
        row = cursor.fetchone()
        snapshot_id = int(row["id"]) if row else 0
        return snapshot_id

    def get_latest_snapshot_date(self, config_id: int) -> Optional[str]:
        row = self.db.get_connection().execute(
            """
            SELECT MAX(snapshot_date) AS snapshot_date
            FROM portfolio_holdings
            WHERE portfolio_config_id = %s
            """,
            (config_id,),
        ).fetchone()
        if not row or not row.get("snapshot_date"):
            return None
        value = row["snapshot_date"]
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    def list_latest(self, config_id: int) -> List[Dict[str, Any]]:
        latest_date = self.get_latest_snapshot_date(config_id)
        if not latest_date:
            return []
        rows = self.db.get_connection().execute(
            """
            SELECT id, portfolio_config_id, snapshot_date, ticker, shares,
                   avg_cost, currency, current_value_krw, allocation_pct, created_at
            FROM portfolio_holdings
            WHERE portfolio_config_id = %s
              AND snapshot_date = %s
            ORDER BY allocation_pct DESC, ticker ASC
            """,
            (config_id, latest_date),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_by_date_range(
        self,
        config_id: int,
        date_from: Any,
        date_to: Any,
    ) -> List[Dict[str, Any]]:
        rows = self.db.get_connection().execute(
            """
            SELECT id, portfolio_config_id, snapshot_date, ticker, shares,
                   avg_cost, currency, current_value_krw, allocation_pct, created_at
            FROM portfolio_holdings
            WHERE portfolio_config_id = %s
              AND snapshot_date BETWEEN %s AND %s
            ORDER BY snapshot_date ASC, ticker ASC
            """,
            (
                config_id,
                self._normalize_date(date_from),
                self._normalize_date(date_to),
            ),
        ).fetchall()
        return [dict(row) for row in rows]

    def cleanup_old_snapshots(
        self,
        config_id: int,
        days: int = 14,
        commit: bool = True,
        conn=None,
    ) -> int:
        keep_days = max(int(days), 1)
        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            DELETE FROM portfolio_holdings
            WHERE portfolio_config_id = %s
              AND snapshot_date < (CURRENT_DATE - (%s || ' days')::interval)
            RETURNING id
            """,
            (config_id, keep_days),
        )
        deleted = len(cursor.fetchall())
        if commit:
            connection.commit()
        if deleted:
            logger.info(
                "Deleted %s old portfolio holding snapshots (config=%s, keep_days=%s)",
                deleted,
                config_id,
                keep_days,
            )
        return deleted
