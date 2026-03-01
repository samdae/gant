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
        CREATE TABLE IF NOT EXISTS schedule_configs (
            id              BIGSERIAL PRIMARY KEY,
            ticker          TEXT    NOT NULL UNIQUE,
            interval_days   INTEGER NOT NULL DEFAULT 1,
            current_cycle   INTEGER NOT NULL DEFAULT 0,
            currency        TEXT    NOT NULL DEFAULT 'USD',
            initial_capital DOUBLE PRECISION NOT NULL DEFAULT 5000,
            market          TEXT    NOT NULL DEFAULT 'us',
            display_name    TEXT,
            last_data_date  DATE,
            created_at      TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_configs_ticker ON schedule_configs(ticker);

        CREATE TABLE IF NOT EXISTS schedule_jobs (
            id                 BIGSERIAL PRIMARY KEY,
            schedule_config_id BIGINT  NOT NULL REFERENCES schedule_configs(id),
            scheduled_cycle    INTEGER NOT NULL,
            status             TEXT    NOT NULL,
            error_type         TEXT,
            error_message      TEXT,
            error_detail       TEXT,
            created_at         TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_jobs_config ON schedule_jobs(schedule_config_id);

        CREATE TABLE IF NOT EXISTS positions (
            id          BIGSERIAL PRIMARY KEY,
            ticker      TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'active',
            shares      DOUBLE PRECISION NOT NULL DEFAULT 0,
            avg_cost    DOUBLE PRECISION,
            currency    TEXT    NOT NULL DEFAULT 'USD',
            stop_loss   DOUBLE PRECISION,
            target      DOUBLE PRECISION,
            return_pct  DOUBLE PRECISION,
            opened_at   TIMESTAMPTZ NOT NULL,
            closed_at   TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_positions_ticker_status ON positions(ticker, status);

        CREATE TABLE IF NOT EXISTS reports (
            id                                BIGSERIAL PRIMARY KEY,
            schedule_job_id                   BIGINT NOT NULL REFERENCES schedule_jobs(id),
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
            decision_position                 TEXT,
            portfolio_action                  TEXT,
            portfolio_shares                  DOUBLE PRECISION,
            portfolio_rationale               TEXT,
            pa_opinion                        TEXT,
            pipeline_strategy                 TEXT,
            rag_used                          BOOLEAN NOT NULL DEFAULT FALSE,
            rag_docs                          JSONB,
            created_at                        TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reports_job ON reports(schedule_job_id);
        CREATE INDEX IF NOT EXISTS idx_reports_position ON reports(position_id);

        CREATE TABLE IF NOT EXISTS trades (
            id          BIGSERIAL PRIMARY KEY,
            position_id BIGINT NOT NULL REFERENCES positions(id),
            report_id   BIGINT NOT NULL REFERENCES reports(id),
            action      TEXT    NOT NULL,
            shares      DOUBLE PRECISION NOT NULL,
            price       DOUBLE PRECISION NOT NULL,
            currency    TEXT    NOT NULL DEFAULT 'USD',
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
            usefulness_score DOUBLE PRECISION NOT NULL DEFAULT 50,
            created_at  TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reflections_position ON reflections(position_id);

        CREATE TABLE IF NOT EXISTS schedule_job_events (
            id              BIGSERIAL PRIMARY KEY,
            schedule_job_id BIGINT REFERENCES schedule_jobs(id),
            ticker          TEXT,
            agent           TEXT,
            status          TEXT,
            message         TEXT,
            step            INTEGER,
            phase           TEXT,
            created_at      TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_job_events_job ON schedule_job_events(schedule_job_id);
        CREATE INDEX IF NOT EXISTS idx_schedule_job_events_ticker ON schedule_job_events(ticker);
        CREATE INDEX IF NOT EXISTS idx_schedule_job_events_created_at ON schedule_job_events(created_at);

        CREATE INDEX IF NOT EXISTS idx_reflections_search
            ON reflections
            USING GIN (to_tsvector('simple', coalesce(reflection, '') || ' ' || coalesce(key_lessons, '')));

        CREATE TABLE IF NOT EXISTS retrospective_analyses (
            id                  BIGSERIAL PRIMARY KEY,
            position_id         BIGINT    NOT NULL UNIQUE REFERENCES positions(id),
            ticker              TEXT      NOT NULL,
            position_sequence   INTEGER   NOT NULL,
            position_status     TEXT      NOT NULL,
            status              TEXT      NOT NULL DEFAULT 'pending',
            analysis_content    TEXT,
            analysis_count      INTEGER   NOT NULL DEFAULT 1,
            position_open_date  TIMESTAMPTZ,
            position_close_date TIMESTAMPTZ,
            analysis_accuracy   INTEGER,
            rag_contribution    INTEGER,
            error_message       TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(ticker, position_sequence)
        );
        CREATE INDEX IF NOT EXISTS idx_retro_ticker ON retrospective_analyses(ticker);
        CREATE INDEX IF NOT EXISTS idx_retro_status ON retrospective_analyses(status);

        CREATE TABLE IF NOT EXISTS rag_validation_results (
            id                BIGSERIAL PRIMARY KEY,
            retrospective_id  BIGINT NOT NULL REFERENCES retrospective_analyses(id),
            reflection_id     BIGINT NOT NULL REFERENCES reflections(id),
            verdict           TEXT NOT NULL,
            justification     TEXT,
            score_delta       INTEGER NOT NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(retrospective_id, reflection_id)
        );
        CREATE INDEX IF NOT EXISTS idx_rag_validation_retro
            ON rag_validation_results(retrospective_id);

        CREATE TABLE IF NOT EXISTS portfolio_configs (
            id               BIGSERIAL PRIMARY KEY,
            name             TEXT      NOT NULL DEFAULT 'default',
            initial_capital  DOUBLE PRECISION NOT NULL DEFAULT 100000000,
            total_fund       DOUBLE PRECISION NOT NULL DEFAULT 100000000,
            available_cash   DOUBLE PRECISION NOT NULL DEFAULT 100000000,
            base_currency    TEXT      NOT NULL DEFAULT 'KRW',
            fee_enabled      BOOLEAN   NOT NULL DEFAULT TRUE,
            us_fee_rate      DOUBLE PRECISION NOT NULL DEFAULT 0.001,
            kr_buy_fee_rate  DOUBLE PRECISION NOT NULL DEFAULT 0.0025,
            kr_sell_fee_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0025,
            kr_sell_tax_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0018,
            crypto_fee_rate  DOUBLE PRECISION NOT NULL DEFAULT 0.001,
            status           TEXT      NOT NULL DEFAULT 'active',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS portfolio_decisions (
            id                      BIGSERIAL PRIMARY KEY,
            portfolio_config_id     BIGINT    NOT NULL REFERENCES portfolio_configs(id),
            decision_date           DATE      NOT NULL,
            briefing_summary        JSONB,
            allocation_plan         JSONB     NOT NULL,
            rationale               TEXT,
            total_fund_snapshot     DOUBLE PRECISION NOT NULL,
            available_cash_snapshot DOUBLE PRECISION NOT NULL,
            exchange_rate_snapshot  DOUBLE PRECISION,
            status                  TEXT      NOT NULL DEFAULT 'pending',
            error_message           TEXT,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_portfolio_decisions_config
            ON portfolio_decisions(portfolio_config_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_decisions_date
            ON portfolio_decisions(portfolio_config_id, decision_date);

        CREATE TABLE IF NOT EXISTS portfolio_trades (
            id                    BIGSERIAL PRIMARY KEY,
            portfolio_decision_id BIGINT    NOT NULL REFERENCES portfolio_decisions(id),
            ticker                TEXT      NOT NULL,
            action                TEXT      NOT NULL,
            shares                DOUBLE PRECISION NOT NULL DEFAULT 0,
            price                 DOUBLE PRECISION NOT NULL,
            currency              TEXT      NOT NULL DEFAULT 'USD',
            exchange_rate         DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            fee_rate              DOUBLE PRECISION NOT NULL DEFAULT 0,
            fee_amount            DOUBLE PRECISION NOT NULL DEFAULT 0,
            amount_local          DOUBLE PRECISION NOT NULL DEFAULT 0,
            amount_krw            DOUBLE PRECISION NOT NULL DEFAULT 0,
            executed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_portfolio_trades_decision
            ON portfolio_trades(portfolio_decision_id);
        CREATE INDEX IF NOT EXISTS idx_portfolio_trades_ticker
            ON portfolio_trades(ticker);

        CREATE TABLE IF NOT EXISTS portfolio_holdings (
            id                  BIGSERIAL PRIMARY KEY,
            portfolio_config_id BIGINT    NOT NULL REFERENCES portfolio_configs(id),
            snapshot_date       DATE      NOT NULL,
            ticker              TEXT      NOT NULL,
            shares              DOUBLE PRECISION NOT NULL DEFAULT 0,
            avg_cost            DOUBLE PRECISION NOT NULL DEFAULT 0,
            currency            TEXT      NOT NULL DEFAULT 'USD',
            current_value_krw   DOUBLE PRECISION NOT NULL DEFAULT 0,
            allocation_pct      DOUBLE PRECISION NOT NULL DEFAULT 0,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_holdings_unique
            ON portfolio_holdings(portfolio_config_id, ticker, snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_snapshot_date
            ON portfolio_holdings(snapshot_date);

        CREATE TABLE IF NOT EXISTS portfolio_reflections (
            id                  BIGSERIAL PRIMARY KEY,
            portfolio_config_id BIGINT    NOT NULL REFERENCES portfolio_configs(id),
            week_start_date     DATE      NOT NULL,
            week_end_date       DATE      NOT NULL,
            reflection_content  TEXT,
            allocation_accuracy INTEGER,
            total_return_pct    DOUBLE PRECISION,
            key_lessons         TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_portfolio_reflections_config
            ON portfolio_reflections(portfolio_config_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_reflections_week
            ON portfolio_reflections(portfolio_config_id, week_start_date);
        """

        for statement in (s.strip() for s in schema_sql.split(";")):
            if not statement:
                continue
            ddl_conn.execute(statement)
        if ddl_conn is self.conn:
            self.conn.commit()
        if ddl_conn_created:
            ddl_conn.close()

        self._ensure_schedule_event_unique_index()
        self._ensure_column("reports", "rag_used", "BOOLEAN NOT NULL DEFAULT FALSE")
        self._ensure_column("reports", "rag_docs", "JSONB")
        self._ensure_column("reflections", "usefulness_score", "DOUBLE PRECISION NOT NULL DEFAULT 50")
        self._ensure_column("retrospective_analyses", "analysis_accuracy", "INTEGER")
        self._ensure_column("retrospective_analyses", "rag_contribution", "INTEGER")

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
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _ensure_column_type(self, table: str, column: str, data_type: str) -> None:
        try:
            row = self.conn.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                (table, column),
            ).fetchone()
            if not row or not row.get("data_type"):
                return
            if str(row["data_type"]).lower() == data_type.lower():
                return

            self.conn.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {data_type} "
                f"USING {column}::{data_type}"
            )
            self.conn.commit()
        except Exception as exc:
            logger.warning(
                f"Failed to ensure column type {table}.{column} -> {data_type}: {exc}"
            )

    def _ensure_schedule_event_unique_index(self) -> None:
        dedupe_sql = """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY schedule_job_id, agent
                           ORDER BY created_at DESC, id DESC
                       ) AS rn
                FROM schedule_job_events
                WHERE schedule_job_id IS NOT NULL AND agent IS NOT NULL
            )
            DELETE FROM schedule_job_events
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """

        try:
            self.conn.execute(dedupe_sql)
            self.conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_job_events_unique
                    ON schedule_job_events(schedule_job_id, agent)
                """
            )
            self.conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to ensure schedule_event unique index: {exc}")
            try:
                self.conn.rollback()
            except Exception:
                pass

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
