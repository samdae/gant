"""Schedule configuration repository for persistent schedules."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)

# Ticker suffix → (currency, initial_capital, market)
_TICKER_DEFAULTS = {
    ".KS": ("KRW", 5_000_000.0, "kr"),
    ".KQ": ("KRW", 5_000_000.0, "kr"),
}
_USD_DEFAULTS = ("USD", 5_000.0, "us")


def detect_ticker_defaults(ticker: str) -> tuple[str, float, str]:
    """Return (currency, initial_capital, market) based on ticker suffix."""
    upper = ticker.upper()
    for suffix, defaults in _TICKER_DEFAULTS.items():
        if upper.endswith(suffix):
            return defaults
    return _USD_DEFAULTS


class ScheduleConfigRepository:
    """Repository for schedule_configs table CRUD operations."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        ticker: str,
        interval_days: int,
        display_name: str = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        currency, initial_capital, market = detect_ticker_defaults(ticker)
        created_at = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO schedule_configs
                (ticker, interval_days, currency, initial_capital, market,
                 display_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (ticker, interval_days, currency, initial_capital, market,
             display_name, created_at),
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
        display_name: str = None,
        commit: bool = True,
        conn=None,
    ) -> int:
        currency, initial_capital, market = detect_ticker_defaults(ticker)
        created_at = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            INSERT INTO schedule_configs
                (ticker, interval_days, currency, initial_capital, market,
                 display_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(ticker)
            DO UPDATE SET interval_days = excluded.interval_days,
                          display_name = COALESCE(excluded.display_name,
                                                  schedule_configs.display_name)
            """,
            (ticker, interval_days, currency, initial_capital, market,
             display_name, created_at),
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

    # ── cycle management (replaces ScheduleRepository) ──

    def increment_cycle(
        self,
        ticker: str,
        commit: bool = True,
        conn=None,
    ) -> int:
        """Atomically increment current_cycle and return the new value."""
        connection = conn or self.db.get_connection()
        row = connection.execute(
            """
            UPDATE schedule_configs
            SET current_cycle = current_cycle + 1
            WHERE ticker = %s
            RETURNING current_cycle
            """,
            (ticker,),
        ).fetchone()
        if commit:
            connection.commit()
        if row is None:
            raise RuntimeError(f"schedule_config not found for {ticker}")
        return int(row["current_cycle"])

    def get_current_cycle(self, ticker: str) -> int:
        row = self.db.get_connection().execute(
            "SELECT current_cycle FROM schedule_configs WHERE ticker = %s",
            (ticker,),
        ).fetchone()
        return int(row["current_cycle"]) if row else 0

    # ── queries ──

    def get_all(self) -> List[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, ticker, interval_days, current_cycle, currency,
                   initial_capital, market, display_name, last_data_date,
                   created_at
            FROM schedule_configs
            ORDER BY created_at ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, ticker, interval_days, current_cycle, currency,
                   initial_capital, market, display_name, last_data_date,
                   created_at
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

    def update_display_name(
        self,
        ticker: str,
        display_name: str,
        commit: bool = True,
        conn=None,
    ) -> None:
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE schedule_configs
            SET display_name = %s
            WHERE ticker = %s
            """,
            (display_name, ticker),
        )
        if commit:
            connection.commit()

    def get_all_display_names(self) -> dict:
        """Return {ticker: display_name} map for all tickers with a display_name."""
        cursor = self.db.get_connection().execute(
            """
            SELECT ticker, display_name
            FROM schedule_configs
            WHERE display_name IS NOT NULL
            """
        )
        return {row["ticker"]: row["display_name"] for row in cursor.fetchall()}

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
