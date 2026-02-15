"""Ticker Scheduler for automated analysis.

APScheduler-based scheduler that runs G-ANT pipeline per ticker at intervals.

Features:
- Per-ticker IntervalTrigger (every N days)
- Per-ticker threading.Lock (timeout=600s) to prevent concurrent execution
- Self-healing: Scans config + virtual_trade/tickers/ on start
- Full analysis cycle: load → propagate → report → portfolio → trade → reflect

Integration Flow:
1. Load trade state (TradeManager)
2. Run G-ANT pipeline (TradingAgentsGraph.propagate)
3. Store report (SummaryAgent + DB)
4. Portfolio decision (PortfolioAgent)
5. Execute trade (TradeManager)
6. Reflect if closed position → store to HybridMemory
7. Save state (TradeManager)
"""

import asyncio
import os
import logging
import threading
import time
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from tradingagents.errors import DataVendorError, DecisionParseError, AgentExecutionError
from tradingagents.runtime_context import set_schedule_context, reset_schedule_context

logger = logging.getLogger(__name__)

# P1-A: Global analysis queue (used by API routes and queue worker)
analysis_queue: Optional[asyncio.Queue] = None


class TickerScheduler:
    """APScheduler wrapper for ticker-based automated analysis."""

    def __init__(self, graph, config: Dict[str, Any]):
        """Initialize the ticker scheduler.

        Args:
            graph: TradingAgentsGraph instance
            config: Configuration dict (with database_path, schedules, etc.)
        """
        self.graph = graph
        self.config = config

        # APScheduler
        self.scheduler = BackgroundScheduler()

        # Per-ticker locks (to prevent concurrent execution)
        self._ticker_locks: Dict[str, threading.Lock] = {}

        # Per-ticker interval tracking
        self._ticker_intervals: Dict[str, int] = {}

        # Queue integration (set by API lifespan)
        self._analysis_queue: Optional[asyncio.Queue] = analysis_queue
        self._queue_loop: Optional[asyncio.AbstractEventLoop] = None

        # Requeue guard
        self._requeued_schedule_ids: set[int] = set()

        # FR-030: Initialize Database and components
        from tradingagents.storage import Database
        from tradingagents.virtual_trade import TradeManager, PortfolioAgent
        from tradingagents.agents.summary_agent import SummaryAgent

        # Initialize Database
        db_path = config.get("database_path", "memory/trading.db")
        self.db = Database(db_path)
        self.db.init_schema()

        # Initialize TradeManager (DB-based)
        self.trade_manager = TradeManager(db=self.db)

        # Initialize SummaryAgent (replaces ReportStore)
        self.summary_agent = SummaryAgent(llm=graph.quick_thinking_llm)

        # Initialize PortfolioAgent (DB-based)
        # P2-B: Pass hybrid_memory for RAG search
        self.portfolio_agent = PortfolioAgent(
            llm=graph.deep_thinking_llm,
            trade_manager=self.trade_manager,
            db=self.db,
            hybrid_memory=graph.memory
        )

        logger.info(f"TickerScheduler initialized (DB-based)")

    def set_queue(
        self,
        queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Attach the global analysis queue and its event loop.

        Args:
            queue: asyncio.Queue instance used by API worker
            loop: Event loop running the queue worker
        """
        self._analysis_queue = queue
        self._queue_loop = loop

    def _queue_item_ticker(self, item: Any) -> Optional[str]:
        if isinstance(item, dict):
            return item.get("ticker")
        if isinstance(item, str):
            return item
        return None

    def _queue_snapshot(self) -> List[str]:
        if not self._analysis_queue:
            return []
        try:
            pending = list(getattr(self._analysis_queue, "_queue", []))
        except Exception:
            return []

        tickers = []
        for item in pending:
            ticker = self._queue_item_ticker(item)
            if ticker:
                tickers.append(str(ticker))
        return tickers

    def _is_ticker_queued(self, ticker: str) -> bool:
        if not self._analysis_queue:
            return False
        try:
            pending = list(self._analysis_queue._queue)
            return any(self._queue_item_ticker(item) == ticker for item in pending)
        except Exception:
            return False

    def _enqueue_item(self, item: Dict[str, Any]) -> None:
        if not self._analysis_queue or not self._queue_loop:
            logger.error(
                f"Analysis queue not initialized; cannot enqueue {item.get('ticker')}"
            )
            return

        if not self._queue_loop.is_running():
            logger.error(
                f"Event loop not running; cannot enqueue {item.get('ticker')}"
            )
            return

        ticker = item.get("ticker")
        if ticker and self._is_ticker_queued(ticker):
            logger.info(f"{ticker} already queued; skipping enqueue")
            return

        asyncio.run_coroutine_threadsafe(
            self._analysis_queue.put(item), self._queue_loop
        )
        logger.info(
            "Queue enqueue: ticker=%s pending=%s",
            ticker,
            self._queue_snapshot(),
        )

    def enqueue_schedule(
        self,
        ticker: str,
        schedule_id: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[int]:
        """Create schedule/job and enqueue for analysis."""
        if self._is_ticker_queued(ticker):
            logger.info(f"{ticker} already queued; skipping enqueue")
            return None

        from tradingagents.storage import ScheduleRepository, ScheduleJobRepository

        schedule_repo = ScheduleRepository(self.db)
        schedule_job_repo = ScheduleJobRepository(self.db)

        if schedule_id is None:
            latest_cycle = schedule_repo.get_latest_cycle(ticker)
            current_cycle = latest_cycle + 1
            interval_days = self._ticker_intervals.get(ticker, 4)
            schedule_id = schedule_repo.create(
                ticker,
                current_cycle,
                interval_days=interval_days,
            )

        job_id = schedule_job_repo.create(
            schedule_id,
            "pending",
            error_type=error_type,
            error_message=error_message,
        )

        logger.info(
            "Schedule queued: ticker=%s schedule_id=%s job_id=%s",
            ticker,
            schedule_id,
            job_id,
        )

        self._enqueue_item(
            {
                "ticker": ticker,
                "schedule_id": schedule_id,
                "job_id": job_id,
            }
        )
        return schedule_id

    def _enqueue_ticker(self, ticker: str) -> None:
        """APScheduler hook: enqueue ticker for analysis."""
        self.enqueue_schedule(ticker)

    def add_ticker(
        self,
        ticker: str,
        interval_days: int = 4,
    ):
        """Add a ticker to the schedule.

        FR-030: Simplified - DB handles position state, no file initialization needed.

        Args:
            ticker: Ticker symbol (e.g., "NVDA")
            interval_days: Analysis interval in days (default 4)
        """
        # Create ticker lock if not exists
        if ticker not in self._ticker_locks:
            self._ticker_locks[ticker] = threading.Lock()

        # Track interval_days for schedule records
        self._ticker_intervals[ticker] = interval_days

        # Add job to scheduler
        job_id = f"ticker_{ticker}"

        # Check if job already exists
        existing_job = self.scheduler.get_job(job_id)
        if existing_job:
            logger.warning(f"Job {job_id} already exists, removing and re-adding")
            self.scheduler.remove_job(job_id)

        trigger = IntervalTrigger(days=interval_days)

        self.scheduler.add_job(
            func=self._enqueue_ticker,
            trigger=trigger,
            args=[ticker],
            id=job_id,
            name=f"Analysis for {ticker} (every {interval_days} days)",
            replace_existing=True,
        )

        logger.info(
            f"Added ticker {ticker} to schedule: every {interval_days} days"
        )

    def remove_ticker(self, ticker: str):
        """Remove a ticker from the schedule.

        Args:
            ticker: Ticker symbol
        """
        job_id = f"ticker_{ticker}"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed ticker {ticker} from schedule")
            self._ticker_intervals.pop(ticker, None)
        else:
            logger.warning(f"Ticker {ticker} not found in schedule")

    def start(self):
        """Start the scheduler and perform self-healing scan."""
        # Self-healing: Scan config + virtual_trade/tickers/
        self._self_heal()

        # Start scheduler
        self.scheduler.start()
        logger.info("TickerScheduler started")

    def stop(self):
        """Stop the scheduler immediately.

        Immediate shutdown (wait=False) is safe because:
        - Atomic writes (tmp + rename) ensure file integrity
        - Per-ticker locks prevent data corruption
        Args:
            wait: Whether to wait for running jobs to complete
        """
        self.scheduler.shutdown(wait=False)
        logger.info("TickerScheduler stopped")

    def is_running(self) -> bool:
        """Check if the scheduler is running.

        Returns:
            True if APScheduler is running
        """
        return self.scheduler.running

    def list_schedules(self) -> List[Dict[str, Any]]:
        """List active schedules.

        Returns:
            List of dicts with ticker, interval_days, next_run_time
        """
        jobs = self.scheduler.get_jobs()

        schedules = []
        for job in jobs:
            # Extract ticker from job.id ("ticker_NVDA" -> "NVDA")
            if job.id.startswith("ticker_"):
                ticker = job.id[len("ticker_"):]

                # Extract interval_days from trigger
                interval_days = None
                if hasattr(job.trigger, 'interval'):
                    interval_days = job.trigger.interval.days

                next_run_time = getattr(job, "next_run_time", None)
                if next_run_time is None:
                    next_run_time = getattr(job, "next_fire_time", None)
                if isinstance(next_run_time, datetime):
                    next_run_time = next_run_time.isoformat()

                schedules.append({
                    "ticker": ticker,
                    "interval_days": interval_days,
                    "next_run_time": next_run_time,
                })

        return schedules

    def _self_heal(self):
        """Self-healing: Scan config to restore schedules.

        FR-030: Simplified - only scans config, no file system scan needed.

        Scans:
        1. config["schedules"] (List[{ticker, interval_days, initial_capital}])
        """
        logger.info("Running self-heal scan...")

        # Scan config schedules
        config_schedules = self.config.get("schedules", [])
        for schedule in config_schedules:
            ticker = schedule.get("ticker")
            interval_days = schedule.get("interval_days", 4)

            if ticker:
                self.add_ticker(ticker, interval_days)

        logger.info("Self-heal scan complete")

    def _run_analysis_cycle(
        self,
        ticker: str,
        schedule_id: Optional[int] = None,
        schedule_job_id: Optional[int] = None,
    ):
        """Run full analysis cycle for a ticker.

        Flow:
        1. Acquire per-ticker lock (timeout=600s)
        2. Load trade state
        3. Get current price (yfinance)
        4. Run G-ANT pipeline (propagate)
        5. Store report
        6. Portfolio decision
        7. Execute trade (BUY/SELL/HOLD)
        8. Reflect if closed position
        9. Save trade state
        10. Release lock

        Retry: 1 retry on failure
        """
        lock = self._ticker_locks.get(ticker)
        if not lock:
            logger.error(f"No lock found for ticker {ticker}, skipping cycle")
            return

        # Try to acquire lock (timeout=600s)
        acquired = lock.acquire(timeout=600)
        if not acquired:
            logger.warning(
                f"Failed to acquire lock for {ticker} within 600s, "
                "skipping this cycle"
            )
            return

        try:
            from tradingagents.storage import ScheduleRepository, ScheduleJobRepository

            schedule_repo = ScheduleRepository(self.db)
            schedule_job_repo = ScheduleJobRepository(self.db)

            if schedule_id is None:
                latest_cycle = schedule_repo.get_latest_cycle(ticker)
                current_cycle = latest_cycle + 1
                interval_days = self._ticker_intervals.get(ticker, 4)
                schedule_id = schedule_repo.create(
                    ticker,
                    current_cycle,
                    interval_days=interval_days,
                )

            if schedule_job_id is None:
                schedule_job_id = schedule_job_repo.create(schedule_id, "running")
            else:
                schedule_job_repo.update_status(
                    schedule_job_id,
                    "running",
                    error_type=None,
                    error_message=None,
                    error_detail=None,
                )

            context_tokens = set_schedule_context(
                schedule_id,
                schedule_job_id,
                self._log_schedule_job,
            )
            try:
                # Run analysis cycle (P3-E: no retry)
                self._run_analysis_cycle_impl(
                    ticker,
                    schedule_id,
                    schedule_job_id,
                )
            finally:
                reset_schedule_context(context_tokens)

        except Exception as e:
            logger.error(f"Analysis cycle failed for {ticker}: {e}")

        finally:
            # Always release lock
            lock.release()

    def _run_analysis_cycle_impl(
        self,
        ticker: str,
        schedule_id: int,
        schedule_job_id: int,
    ):
        """Implementation of analysis cycle with DB transaction pattern.

        FR-030: Complete rewrite for SQLite-based storage.

        Flow (based on arch-be.md Section 5.1):
        1. G-ANT 분석 (12 agents) → final_state
        2. PA 판단 → trade_decision + pa_opinion
        3. SummaryAgent → 13 summaries
        4. 청산 확인 → (청산 시) Reflector 실행
        ── BEGIN TRANSACTION ──
        5. schedule INSERT/UPDATE
        6. trade INSERT (if any)
        7. report INSERT
        8. (청산 시) reflection INSERT + position UPDATE
        ── COMMIT ──
        """
        from tradingagents.storage import (
            ScheduleRepository,
            PositionRepository,
            TradeRepository,
            ReportRepository,
            ScheduleJobRepository,
        )

        logger.info(f"Starting analysis cycle for {ticker}")

        # Initialize repositories
        schedule_repo = ScheduleRepository(self.db)
        position_repo = PositionRepository(self.db)
        trade_repo = TradeRepository(self.db)
        report_repo = ReportRepository(self.db)
        schedule_job_repo = ScheduleJobRepository(self.db)

        # ===== LLM CALLS (outside transaction) =====

        # 1. Get or create active position
        active_position = position_repo.get_active(ticker)
        if not active_position:
            # Create new position if none exists
            position_id = position_repo.create(ticker)
            active_position = position_repo.get_by_id(position_id)
            logger.info(f"{ticker}: Created new position {position_id}")
        else:
            position_id = active_position["id"]

        # 3. Get current price (with retries)
        current_price = self._get_current_price(ticker, schedule_id)

        logger.info(f"{ticker}: Current price: ${current_price:.2f}")

        # 4. Get position summary
        position_summary = self.trade_manager.get_position_summary(ticker)

        try:
            # 5. Run G-ANT pipeline (12 agents, objective analysis)
            today = datetime.now().strftime("%Y-%m-%d")

            logger.info(f"{ticker}: Running G-ANT pipeline...")
            try:
                final_state, pipeline_decision = self.graph.propagate(
                    company_name=ticker,
                    trade_date=today,
                    current_position=""  # FR-021: No position injection to 12 agents
                )
            except (DecisionParseError, DataVendorError):
                raise
            except Exception as e:
                raise AgentExecutionError(f"{ticker}: pipeline failed") from e

            logger.info(f"{ticker}: Pipeline decision: {pipeline_decision}")

            # 6. Portfolio Agent decision (with position context)
            logger.info(f"{ticker}: Running portfolio agent...")

            # PA needs position info - build context
            pa_context = {
                "ticker": ticker,
                "position": active_position,
                "position_summary": position_summary,
                "current_price": current_price,
            }

            try:
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent",
                        "running",
                        "Portfolio Agent running",
                    )
                portfolio_decision = self.portfolio_agent.decide(
                    ticker=ticker,
                    pipeline_decision=pipeline_decision,
                    pipeline_state=final_state,
                    current_price=current_price,
                    context=pa_context  # Pass position context to PA
                )
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent",
                        "completed",
                        "Portfolio Agent completed",
                    )
            except DecisionParseError:
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent",
                        "error",
                        "Portfolio Agent decision parse failed",
                    )
                raise
            except Exception as e:
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent",
                        "error",
                        f"Portfolio Agent error: {e}",
                    )
                raise AgentExecutionError(f"{ticker}: portfolio agent failed") from e

            pa_opinion = portfolio_decision.get("rationale", "")
            action = portfolio_decision["action"]
            shares = portfolio_decision["shares"]

            logger.info(
                f"{ticker}: Portfolio decision: {action} "
                f"(shares={shares})"
            )

            # 7. SummaryAgent (generate 13 summaries)
            logger.info(f"{ticker}: Generating summaries...")
            summaries = self.summary_agent.summarize(final_state, pa_opinion)

            # 8. Prepare trade execution (defer DB writes to transaction)
            trade_executed = False
            trade_action = None
            trade_shares = 0
            trade_price = current_price
            sell_all = False

            if action == "BUY" and shares > 0:
                trade_executed = True
                trade_action = "BUY"
                trade_shares = shares
                logger.info(f"{ticker}: BUY planned - {shares} shares")

            elif action == "SELL" and shares > 0:
                total_shares = active_position["shares"]

                if shares >= total_shares:
                    sell_all = True
                    trade_shares = total_shares
                else:
                    trade_shares = shares

                trade_executed = True
                trade_action = "SELL"
                logger.info(
                    f"{ticker}: SELL planned - {trade_shares} shares"
                )

            is_closed = trade_action == "SELL" and sell_all
            trade_result = None

            # ===== BEGIN TRANSACTION =====
            logger.info(f"{ticker}: Starting DB transaction...")

            def transaction_operations(conn):
                nonlocal trade_result
                # 9. Update schedule status
                schedule_job_repo.update_status(
                    schedule_job_id,
                    "done",
                    error_type=None,
                    error_message=None,
                    error_detail=None,
                    commit=False,
                    conn=conn,
                )

                # 10. Insert report
                report_id = report_repo.create(
                    schedule_id=schedule_id,
                    position_id=position_id,
                    summaries=summaries,
                    commit=False,
                    conn=conn,
                )

                # 11. Execute trade + insert trade record
                if trade_executed and trade_action:
                    if trade_action == "BUY":
                        self.trade_manager.open_position(
                            ticker,
                            trade_shares,
                            current_price,
                            today,
                            commit=False,
                            conn=conn,
                        )
                    elif trade_action == "SELL":
                        if sell_all:
                            trade_result = self.trade_manager.close_all_positions(
                                ticker,
                                current_price,
                                today,
                                commit=False,
                                conn=conn,
                            )
                        else:
                            trade_result = self.trade_manager.close_positions(
                                ticker,
                                trade_shares,
                                current_price,
                                today,
                                commit=False,
                                conn=conn,
                            )

                    trade_repo.create(
                        position_id=position_id,
                        report_id=report_id,
                        action=trade_action,
                        shares=trade_shares,
                        price=trade_price,
                        commit=False,
                        conn=conn,
                    )

            # Execute transaction
            self.db.execute_in_transaction(transaction_operations)

            logger.info(f"{ticker}: Transaction committed")

            # 12. Reflect and store (outside SQL transaction)
            if is_closed:
                reflection_result = None
                reflection_metadata = {
                    "sector": None,
                    "industry": None,
                    "market": None,
                }
                try:
                    logger.info(f"{ticker}: Position closed, running reflection...")
                    reflection_result = self.graph.reflector.reflect_on_position(
                        position_id=position_id,
                        db=self.db,
                        ticker=ticker,
                    )
                    logger.info(f"{ticker}: Reflection complete")
                except Exception as e:
                    logger.error(f"{ticker}: Reflection failed: {e}")
                    reflection_result = None

                if reflection_result:
                    # FR-029: Fetch metadata for reflection tags
                    try:
                        import yfinance as yf
                        info = yf.Ticker(ticker).info
                        reflection_metadata["sector"] = info.get("sector")
                        reflection_metadata["industry"] = info.get("industry")
                        reflection_metadata["market"] = (
                            info.get("fullExchangeName") or info.get("exchange")
                        )
                        if info.get("quoteType") == "CRYPTOCURRENCY":
                            reflection_metadata["market"] = "Crypto"
                    except Exception:
                        pass

                    from tradingagents.storage import ReflectionRepository
                    reflection_repo = ReflectionRepository(self.db)
                    reflection_id = reflection_repo.create(
                        position_id=position_id,
                        reflection=reflection_result["reflection"],
                        key_lessons=reflection_result["key_lessons"],
                        outcome=reflection_result["outcome"],
                        return_pct=reflection_result["return_pct"],
                        market=reflection_metadata["market"],
                        sector=reflection_metadata["sector"],
                        industry=reflection_metadata["industry"],
                    )

                    # Store to HybridMemory (ChromaDB)
                    try:
                        metadata = {
                            "position_id": position_id,
                            "ticker": ticker,
                            "outcome": reflection_result["outcome"],
                            "return_pct": reflection_result["return_pct"],
                            "sector": reflection_metadata["sector"],
                            "industry": reflection_metadata["industry"],
                            "market": reflection_metadata["market"],
                        }
                        self.graph.memory.add_situations(
                            [(reflection_result["key_lessons"], reflection_result["reflection"])],
                            metadata=metadata,
                            reflection_id=reflection_id,
                            store_sqlite=False,
                        )
                        logger.info(f"{ticker}: Reflection stored to ChromaDB")
                    except Exception as e:
                        logger.warning(f"{ticker}: ChromaDB storage failed: {e}")

            logger.info(f"{ticker}: Analysis cycle complete")

        except DecisionParseError as e:
            schedule_job_repo.update_status(
                schedule_job_id,
                "failed",
                error_type="parse_failure",
                error_message=str(e)[:500],
                error_detail=e.raw_text or traceback.format_exc(),
            )
            self._requeue_schedule(schedule_id, ticker, "parse_failure")
            logger.error(f"{ticker}: Parse failure: {e}")
            raise
        except DataVendorError as e:
            schedule_job_repo.update_status(
                schedule_job_id,
                "failed",
                error_type="vendor_failure",
                error_message=str(e)[:500],
                error_detail=str(getattr(e, "details", None)) or traceback.format_exc(),
            )
            logger.error(f"{ticker}: Data vendor failure: {e}")
            raise
        except AgentExecutionError as e:
            schedule_job_repo.update_status(
                schedule_job_id,
                "failed",
                error_type="agent_failure",
                error_message=str(e)[:500],
                error_detail=traceback.format_exc(),
            )
            self._requeue_schedule(schedule_id, ticker, "agent_failure")
            logger.error(f"{ticker}: Agent failure: {e}")
            raise
        except Exception as e:
            schedule_job_repo.update_status(
                schedule_job_id,
                "failed",
                error_type="analysis_failure",
                error_message=str(e)[:500],
                error_detail=traceback.format_exc(),
            )
            logger.error(f"{ticker}: Analysis cycle failed: {e}")
            raise
        finally:
            pass

    def _log_schedule_job(
        self,
        schedule_id: int,
        error_type: str,
        error_message: str,
        error_detail: Optional[str] = None,
    ) -> None:
        from tradingagents.storage import ScheduleJobRepository

        try:
            repo = ScheduleJobRepository(self.db)
            repo.update_latest_by_schedule(
                schedule_id,
                error_type=error_type,
                error_message=error_message,
                error_detail=error_detail,
            )
        except Exception as e:
            logger.warning(f"Failed to log schedule_job: {e}")

    def _requeue_schedule(self, schedule_id: int, ticker: str, reason: str) -> bool:
        try:
            if schedule_id in self._requeued_schedule_ids:
                logger.info(
                    f"{ticker}: Requeue skipped (already requeued once)"
                )
                return False

            self._requeued_schedule_ids.add(schedule_id)
            self.enqueue_schedule(
                ticker,
                schedule_id=schedule_id,
                error_type="requeue",
                error_message=f"Requeued after {reason}",
            )
            logger.info(f"{ticker}: Requeued after {reason}")
            return True
        except Exception as e:
            logger.warning(f"{ticker}: Failed to requeue: {e}")
            return False

    def _get_current_price(
        self,
        ticker: str,
        schedule_id: int,
        retries: int = 2,
        retry_delay: int = 30,
    ) -> float:
        """Get current stock price using yfinance with retries.

        Args:
            ticker: Ticker symbol
            schedule_id: Schedule ID for error logging
            retries: Number of retries after initial failure
            retry_delay: Delay between retries in seconds

        Returns:
            Current price (close price of last trading day)

        Raises:
            DataVendorError: If all attempts fail
        """
        errors = []
        total_attempts = retries + 1

        for attempt in range(1, total_attempts + 1):
            try:
                import yfinance as yf

                ticker_obj = yf.Ticker(ticker)
                history = ticker_obj.history(period="1d")

                if history.empty:
                    raise ValueError("No price data returned")

                current_price = history["Close"].iloc[-1]
                return float(current_price)

            except Exception as e:
                error_msg = (
                    f"price vendor failed for {ticker} "
                    f"(attempt {attempt}/{total_attempts})"
                )
                errors.append({"attempt": attempt, "error": str(e)})
                self._log_schedule_job(
                    schedule_id,
                    "vendor_retry",
                    error_msg,
                    str(e),
                )
                logger.warning(f"{ticker}: {error_msg} - {e}")

                if attempt < total_attempts:
                    time.sleep(retry_delay)

        raise DataVendorError(
            f"Failed to fetch current price for {ticker}",
            details=errors,
        )


if __name__ == "__main__":
    print("TickerScheduler requires TradingAgentsGraph for testing.")
    print("See integration example in main.py or CLI.")
