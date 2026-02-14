"""SQLite database connection management and schema initialization.

This module provides:
- Connection management with WAL mode for concurrent read/write
- Schema initialization (tables + FTS5 + triggers)
- Transaction support
"""

import os
import sqlite3
import logging
from typing import Callable, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """SQLite connection manager with schema initialization."""

    def __init__(self, db_path: str = "memory/trading.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure parent directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Initialize connection
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        # Enable WAL mode for concurrent read/write
        self.conn.execute("PRAGMA journal_mode=WAL")

        # Enable foreign key constraints
        self.conn.execute("PRAGMA foreign_keys=ON")

        # Set busy timeout (5 seconds)
        self.conn.execute("PRAGMA busy_timeout=5000")

        logger.info(f"Database initialized at {db_path}")

    def init_schema(self) -> None:
        """Initialize database schema (tables + FTS5 + triggers).

        Creates all tables if they don't exist. Idempotent (safe to call multiple times).
        """
        logger.info("Initializing database schema...")

        # DDL from proposal_v3.md and arch-be.md Section 2
        schema_sql = """
        -- ① schedules: 분석 실행 단위
        CREATE TABLE IF NOT EXISTS schedules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT    NOT NULL,
            interval_days   INTEGER NOT NULL DEFAULT 4,
            scheduled_cycle INTEGER NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'pending',
            error_message   TEXT,
            created_at      TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedules_ticker ON schedules(ticker);

        -- ② positions: 매매 사이클 (진입 → 청산)
        CREATE TABLE IF NOT EXISTS positions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'active',
            shares      INTEGER NOT NULL DEFAULT 0,
            avg_cost    REAL,
            return_pct  REAL,
            opened_at   TEXT    NOT NULL,
            closed_at   TEXT,
            created_at  TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_positions_ticker_status ON positions(ticker, status);

        -- ③ reports: 에이전트별 요약 (스케줄마다 1건)
        CREATE TABLE IF NOT EXISTS reports (
            id                                INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id                       INTEGER NOT NULL REFERENCES schedules(id),
            position_id                       INTEGER REFERENCES positions(id),
            market_report                     TEXT,
            fundamentals_report               TEXT,
            bull_history                      TEXT,
            bear_history                      TEXT,
            investment_debate_judge_decision  TEXT,
            aggressive_history                TEXT,
            conservative_history              TEXT,
            neutral_history                   TEXT,
            trader_investment_judge_decision  TEXT,
            trader_investment_decision        TEXT,
            investment_plan                   TEXT,
            final_trade_decision              TEXT,
            pa_opinion                        TEXT,
            created_at                        TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reports_schedule ON reports(schedule_id);
        CREATE INDEX IF NOT EXISTS idx_reports_position ON reports(position_id);

        -- ④ trades: 개별 BUY/SELL 액션
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER NOT NULL REFERENCES positions(id),
            report_id   INTEGER NOT NULL REFERENCES reports(id),
            action      TEXT    NOT NULL,
            shares      INTEGER NOT NULL,
            price       REAL    NOT NULL,
            executed_at TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trades_position ON trades(position_id);
        CREATE INDEX IF NOT EXISTS idx_trades_report ON trades(report_id);

        -- ⑤ reflections: 청산 시 반성에이전트 산출물
        CREATE TABLE IF NOT EXISTS reflections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER NOT NULL REFERENCES positions(id),
            reflection  TEXT    NOT NULL,
            key_lessons TEXT,
            outcome     TEXT,
            return_pct  REAL,
            market      TEXT,
            sector      TEXT,
            industry    TEXT,
            created_at  TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reflections_position ON reflections(position_id);

        -- ⑥ schedule_jobs: 에러/재시도 이력
        CREATE TABLE IF NOT EXISTS schedule_jobs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id   INTEGER NOT NULL REFERENCES schedules(id),
            error_type    TEXT    NOT NULL,
            error_message TEXT    NOT NULL,
            error_detail  TEXT,
            created_at    TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_jobs_schedule ON schedule_jobs(schedule_id);
        """

        # Execute schema creation
        self.conn.executescript(schema_sql)
        self.conn.commit()

        # Ensure new columns exist on legacy databases
        self._ensure_column("schedules", "interval_days", "INTEGER NOT NULL DEFAULT 4")
        self._ensure_column("reflections", "market", "TEXT")
        self._ensure_column("reflections", "sector", "TEXT")
        self._ensure_column("reflections", "industry", "TEXT")

        # FTS5 table creation (separate for better error handling)
        try:
            # Check if FTS5 table exists
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='reflections_fts'"
            )
            if not cursor.fetchone():
                # Create FTS5 table
                self.conn.execute("""
                    CREATE VIRTUAL TABLE reflections_fts USING fts5(
                        reflection,
                        key_lessons,
                        content='reflections',
                        content_rowid='id'
                    )
                """)
                logger.info("Created FTS5 table: reflections_fts")

            # Check if trigger exists
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name='reflections_ai'"
            )
            if not cursor.fetchone():
                # Create FTS5 sync trigger
                self.conn.execute("""
                    CREATE TRIGGER reflections_ai AFTER INSERT ON reflections BEGIN
                        INSERT INTO reflections_fts(rowid, reflection, key_lessons)
                        VALUES (new.id, new.reflection, new.key_lessons);
                    END
                """)
                logger.info("Created FTS5 sync trigger: reflections_ai")

            self.conn.commit()

        except Exception as e:
            logger.warning(f"Failed to create FTS5 table/trigger: {e}")
            # Continue without FTS5 (graceful degradation)

        logger.info("Schema initialization complete")

    def get_connection(self) -> sqlite3.Connection:
        """Get the database connection.

        Returns:
            SQLite connection object
        """
        return self.conn

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        """Add a column if missing (safe for legacy DBs)."""
        try:
            cursor = self.conn.execute(f"PRAGMA table_info({table})")
            existing = {row["name"] for row in cursor.fetchall()}
            if column not in existing:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
                )
                self.conn.commit()
                logger.info(f"Added column {table}.{column}")
        except Exception as e:
            logger.warning(f"Failed to ensure column {table}.{column}: {e}")

    def execute_in_transaction(self, operations: Callable[[sqlite3.Connection], None]) -> None:
        """Execute operations in a single transaction.

        Args:
            operations: Callable that takes connection and performs operations
        """
        try:
            operations(self.conn)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Transaction failed, rolled back: {e}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    # Test database initialization
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        db_path = os.path.join(temp_dir, "test_trading.db")
        db = Database(db_path)

        # Initialize schema
        db.init_schema()

        # Test connection
        conn = db.get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Created tables: {tables}")

        # Test WAL mode
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        print(f"Journal mode: {mode}")

        # Test foreign keys
        cursor = conn.execute("PRAGMA foreign_keys")
        fk_enabled = cursor.fetchone()[0]
        print(f"Foreign keys enabled: {fk_enabled == 1}")

        print("\n✅ Database initialization test passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")
