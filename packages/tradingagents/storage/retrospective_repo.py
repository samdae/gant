"""Retrospective analysis repository for CRUD operations."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class RetrospectiveRepository:
    """Repository for retrospective_analyses table CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def upsert(
        self,
        position_id: int,
        ticker: str,
        position_sequence: int,
        position_status: str,
        position_open_date: Optional[str] = None,
        position_close_date: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        """Insert or update a retrospective analysis record.

        On conflict (same position_id), resets status to 'pending' and bumps analysis_count.
        """
        now = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO retrospective_analyses (
                position_id, ticker, position_sequence,
                position_status, status,
                position_open_date, position_close_date,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, %s)
            ON CONFLICT (position_id) DO UPDATE SET
                position_status = EXCLUDED.position_status,
                status = 'pending',
                analysis_count = retrospective_analyses.analysis_count + 1,
                position_close_date = EXCLUDED.position_close_date,
                error_message = NULL,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            (
                position_id, ticker, position_sequence,
                position_status,
                position_open_date, position_close_date,
                now, now,
            ),
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        retro_id = int(row["id"]) if row else 0
        logger.info(
            f"Upserted retrospective analysis {retro_id} for {ticker} "
            f"position_id={position_id} seq={position_sequence}"
        )
        return retro_id

    def update_status(
        self,
        retro_id: int,
        status: str,
        analysis_content: Optional[str] = None,
        error_message: Optional[str] = None,
        commit: bool = True,
        conn=None,
    ) -> None:
        """Update analysis status (pending -> running -> completed/failed)."""
        now = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE retrospective_analyses
            SET status = %s,
                analysis_content = COALESCE(%s, analysis_content),
                error_message = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (status, analysis_content, error_message, now, retro_id),
        )
        if commit:
            connection.commit()
        logger.info(f"Updated retrospective {retro_id} status={status}")

    def get_by_id(self, retro_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, position_id, ticker, position_sequence,
                   position_status, status, analysis_content,
                   analysis_count, position_open_date, position_close_date,
                   error_message, created_at, updated_at
            FROM retrospective_analyses
            WHERE id = %s
            """,
            (retro_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_incomplete(self) -> List[Dict[str, Any]]:
        """Return all retrospective analyses stuck in pending/running."""
        cursor = self.db.get_connection().execute(
            """
            SELECT id, position_id, ticker, position_sequence, position_status
            FROM retrospective_analyses
            WHERE status IN ('pending', 'running')
            ORDER BY id
            """,
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_position_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, position_id, ticker, position_sequence,
                   position_status, status, analysis_content,
                   analysis_count, position_open_date, position_close_date,
                   error_message, created_at, updated_at
            FROM retrospective_analyses
            WHERE position_id = %s
            """,
            (position_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_positions_with_status(self, ticker: str) -> List[Dict[str, Any]]:
        """Get all positions for a ticker with retrospective analysis status.

        Returns positions LEFT JOINed with retrospective_analyses.
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT p.id AS position_id, p.ticker, p.status AS pos_status,
                   p.shares, p.avg_cost, p.return_pct,
                   p.opened_at, p.closed_at,
                   ROW_NUMBER() OVER (PARTITION BY p.ticker ORDER BY p.opened_at)
                       AS position_sequence,
                   ra.id AS retro_id,
                   ra.position_status AS retro_position_status,
                   ra.status AS retro_status,
                   ra.analysis_count
            FROM positions p
            LEFT JOIN retrospective_analyses ra ON ra.position_id = p.id
            WHERE p.ticker = %s
            ORDER BY p.opened_at
            """,
            (ticker,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_analyzable_tickers(self) -> List[Dict[str, Any]]:
        """Get tickers that have at least one BUY trade, with position counts."""
        cursor = self.db.get_connection().execute(
            """
            SELECT sc.ticker, sc.display_name,
                   COUNT(DISTINCT p.id) AS position_count,
                   TRUE AS has_trades
            FROM schedule_configs sc
            JOIN positions p ON p.ticker = sc.ticker
            JOIN trades t ON t.position_id = p.id AND t.action = 'BUY'
            GROUP BY sc.ticker, sc.display_name
            ORDER BY sc.ticker
            """,
        )
        has_trades = [dict(row) for row in cursor.fetchall()]

        cursor2 = self.db.get_connection().execute(
            """
            SELECT sc.ticker, sc.display_name
            FROM schedule_configs sc
            WHERE sc.ticker NOT IN (
                SELECT DISTINCT p.ticker
                FROM positions p
                JOIN trades t ON t.position_id = p.id AND t.action = 'BUY'
            )
            ORDER BY sc.ticker
            """,
        )
        no_trades = [
            {**dict(row), "position_count": 0, "has_trades": False}
            for row in cursor2.fetchall()
        ]

        return has_trades + no_trades

    def get_ticker_summary(self) -> List[Dict[str, Any]]:
        """Get tickers with completed retrospective analyses, with counts."""
        cursor = self.db.get_connection().execute(
            """
            SELECT ra.ticker,
                   sc.display_name,
                   COUNT(*) FILTER (WHERE ra.status = 'completed') AS completed_count,
                   COUNT(*) AS total_count,
                   MAX(ra.updated_at) AS latest_at
            FROM retrospective_analyses ra
            JOIN schedule_configs sc ON sc.ticker = ra.ticker
            GROUP BY ra.ticker, sc.display_name
            HAVING COUNT(*) FILTER (WHERE ra.status = 'completed') > 0
            ORDER BY MAX(ra.updated_at) DESC
            """,
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_by_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        """Get all retrospective analyses for a ticker, newest first."""
        cursor = self.db.get_connection().execute(
            """
            SELECT ra.id, ra.position_id, ra.ticker,
                   ra.position_sequence, ra.position_status,
                   ra.status, ra.analysis_content,
                   ra.analysis_count,
                   ra.position_open_date, ra.position_close_date,
                   ra.error_message, ra.created_at, ra.updated_at,
                   p.return_pct, p.status AS pos_status
            FROM retrospective_analyses ra
            JOIN positions p ON p.id = ra.position_id
            WHERE ra.ticker = %s
            ORDER BY ra.position_sequence DESC
            """,
            (ticker,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_analyzable_positions(
        self,
        tickers: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get positions eligible for retrospective analysis.

        Excludes: completed+closed, pending, running.
        """
        conditions = ["1=1"]
        params: list = []

        if tickers:
            conditions.append("p.ticker = ANY(%s)")
            params.append(tickers)

        if date_from:
            conditions.append("p.opened_at >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("p.opened_at <= %s")
            params.append(date_to)

        where = " AND ".join(conditions)

        cursor = self.db.get_connection().execute(
            f"""
            SELECT p.id AS position_id, p.ticker, p.status AS pos_status,
                   p.opened_at, p.closed_at, p.return_pct,
                   ROW_NUMBER() OVER (PARTITION BY p.ticker ORDER BY p.opened_at)
                       AS position_sequence,
                   ra.status AS retro_status,
                   ra.position_status AS retro_position_status
            FROM positions p
            LEFT JOIN retrospective_analyses ra ON ra.position_id = p.id
            WHERE {where}
            ORDER BY p.ticker, p.opened_at
            """,
            tuple(params),
        )
        rows = [dict(row) for row in cursor.fetchall()]

        eligible = []
        for row in rows:
            retro_status = row.get("retro_status")
            retro_pos_status = row.get("retro_position_status")

            if retro_status in ("pending", "running"):
                continue
            if retro_status == "completed" and retro_pos_status == "closed":
                continue

            eligible.append(row)

        return eligible
