"""Portfolio trade repository."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


class PortfolioTradeRepository:
    """Repository for `portfolio_trades` table."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _normalize_date(value: Any) -> str:
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]

    def create_batch(
        self,
        trades: List[Dict[str, Any]],
        commit: bool = True,
        conn=None,
    ) -> List[int]:
        if not trades:
            return []

        connection = conn or self.db.get_connection()
        created_ids: List[int] = []
        for item in trades:
            executed_at = item.get("executed_at") or datetime.now().isoformat()
            cursor = connection.execute(
                """
                INSERT INTO portfolio_trades (
                    portfolio_decision_id, ticker, action, shares, price, currency,
                    exchange_rate, fee_rate, fee_amount, amount_local, amount_krw,
                    executed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    int(item["portfolio_decision_id"]),
                    str(item["ticker"]).upper(),
                    str(item.get("action", "hold")).lower(),
                    float(item.get("shares", 0.0)),
                    float(item.get("price", 0.0)),
                    str(item.get("currency", "USD")).upper(),
                    float(item.get("exchange_rate", 1.0)),
                    float(item.get("fee_rate", 0.0)),
                    float(item.get("fee_amount", 0.0)),
                    float(item.get("amount_local", 0.0)),
                    float(item.get("amount_krw", 0.0)),
                    executed_at,
                ),
            )
            row = cursor.fetchone()
            if row:
                created_ids.append(int(row["id"]))

        if commit:
            connection.commit()

        logger.info("Inserted %s portfolio_trades", len(created_ids))
        return created_ids

    def list_by_decision(self, decision_id: int) -> List[Dict[str, Any]]:
        rows = self.db.get_connection().execute(
            """
            SELECT id, portfolio_decision_id, ticker, action, shares, price, currency,
                   exchange_rate, fee_rate, fee_amount, amount_local, amount_krw,
                   executed_at
            FROM portfolio_trades
            WHERE portfolio_decision_id = %s
            ORDER BY id ASC
            """,
            (decision_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_recent(
        self,
        config_id: int,
        ticker: Optional[str] = None,
        cursor: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT pt.id, pt.portfolio_decision_id, pt.ticker, pt.action,
                   pt.shares, pt.price, pt.currency, pt.exchange_rate,
                   pt.fee_rate, pt.fee_amount, pt.amount_local, pt.amount_krw,
                   pt.executed_at,
                   pd.decision_date
            FROM portfolio_trades pt
            JOIN portfolio_decisions pd ON pd.id = pt.portfolio_decision_id
            WHERE pd.portfolio_config_id = %s
        """
        params: List[Any] = [config_id]
        if ticker:
            query += " AND pt.ticker = %s"
            params.append(str(ticker).upper())
        if cursor:
            query += " AND pt.id < %s"
            params.append(cursor)
        query += " ORDER BY pt.id DESC LIMIT %s"
        params.append(limit)
        rows = self.db.get_connection().execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_by_week(
        self,
        config_id: int,
        week_start_date: Any,
        week_end_date: Any,
    ) -> List[Dict[str, Any]]:
        rows = self.db.get_connection().execute(
            """
            SELECT pt.id, pt.portfolio_decision_id, pt.ticker, pt.action,
                   pt.shares, pt.price, pt.currency, pt.exchange_rate,
                   pt.fee_rate, pt.fee_amount, pt.amount_local, pt.amount_krw,
                   pt.executed_at,
                   pd.decision_date
            FROM portfolio_trades pt
            JOIN portfolio_decisions pd ON pd.id = pt.portfolio_decision_id
            WHERE pd.portfolio_config_id = %s
              AND pd.decision_date BETWEEN %s AND %s
            ORDER BY pt.id ASC
            """,
            (
                config_id,
                self._normalize_date(week_start_date),
                self._normalize_date(week_end_date),
            ),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_summary_by_ticker(self, config_id: int) -> List[Dict[str, Any]]:
        rows = self.db.get_connection().execute(
            """
            SELECT pt.ticker,
                   SUM(CASE WHEN pt.action = 'buy' THEN pt.shares ELSE 0 END) AS bought_shares,
                   SUM(CASE WHEN pt.action = 'sell' THEN pt.shares ELSE 0 END) AS sold_shares,
                   SUM(CASE WHEN pt.action = 'buy' THEN pt.amount_krw ELSE 0 END) AS buy_amount_krw,
                   SUM(CASE WHEN pt.action = 'sell' THEN pt.amount_krw ELSE 0 END) AS sell_amount_krw
            FROM portfolio_trades pt
            JOIN portfolio_decisions pd ON pd.id = pt.portfolio_decision_id
            WHERE pd.portfolio_config_id = %s
            GROUP BY pt.ticker
            ORDER BY pt.ticker ASC
            """,
            (config_id,),
        ).fetchall()
        return [dict(row) for row in rows]
