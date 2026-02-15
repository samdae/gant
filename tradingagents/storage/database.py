"""Postgres database connection management and schema initialization.

This module provides:
- Connection management with per-thread connections
- Schema initialization (tables + indexes + FTS)
- Transaction support
"""

import logging
import os
import threading
from typing import Callable, Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class Database:
    """Postgres connection manager with schema initialization."""

    def __init__(self, db_url: str):
        """Initialize database connection.

        Args:
            db_url: Postgres connection URL
        """
        if not db_url:
            raise RuntimeError("Database URL is required")

        self.db_url = self._normalize_db_url(db_url)
        self.direct_url = self._normalize_db_url(os.getenv("SUPABASE_DIRECT_URL", ""))
        self._connections = []
        self._connections_lock = threading.Lock()
        self._local = threading.local()

        # Initialize primary connection
        self.conn = self._create_connection()
        logger.info("Database initialized")

    def _normalize_db_url(self, db_url: str) -> str:
        try:
            parts = urlsplit(db_url)
            query = parse_qsl(parts.query, keep_blank_values=True)
            filtered = [(k, v) for k, v in query if k.lower() != "pgbouncer"]
            if len(filtered) != len(query):
                db_url = urlunsplit(
                    (parts.scheme, parts.netloc, parts.path, urlencode(filtered), parts.fragment)
                )
                logger.info("Removed unsupported query param 'pgbouncer' from DB URL")
        except Exception:
            pass
        return db_url

    def _create_connection(self) -> psycopg.Connection:
        connection = psycopg.connect(
            self.db_url,
            row_factory=dict_row,
            connect_timeout=5,
        )
        connection.autocommit = False

        with self._connections_lock:
            self._connections.append(connection)

        return connection

    def init_schema(self) -> None:
        """Initialize database schema.

        Creates all tables if they don't exist. Idempotent (safe to call multiple times).
        """
        logger.info("Initializing database schema...")

        ddl_conn = self.conn
        ddl_conn_created = False
        if self.direct_url:
            try:
                ddl_conn = psycopg.connect(
                    self.direct_url,
                    row_factory=dict_row,
                    connect_timeout=5,
                )
                ddl_conn.autocommit = True
                ddl_conn_created = True
                logger.info("Using SUPABASE_DIRECT_URL for schema init")
            except Exception as exc:
                logger.warning(f"Failed to use SUPABASE_DIRECT_URL: {exc}")
                ddl_conn = self.conn

        schema_sql = """
        CREATE TABLE IF NOT EXISTS schedules (
            id              BIGSERIAL PRIMARY KEY,
            ticker          TEXT    NOT NULL,
            interval_days   INTEGER NOT NULL DEFAULT 4,
            scheduled_cycle INTEGER NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedules_ticker ON schedules(ticker);

        CREATE TABLE IF NOT EXISTS schedule_configs (
            id            BIGSERIAL PRIMARY KEY,
            ticker        TEXT    NOT NULL UNIQUE,
            interval_days INTEGER NOT NULL DEFAULT 4,
            created_at    TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_configs_ticker ON schedule_configs(ticker);

        CREATE TABLE IF NOT EXISTS positions (
            id          BIGSERIAL PRIMARY KEY,
            ticker      TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'active',
            shares      INTEGER NOT NULL DEFAULT 0,
            avg_cost    DOUBLE PRECISION,
            return_pct  DOUBLE PRECISION,
            opened_at   TIMESTAMPTZ NOT NULL,
            closed_at   TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_positions_ticker_status ON positions(ticker, status);

        CREATE TABLE IF NOT EXISTS reports (
            id                                BIGSERIAL PRIMARY KEY,
            schedule_id                       BIGINT NOT NULL REFERENCES schedules(id),
            position_id                       BIGINT REFERENCES positions(id),
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
            created_at                        TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reports_schedule ON reports(schedule_id);
        CREATE INDEX IF NOT EXISTS idx_reports_position ON reports(position_id);

        CREATE TABLE IF NOT EXISTS trades (
            id          BIGSERIAL PRIMARY KEY,
            position_id BIGINT NOT NULL REFERENCES positions(id),
            report_id   BIGINT NOT NULL REFERENCES reports(id),
            action      TEXT    NOT NULL,
            shares      INTEGER NOT NULL,
            price       DOUBLE PRECISION NOT NULL,
            executed_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trades_position ON trades(position_id);
        CREATE INDEX IF NOT EXISTS idx_trades_report ON trades(report_id);

        CREATE TABLE IF NOT EXISTS reflections (
            id          BIGSERIAL PRIMARY KEY,
            position_id BIGINT NOT NULL REFERENCES positions(id),
            reflection  TEXT    NOT NULL,
            key_lessons TEXT,
            outcome     TEXT,
            return_pct  DOUBLE PRECISION,
            market      TEXT,
            sector      TEXT,
            industry    TEXT,
            created_at  TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reflections_position ON reflections(position_id);

        CREATE TABLE IF NOT EXISTS schedule_jobs (
            id            BIGSERIAL PRIMARY KEY,
            schedule_id   BIGINT NOT NULL REFERENCES schedules(id),
            status        TEXT    NOT NULL,
            error_type    TEXT,
            error_message TEXT,
            error_detail  TEXT,
            created_at    TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_jobs_schedule ON schedule_jobs(schedule_id);

        CREATE TABLE IF NOT EXISTS schedule_job_events (
            id              BIGSERIAL PRIMARY KEY,
            schedule_job_id BIGINT REFERENCES schedule_jobs(id),
            schedule_id     BIGINT REFERENCES schedules(id),
            ticker          TEXT,
            agent           TEXT,
            status          TEXT,
            message         TEXT,
            step            INTEGER,
            phase           TEXT,
            created_at      TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_job_events_job ON schedule_job_events(schedule_job_id);
        CREATE INDEX IF NOT EXISTS idx_schedule_job_events_schedule ON schedule_job_events(schedule_id);
        CREATE INDEX IF NOT EXISTS idx_schedule_job_events_ticker ON schedule_job_events(ticker);
        CREATE INDEX IF NOT EXISTS idx_schedule_job_events_created_at ON schedule_job_events(created_at);

        CREATE INDEX IF NOT EXISTS idx_reflections_search
            ON reflections
            USING GIN (to_tsvector('simple', coalesce(reflection, '') || ' ' || coalesce(key_lessons, '')));
        """

        for statement in (s.strip() for s in schema_sql.split(";")):
            if not statement:
                continue
            ddl_conn.execute(statement)
        if ddl_conn is self.conn:
            self.conn.commit()
        if ddl_conn_created:
            ddl_conn.close()

        self._ensure_column("schedules", "interval_days", "INTEGER NOT NULL DEFAULT 4")
        self._ensure_column("reflections", "market", "TEXT")
        self._ensure_column("reflections", "sector", "TEXT")
        self._ensure_column("reflections", "industry", "TEXT")

        logger.info("Schema initialization complete")

    def get_connection(self) -> psycopg.Connection:
        """Get the database connection.

        Returns:
            psycopg connection object
        """
        connection = getattr(self._local, "conn", None)
        if connection is None or getattr(connection, "closed", False):
            connection = self._create_connection()
            self._local.conn = connection
            return connection

        try:
            connection.execute("SELECT 1")
        except Exception:
            try:
                connection.close()
            except Exception:
                pass
            connection = self._create_connection()
            self._local.conn = connection

        return connection

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        """Add a column if missing (safe for legacy DBs)."""
        try:
            self.conn.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"
            )
            self.conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to ensure column {table}.{column}: {exc}")

    def execute_in_transaction(
        self, operations: Callable[[psycopg.Connection], None]
    ) -> None:
        """Execute operations in a single transaction.

        Args:
            operations: Callable that takes connection and performs operations
        """
        connection: Optional[psycopg.Connection] = None
        try:
            connection = self.get_connection()
            operations(connection)
            connection.commit()
        except Exception as exc:
            if connection:
                connection.rollback()
            logger.error(f"Transaction failed, rolled back: {exc}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        with self._connections_lock:
            for connection in self._connections:
                try:
                    connection.close()
                except Exception:
                    pass
            self._connections = []
        logger.info("Database connections closed")
