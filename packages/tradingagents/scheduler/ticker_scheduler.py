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
import math
import threading
import time
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from tradingagents.errors import DataVendorError, DecisionParseError, AgentExecutionError
from tradingagents.forecast_lab.scheduled_sources import collect_scheduled_issues
from tradingagents.agents.utils.news_citations import cited_refs
from tradingagents.scheduler.news_evidence import trade_news_for_close
from tradingagents.runtime_context import set_schedule_context, reset_schedule_context
from tradingagents.scheduler.portfolio_pipeline import PortfolioPipeline

logger = logging.getLogger(__name__)

analysis_queue: Optional[asyncio.PriorityQueue] = None

PRIORITY_SCHEDULED = 0
PRIORITY_RETROSPECTIVE = 1
PRIORITY_RAG_VALIDATION = 2
PRIORITY_PORTFOLIO_DAILY = 3
PRIORITY_PORTFOLIO_WEEKLY = 4
_enqueue_seq: int = 0


class TickerScheduler:
    """APScheduler wrapper for ticker-based automated analysis."""

    def __init__(self, graph, config: Dict[str, Any]):
        self.graph = graph
        self.config = config

        self.scheduler = BackgroundScheduler()
        self._ticker_locks: Dict[str, threading.Lock] = {}

        self._analysis_queue: Optional[asyncio.PriorityQueue] = analysis_queue
        self._queue_loop: Optional[asyncio.AbstractEventLoop] = None
        self._requeued_job_ids: set[int] = set()
        self._portfolio_daily_enqueued_dates: set[str] = set()

        from tradingagents.storage import Database
        from tradingagents.virtual_trade import TradeManager, PortfolioAgent
        from tradingagents.agents.summary_agent import SummaryAgent

        db_path = config.get("database_path", "memory/trading.db")
        self.db = Database(db_path)
        self.db.init_schema()

        self.trade_manager = TradeManager(db=self.db)
        self.summary_agent = SummaryAgent(llm=graph.quick_thinking_llm)

        initial_capital = config.get("default_initial_capital", 1000.0)
        self.portfolio_agent = PortfolioAgent(
            llm=graph.deep_thinking_llm,
            trade_manager=self.trade_manager,
            db=self.db,
            hybrid_memory=graph.memory,
            initial_capital=initial_capital,
        )
        self.portfolio_pipeline = PortfolioPipeline(
            db=self.db,
            config=self.config,
            llm=graph.deep_thinking_llm,
            hybrid_memory=graph.memory,
        )

        logger.info("TickerScheduler initialized (DB-based)")

    # ── queue helpers ──

    def set_queue(self, queue: asyncio.PriorityQueue, loop: asyncio.AbstractEventLoop) -> None:
        self._analysis_queue = queue
        self._queue_loop = loop

    def _queue_item_ticker(self, item: Any) -> Optional[str]:
        if isinstance(item, tuple) and len(item) == 3:
            _, _, payload = item
            return self._queue_item_ticker(payload)
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

    def _enqueue_item(
        self, item: Dict[str, Any], priority: int = PRIORITY_SCHEDULED, skip_dedup: bool = False,
    ) -> None:
        global _enqueue_seq
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
        if not skip_dedup and ticker and self._is_ticker_queued(ticker):
            logger.info(f"{ticker} already queued; skipping enqueue")
            return

        _enqueue_seq += 1
        asyncio.run_coroutine_threadsafe(
            self._analysis_queue.put((priority, _enqueue_seq, item)),
            self._queue_loop,
        )
        logger.info(
            "Queue enqueue: ticker=%s priority=%s pending=%s",
            ticker,
            priority,
            self._queue_snapshot(),
        )

    # ── schedule creation ──

    def enqueue_schedule(
        self,
        ticker: str,
        schedule_job_id: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[int]:
        """Enqueue ticker for analysis.

        Job creation and cycle increment happen in _run_analysis_cycle,
        after skip checks pass, so that skipped runs don't inflate the cycle count.

        Returns schedule_job_id or None if already queued.
        """
        if self._is_ticker_queued(ticker):
            logger.info(f"{ticker} already queued; skipping enqueue")
            return None

        logger.info(
            "Schedule queued: ticker=%s job_id=%s",
            ticker,
            schedule_job_id,
        )

        self._enqueue_item(
            {
                "ticker": ticker,
                "schedule_job_id": schedule_job_id,
            }
        )
        return schedule_job_id

    def _enqueue_ticker(self, ticker: str) -> None:
        """APScheduler hook: enqueue ticker for analysis."""
        self.enqueue_schedule(ticker)

    # ── ticker management ──

    def add_ticker(self, ticker: str, interval_days: int = 1, market: str = "us"):
        if ticker not in self._ticker_locks:
            self._ticker_locks[ticker] = threading.Lock()

        job_id = f"ticker_{ticker}"
        existing_job = self.scheduler.get_job(job_id)
        if existing_job:
            logger.warning(f"Job {job_id} already exists, removing and re-adding")
            self.scheduler.remove_job(job_id)

        trigger = self._make_cron_trigger(market)

        self.scheduler.add_job(
            func=self._enqueue_ticker,
            trigger=trigger,
            args=[ticker],
            id=job_id,
            name=f"Analysis for {ticker} ({market})",
            replace_existing=True,
        )
        logger.info(f"Added ticker {ticker} to schedule: market={market}")

    @staticmethod
    def _make_cron_trigger(market: str) -> CronTrigger:
        """Build CronTrigger based on market timezone."""
        if market == "kr":
            return CronTrigger(hour=16, minute=30, timezone="Asia/Seoul")
        # us + crypto: ET 17:00 (1h after US close)
        return CronTrigger(hour=17, minute=0, timezone="US/Eastern")

    def remove_ticker(self, ticker: str):
        job_id = f"ticker_{ticker}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed ticker {ticker} from schedule")
        else:
            logger.warning(f"Ticker {ticker} not found in schedule")

    def start(self):
        self._self_heal()
        self._init_weekly_schedule()
        self.scheduler.add_job(
            self._evaluate_memory_outcomes,
            CronTrigger(hour=16, minute=10, timezone="Asia/Seoul"),
            id="rag_outcomes",
            name="Evaluate matured lesson decisions",
            next_run_time=datetime.now(ZoneInfo("Asia/Seoul")),
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("TickerScheduler started")
        import pytz
        kst = pytz.timezone("Asia/Seoul")
        for job in self.scheduler.get_jobs():
            nft = job.trigger.get_next_fire_time(None, datetime.now(job.trigger.timezone))
            nft_kst = nft.astimezone(kst) if nft else None
            logger.info(f"  Job '{job.id}': next={nft_kst:%Y-%m-%d %H:%M KST}" if nft_kst else f"  Job '{job.id}': next=None")

    def _evaluate_memory_outcomes(self):
        from tradingagents.rag_validator.outcome import evaluate_pending

        result = evaluate_pending(self.db, as_of=datetime.now(ZoneInfo("Asia/Seoul")))
        logger.info("Lesson outcome evaluation: %s", result)

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("TickerScheduler stopped")

    def is_running(self) -> bool:
        return self.scheduler.running

    def list_schedules(self) -> List[Dict[str, Any]]:
        import pytz
        kst = pytz.timezone("Asia/Seoul")
        jobs = self.scheduler.get_jobs()
        schedules = []
        for job in jobs:
            if job.id.startswith("ticker_"):
                ticker = job.id[len("ticker_"):]
                interval_days = None
                if hasattr(job.trigger, "interval"):
                    interval_days = job.trigger.interval.days

                next_run_time = None
                nft = job.trigger.get_next_fire_time(None, datetime.now(job.trigger.timezone))
                if nft:
                    next_run_time = nft.astimezone(kst).isoformat()

                schedules.append({
                    "ticker": ticker,
                    "interval_days": interval_days,
                    "next_run_time": next_run_time,
                })
        return schedules

    def _is_portfolio_enabled(self) -> bool:
        """포트폴리오 활성화 = DB에 active config 존재 (env 아님)."""
        try:
            from tradingagents.storage import PortfolioConfigRepository

            return PortfolioConfigRepository(self.db).get_active() is not None
        except Exception:
            return False

    def _today_kst_date(self) -> str:
        return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()

    @staticmethod
    def _as_kst_date(value: Any) -> str:
        if value is None:
            return ""
        kst = ZoneInfo("Asia/Seoul")
        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).strip()
            if not text:
                return ""
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                return text[:10]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=kst)
        else:
            dt = dt.astimezone(kst)
        return dt.date().isoformat()

    def _enqueue_portfolio_weekly(self) -> None:
        if not self._is_portfolio_enabled():
            return
        self._enqueue_item(
            {
                "type": "portfolio_weekly",
                "ticker": "__portfolio_weekly__",
            },
            priority=PRIORITY_PORTFOLIO_WEEKLY,
            skip_dedup=True,
        )

    def _init_weekly_schedule(self) -> None:
        if not self._is_portfolio_enabled():
            return
        job_id = "portfolio_weekly"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        self.scheduler.add_job(
            func=self._enqueue_portfolio_weekly,
            trigger=CronTrigger(day_of_week="sun", hour=12, minute=0, timezone="Asia/Seoul"),
            id=job_id,
            name="Portfolio weekly reflection",
            replace_existing=True,
        )
        logger.info("Added portfolio weekly schedule (Sun 12:00 KST)")

    def _on_all_tickers_complete(self) -> None:
        """Enqueue portfolio daily job when strict completion rule is satisfied."""
        if not self._is_portfolio_enabled():
            return

        from tradingagents.storage import (
            PortfolioConfigRepository,
            ScheduleConfigRepository,
            ScheduleJobRepository,
        )

        active_portfolio = PortfolioConfigRepository(self.db).get_active()
        if not active_portfolio:
            return

        config_repo = ScheduleConfigRepository(self.db)
        job_repo = ScheduleJobRepository(self.db)
        schedule_configs = config_repo.get_all()
        total_active = len(schedule_configs)
        if total_active == 0:
            return

        today = self._today_kst_date()
        done = skipped = failed = 0

        for cfg in schedule_configs:
            latest = job_repo.get_latest_by_config(int(cfg["id"]))
            if not latest:
                continue

            created_at = latest.get("created_at")
            created_date = self._as_kst_date(created_at)
            status = str(latest.get("status") or "").lower()

            if created_date == today:
                if status == "done":
                    done += 1
                elif status == "skipped":
                    skipped += 1
                elif status == "failed":
                    failed += 1
                continue

            # No today's job row: treat as completed if last_data_date already advanced to today.
            last_data_date = self._as_kst_date(cfg.get("last_data_date"))
            if last_data_date == today:
                skipped += 1

        logger.info(
            "Portfolio trigger check: total=%s done=%s skipped=%s failed=%s",
            total_active,
            done,
            skipped,
            failed,
        )

        if (done + skipped) == total_active and failed == 0:
            if today in self._portfolio_daily_enqueued_dates:
                return
            self._portfolio_daily_enqueued_dates.add(today)
            self._enqueue_item(
                {
                    "type": "portfolio_daily",
                    "ticker": "__portfolio_daily__",
                    "config_id": int(active_portfolio["id"]),
                    "decision_date": today,
                },
                priority=PRIORITY_PORTFOLIO_DAILY,
                skip_dedup=True,
            )
            logger.info("Enqueued portfolio_daily for date=%s", today)

    # ── self-heal ──

    def _self_heal(self):
        logger.info("Running self-heal scan...")

        from tradingagents.storage import ScheduleJobRepository

        job_repo = ScheduleJobRepository(self.db)

        config_schedules = self.config.get("schedules", [])
        for schedule in config_schedules:
            ticker = schedule.get("ticker")
            interval_days = schedule.get("interval_days", 4)
            if not ticker:
                continue

            latest_job = job_repo.get_latest_by_ticker(ticker)
            if latest_job and latest_job.get("status") in ("failed", "running"):
                if latest_job.get("status") == "running":
                    job_repo.update_status(
                        latest_job["id"],
                        "failed",
                        error_type="interrupted",
                        error_message="Marked failed after restart",
                        error_detail=None,
                    )
                    logger.info(
                        f"Self-heal: marked running job {latest_job['id']} as failed "
                        f"for {ticker}"
                    )
                logger.info(
                    f"Self-heal: re-queuing job {latest_job['id']} for {ticker}"
                )
                self.enqueue_schedule(ticker, schedule_job_id=latest_job["id"])

            from tradingagents.storage import ScheduleConfigRepository
            cfg = ScheduleConfigRepository(self.db).get_by_ticker(ticker)
            market = cfg.get("market", "us") if cfg else "us"
            self.add_ticker(ticker, interval_days, market=market)

        logger.info("Self-heal scan complete")

    # ── analysis cycle ──

    def _run_analysis_cycle(
        self,
        ticker: str,
        schedule_job_id: Optional[int] = None,
    ) -> bool:
        lock = self._ticker_locks.get(ticker)
        if not lock:
            logger.error(f"No lock found for ticker {ticker}, skipping cycle")
            return False

        acquired = lock.acquire(timeout=600)
        if not acquired:
            logger.warning(
                f"Failed to acquire lock for {ticker} within 600s, "
                "skipping this cycle"
            )
            return False

        retry_attempt = schedule_job_id in self._requeued_job_ids
        job_repo = None
        try:
            from tradingagents.storage import ScheduleConfigRepository, ScheduleJobRepository

            config_repo = ScheduleConfigRepository(self.db)
            job_repo = ScheduleJobRepository(self.db)

            cfg = config_repo.get_by_ticker(ticker)
            if not cfg:
                logger.error(f"No schedule_config for {ticker}")
                return False
            config_id = cfg["id"]
            if schedule_job_id is not None:
                latest = job_repo.get_latest_by_config(config_id)
                if not latest or latest["id"] != schedule_job_id or latest["status"] == "done":
                    logger.info("%s: Ignoring stale or completed job %s", ticker, schedule_job_id)
                    return False

            latest_market_date = self._get_latest_market_date(ticker)
            if latest_market_date is None:
                if schedule_job_id is not None:
                    job_repo.update_status(
                        schedule_job_id, "skipped",
                        error_type="no_data",
                        error_message="No market data available",
                    )
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "system", "skipped", "No market data available",
                    )
                logger.info(f"{ticker}: Skipped (no market data)")
                return False

            last_data_date = cfg.get("last_data_date")
            if hasattr(last_data_date, "isoformat"):
                last_data_date = last_data_date.isoformat()

            if last_data_date == latest_market_date:
                if schedule_job_id is not None:
                    job_repo.update_status(
                        schedule_job_id, "skipped",
                        error_type="no_update",
                        error_message=f"No new market data since {latest_market_date}",
                    )
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "system", "skipped",
                        f"No new market data since {latest_market_date}",
                    )
                logger.info(
                    f"{ticker}: Skipped (no new data since {latest_market_date})"
                )
                return False

            if schedule_job_id is None:
                def start_job(conn):
                    nonlocal schedule_job_id
                    cycle = config_repo.increment_cycle(ticker, commit=False, conn=conn)
                    schedule_job_id = job_repo.create(config_id, cycle, "running", commit=False, conn=conn)

                self.db.execute_in_transaction(start_job)
            else:
                job_repo.update_status(
                    schedule_job_id,
                    "running",
                    error_type=None,
                    error_message=None,
                    error_detail=None,
                )

            context_tokens = set_schedule_context(
                schedule_job_id,
                schedule_job_id,
                self._log_schedule_job,
            )
            try:
                self._run_analysis_cycle_impl(
                    ticker,
                    schedule_job_id,
                )
                return True
            finally:
                reset_schedule_context(context_tokens)

        except Exception as e:
            if schedule_job_id is not None and job_repo is not None:
                job_repo.fail_if_running(schedule_job_id, str(e)[:500], traceback.format_exc())
            logger.exception("Analysis cycle failed for %s", ticker)
            raise
        finally:
            if retry_attempt:
                self._requeued_job_ids.discard(schedule_job_id)
            try:
                self._on_all_tickers_complete()
            except Exception as e:
                logger.warning(f"Portfolio completion check failed: {e}")
            lock.release()

    def _run_analysis_cycle_impl(
        self,
        ticker: str,
        schedule_job_id: int,
    ):
        from tradingagents.storage import (
            ScheduleConfigRepository,
            PositionRepository,
            TradeRepository,
            ReportRepository,
            ScheduleJobRepository,
        )

        logger.info(f"Starting analysis cycle for {ticker}")

        config_repo = ScheduleConfigRepository(self.db)
        position_repo = PositionRepository(self.db)
        trade_repo = TradeRepository(self.db)
        report_repo = ReportRepository(self.db)
        job_repo = ScheduleJobRepository(self.db)

        cfg = config_repo.get_by_ticker(ticker) or {}
        ticker_currency = cfg.get("currency", "USD")
        ticker_initial_capital = float(cfg.get("initial_capital", 5000))

        quote_metadata = {}
        quote_requested_at = datetime.now(timezone.utc)
        raw_price, data_date = self._get_latest_close(ticker, schedule_job_id, quote_metadata=quote_metadata)
        current_price = round(raw_price, 2)
        trade_date = data_date

        collect_scheduled_issues(ticker, cfg.get("market", "us"))

        active_position = position_repo.get_active(ticker)
        position_id = active_position["id"] if active_position else None

        logger.info(
            f"{ticker}: Close price: {current_price:.2f} {ticker_currency} "
            f"(data date: {data_date})"
        )

        # --- Auto-liquidation check ---
        if active_position and active_position.get("shares", 0) > 0:
            avg_cost = float(active_position.get("avg_cost") or 0)
            if avg_cost > 0:
                return_pct = ((current_price - avg_cost) / avg_cost) * 100.0
                sl = active_position.get("stop_loss")
                tgt = active_position.get("target")
                sl_pct = ((sl - avg_cost) / avg_cost * 100.0) if sl else -30.0
                tgt_pct = ((tgt - avg_cost) / avg_cost * 100.0) if tgt else 30.0

                should_liquidate = return_pct <= sl_pct or return_pct >= tgt_pct
                if should_liquidate:
                    reason = "stop_loss" if return_pct <= sl_pct else "target"
                    logger.info(
                        f"{ticker}: Auto-liquidation triggered ({reason}): "
                        f"return={return_pct:.1f}% sl={sl_pct:.1f}% tgt={tgt_pct:.1f}%"
                    )

                    def auto_close_txn(conn):
                        self.trade_manager.close_all_positions(
                            ticker, current_price, trade_date,
                            commit=False, conn=conn,
                        )
                        quantity = float(active_position["shares"])
                        report_id = report_repo.create(
                            schedule_job_id, position_id, {
                                "decision_position": "SELL", "portfolio_action": "SELL",
                                "portfolio_shares": quantity,
                                "portfolio_rationale": f"Automatic liquidation: {reason}",
                            }, commit=False, conn=conn,
                        )
                        trade_repo.create(
                            position_id, report_id, "SELL", quantity, current_price,
                            ticker_currency, trade_date, commit=False, conn=conn,
                        )
                        config_repo.update_last_data_date(ticker, trade_date, commit=False, conn=conn)
                        job_repo.update_status(
                            schedule_job_id, "done",
                            error_type=None, error_message=None, error_detail=None,
                            commit=False, conn=conn,
                        )

                    self.db.execute_in_transaction(auto_close_txn)
                    logger.info(f"{ticker}: Auto-liquidation complete, running reflection...")

                    self._reflect_closed_position(ticker, position_id)
                    return

        position_summary = self.trade_manager.get_position_summary(ticker)

        try:
            logger.info(f"{ticker}: Collecting macro context...")
            from tradingagents.dataflows.macro_collector import collect_macro_context
            macro_ctx = collect_macro_context(ticker, cfg.get("market", "us"), trade_date)
            if macro_ctx:
                logger.info(f"{ticker}: Macro context collected ({len(macro_ctx)} chars)")

            logger.info(f"{ticker}: Running G-ANT pipeline...")
            try:
                news_evidence = trade_news_for_close(
                    ticker, cfg.get("market", "us"), trade_date, quote_metadata, quote_requested_at,
                )
                final_state, (pipeline_decision, pipeline_strategy) = self.graph.propagate(
                    company_name=ticker,
                    trade_date=trade_date,
                    current_position=position_summary,
                    macro_context=macro_ctx,
                    news_evidence=news_evidence,
                )
            except (DecisionParseError, DataVendorError):
                raise
            except Exception as e:
                raise AgentExecutionError(f"{ticker}: pipeline failed") from e

            logger.info(f"{ticker}: Pipeline decision: {pipeline_decision}")
            if pipeline_strategy:
                logger.info(f"{ticker}: Pipeline strategy: {pipeline_strategy}")

            logger.info(f"{ticker}: Running portfolio agent...")

            pa_context = {
                "ticker": ticker,
                "position": active_position,
                "position_summary": position_summary,
                "current_price": current_price,
                "currency": ticker_currency,
                "initial_capital": ticker_initial_capital,
                "market": cfg.get("market"),
            }

            try:
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent", "running", "Portfolio Agent running",
                    )
                portfolio_decision = self.portfolio_agent.decide(
                    ticker=ticker,
                    pipeline_decision=pipeline_decision,
                    pipeline_state=final_state,
                    current_price=current_price,
                    context=pa_context,
                    pipeline_strategy=pipeline_strategy,
                )
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent", "completed", "Portfolio Agent completed",
                    )
            except DecisionParseError:
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent", "error", "Portfolio Agent decision parse failed",
                    )
                raise
            except Exception as e:
                if self.graph.status_callback:
                    self.graph.status_callback(
                        "Portfolio Agent", "error", f"Portfolio Agent error: {e}",
                    )
                raise AgentExecutionError(f"{ticker}: portfolio agent failed") from e

            pa_opinion = portfolio_decision.get("rationale", "")
            action = portfolio_decision["action"]
            shares = float(portfolio_decision.get("shares", 0.0) or 0.0)
            shares = round(shares, 6)

            logger.info(f"{ticker}: Portfolio decision: {action} (shares={shares})")

            pa_strategy = portfolio_decision.get("strategy_update") or {}
            pa_sl = pa_strategy.get("stop_loss")
            pa_tgt = pa_strategy.get("target")
            if pa_sl is not None and pa_tgt is not None and pa_sl >= pa_tgt:
                logger.warning(
                    f"{ticker}: stop_loss ({pa_sl}) >= target ({pa_tgt}), "
                    "ignoring invalid PA strategy values"
                )
                pa_sl, pa_tgt = None, None

            logger.info(f"{ticker}: Generating summaries...")
            summaries = self.summary_agent.summarize(final_state, pa_opinion)
            if "news_analyst_cited" in final_state:
                analyst_cited = final_state["news_analyst_cited"]
                summaries["news_evidence"] = {
                    **news_evidence,
                    "analyst_cited": analyst_cited,
                    "decision_cited": cited_refs(final_state["final_trade_decision"], analyst_cited),
                }
            summaries["decision_position"] = pipeline_decision
            summaries["portfolio_action"] = action
            summaries["portfolio_shares"] = shares
            summaries["portfolio_rationale"] = pa_opinion
            if pipeline_strategy and "forecast_5s" in pipeline_strategy:
                forecast = pipeline_strategy["forecast_5s"]
                forecast["market_data_date"] = trade_date
                forecast["judge_model"] = self.config.get("deep_think_llm")
            summaries["pipeline_strategy"] = pipeline_strategy
            summaries["rag_used"] = portfolio_decision.get("rag_used", False)
            summaries["rag_docs"] = portfolio_decision.get("rag_docs")

            trade_executed = False
            trade_action = None
            trade_shares = 0
            trade_price = round(current_price, 2)
            sell_all = False

            if action == "BUY" and shares > 0:
                trade_executed = True
                trade_action = "BUY"
                trade_shares = shares
                logger.info(f"{ticker}: BUY planned - {shares} shares")

            elif action == "SELL" and shares > 0:
                if not active_position:
                    logger.info(
                        f"{ticker}: SELL requested but no position; skipping trade"
                    )
                else:
                    total_shares = float(active_position["shares"])

                    if shares >= total_shares - 1e-8:
                        sell_all = True
                        trade_shares = total_shares
                    else:
                        trade_shares = shares

                    trade_executed = True
                    trade_action = "SELL"
                    logger.info(f"{ticker}: SELL planned - {trade_shares} shares")

            is_closed = trade_action == "SELL" and sell_all
            trade_result = None

            logger.info(f"{ticker}: Starting DB transaction...")

            def transaction_operations(conn):
                nonlocal trade_result, position_id
                job_repo.update_status(
                    schedule_job_id,
                    "done",
                    error_type=None,
                    error_message=None,
                    error_detail=None,
                    commit=False,
                    conn=conn,
                )

                if trade_executed and trade_action == "BUY":
                    state = self.trade_manager.open_position(
                        ticker, trade_shares, current_price, trade_date,
                        currency=ticker_currency,
                        commit=False, conn=conn,
                    )
                    position = state.get("position") if state else None
                    if position:
                        position_id = position.get("id")

                if position_id and not is_closed and (pa_sl is not None or pa_tgt is not None):
                    position_repo.update_stop_loss_target(position_id, pa_sl, pa_tgt, commit=False, conn=conn)
                config_repo.update_last_data_date(ticker, trade_date, commit=False, conn=conn)
                report_id = report_repo.create(
                    schedule_job_id=schedule_job_id,
                    position_id=position_id,
                    summaries=summaries,
                    commit=False,
                    conn=conn,
                )

                if trade_executed and trade_action:
                    if trade_action == "SELL":
                        if sell_all:
                            trade_result = self.trade_manager.close_all_positions(
                                ticker, current_price, trade_date,
                                commit=False, conn=conn,
                            )
                        else:
                            trade_result = self.trade_manager.close_positions(
                                ticker, trade_shares, current_price, trade_date,
                                commit=False, conn=conn,
                            )

                    if position_id:
                        trade_repo.create(
                            position_id=position_id,
                            report_id=report_id,
                            action=trade_action,
                            shares=trade_shares,
                            price=trade_price,
                            currency=ticker_currency,
                            executed_at=trade_date,
                            commit=False,
                            conn=conn,
                        )
                    else:
                        raise RuntimeError(f"{ticker}: Executed trade has no position id")

            self.db.execute_in_transaction(transaction_operations)
            logger.info(f"{ticker}: Transaction committed")

            if is_closed:
                self._reflect_closed_position(ticker, position_id)

            logger.info(f"{ticker}: Analysis cycle complete")

        except DecisionParseError as e:
            job_repo.update_status(
                schedule_job_id, "failed",
                error_type="parse_failure",
                error_message=str(e)[:500],
                error_detail=e.raw_text or traceback.format_exc(),
            )
            self._requeue_job(schedule_job_id, ticker, "parse_failure")
            logger.error(f"{ticker}: Parse failure: {e}")
            raise
        except DataVendorError as e:
            job_repo.update_status(
                schedule_job_id, "failed",
                error_type="vendor_failure",
                error_message=str(e)[:500],
                error_detail=str(getattr(e, "details", None)) or traceback.format_exc(),
            )
            logger.error(f"{ticker}: Data vendor failure: {e}")
            raise
        except AgentExecutionError as e:
            job_repo.update_status(
                schedule_job_id, "failed",
                error_type="agent_failure",
                error_message=str(e)[:500],
                error_detail=traceback.format_exc(),
            )
            self._requeue_job(schedule_job_id, ticker, "agent_failure")
            logger.error(f"{ticker}: Agent failure: {e}")
            raise
        except Exception as e:
            job_repo.update_status(
                schedule_job_id, "failed",
                error_type="analysis_failure",
                error_message=str(e)[:500],
                error_detail=traceback.format_exc(),
            )
            logger.error(f"{ticker}: Analysis cycle failed: {e}")
            raise

    # ── helpers ──

    def _reflect_closed_position(self, ticker, position_id):
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

            try:
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
            except Exception:
                logger.exception("%s: Failed to store post-trade reflection", ticker)
                return

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

    def _log_schedule_job(
        self,
        job_id: int,
        error_type: str,
        error_message: str,
        error_detail: Optional[str] = None,
    ) -> None:
        from tradingagents.storage import ScheduleJobRepository

        try:
            repo = ScheduleJobRepository(self.db)
            repo.update_status(
                job_id,
                "running",
                error_type=error_type,
                error_message=error_message,
                error_detail=error_detail,
            )
        except Exception as e:
            logger.warning(f"Failed to log schedule_job: {e}")

    def _requeue_job(self, job_id: int, ticker: str, reason: str) -> bool:
        try:
            if job_id in self._requeued_job_ids:
                logger.info(f"{ticker}: Requeue skipped (already requeued once)")
                return False

            self._requeued_job_ids.add(job_id)
            self.enqueue_schedule(
                ticker,
                schedule_job_id=job_id,
                error_type="requeue",
                error_message=f"Requeued after {reason}",
            )
            logger.info(f"{ticker}: Requeued after {reason}")
            return True
        except Exception as e:
            logger.warning(f"{ticker}: Failed to requeue: {e}")
            return False

    def _get_latest_close(
        self,
        ticker: str,
        schedule_job_id: int,
        retries: int = 2,
        retry_delay: int = 30,
        *,
        quote_metadata: Optional[dict] = None,
    ) -> tuple[float, str]:
        """Return (close_price, data_date_iso) from yfinance.

        Always uses the latest available bar. The scheduler runs after
        market close (CronTrigger), so the latest bar is the confirmed
        daily close. The previous 'today guard' that skipped to the
        prior day has been removed — it caused all scheduled analyses
        to use stale (T-1) prices.
        """
        errors = []
        total_attempts = retries + 1

        for attempt in range(1, total_attempts + 1):
            try:
                import yfinance as yf

                ticker_obj = yf.Ticker(ticker)
                history = ticker_obj.history(period="5d", interval="1d")

                if history.empty:
                    raise ValueError("No price data returned")

                price = float(history["Close"].iloc[-1])

                latest_index = history.index[-1]
                verified_date = True
                try:
                    # Keep market-local calendar date (do NOT convert timezone).
                    # tz_convert(None) can shift KRX timestamps (+09:00) to previous day.
                    data_date = latest_index.tz_localize(None).date()
                except Exception:
                    try:
                        data_date = latest_index.date()
                    except Exception:
                        data_date = datetime.now().date()
                        verified_date = False

                if not math.isfinite(price) or price <= 0:
                    raise ValueError("Close price must be positive and finite")
                if quote_metadata is not None and verified_date:
                    # Use the metadata from this daily response. history_metadata may fetch a different chart.
                    chart = getattr(getattr(ticker_obj, "_price_history", None), "_history_metadata", None)
                    if isinstance(chart, dict):
                        quote_metadata.update({k: chart.get(k) for k in (
                            "symbol", "instrumentType", "currency", "exchangeName", "exchangeTimezoneName",
                        )})
                return price, data_date.isoformat()

            except Exception as e:
                error_msg = (
                    f"price vendor failed for {ticker} "
                    f"(attempt {attempt}/{total_attempts})"
                )
                errors.append({"attempt": attempt, "error": str(e)})
                self._log_schedule_job(
                    schedule_job_id, "vendor_retry", error_msg, str(e),
                )
                logger.warning(f"{ticker}: {error_msg} - {e}")

                if attempt < total_attempts:
                    time.sleep(retry_delay)

        raise DataVendorError(
            f"Failed to fetch current price for {ticker}",
            details=errors,
        )

    def _get_latest_market_date(self, ticker: str) -> Optional[str]:
        try:
            import yfinance as yf

            ticker_obj = yf.Ticker(ticker)
            history = ticker_obj.history(period="7d")
            if history.empty:
                return None

            latest = history.index.max()
            if getattr(latest, "tzinfo", None) is not None:
                latest = latest.tz_localize(None)
            return latest.date().isoformat()
        except Exception as e:
            logger.warning(f"{ticker}: Failed to fetch latest market date: {e}")
            return None
