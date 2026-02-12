"""Ticker Scheduler for automated analysis.

APScheduler-based scheduler that runs G-ANT pipeline per ticker at intervals.

Features:
- Per-ticker IntervalTrigger (every N days)
- Per-ticker threading.Lock (timeout=600s) to prevent concurrent execution
- Self-healing: Scans config + virtual_trade/tickers/ on start
- Simple retry: 1 retry on failure
- Full analysis cycle: load → propagate → report → portfolio → trade → reflect

Integration Flow:
1. Load trade state (TradeManager)
2. Run G-ANT pipeline (TradingAgentsGraph.propagate)
3. Store report (ReportStore)
4. Portfolio decision (PortfolioAgent)
5. Execute trade (TradeManager)
6. Reflect if closed position (TradingAgentsGraph.reflect_and_remember)
7. Save state (TradeManager)
"""

import os
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class TickerScheduler:
    """APScheduler wrapper for ticker-based automated analysis."""

    def __init__(self, graph, config: Dict[str, Any]):
        """Initialize the ticker scheduler.

        Args:
            graph: TradingAgentsGraph instance
            config: Configuration dict (with virtual_trade_dir, schedules, etc.)
        """
        self.graph = graph
        self.config = config

        # APScheduler
        self.scheduler = BackgroundScheduler()

        # Per-ticker locks (to prevent concurrent execution)
        self._ticker_locks: Dict[str, threading.Lock] = {}

        # Import virtual_trade components lazily (avoid circular imports)
        from tradingagents.virtual_trade import (
            TradeManager,
            ReportStore,
            PortfolioAgent
        )

        # Initialize virtual trade components
        trade_dir = config.get(
            "virtual_trade_dir",
            os.path.join(os.path.dirname(config["project_dir"]), "virtual_trade/tickers")
        )

        self.trade_manager = TradeManager(base_dir=trade_dir)
        self.report_store = ReportStore(base_dir=trade_dir)
        self.portfolio_agent = PortfolioAgent(
            llm=graph.deep_thinking_llm,
            trade_manager=self.trade_manager,
            report_store=self.report_store
        )

        logger.info(f"TickerScheduler initialized with trade_dir: {trade_dir}")

    def add_ticker(
        self,
        ticker: str,
        interval_days: int = 4,
        initial_capital: float = 1000.0
    ):
        """Add a ticker to the schedule.

        Args:
            ticker: Ticker symbol (e.g., "NVDA")
            interval_days: Analysis interval in days (default 4)
            initial_capital: Initial capital for new tickers (default 1000.0)
        """
        # Create ticker lock if not exists
        if ticker not in self._ticker_locks:
            self._ticker_locks[ticker] = threading.Lock()

        # Initialize trade state if not exists
        trade_state = self.trade_manager.load(ticker)
        if trade_state["initial_capital"] != initial_capital:
            # Update initial capital if different
            trade_state["initial_capital"] = initial_capital
            if not trade_state["positions"] and trade_state["status"] == "open":
                trade_state["cash"] = initial_capital
            self.trade_manager._cache[ticker] = trade_state
            self.trade_manager.save(ticker)

        # Add job to scheduler
        job_id = f"ticker_{ticker}"

        # Check if job already exists
        existing_job = self.scheduler.get_job(job_id)
        if existing_job:
            logger.warning(f"Job {job_id} already exists, removing and re-adding")
            self.scheduler.remove_job(job_id)

        trigger = IntervalTrigger(days=interval_days)

        self.scheduler.add_job(
            func=self._run_analysis_cycle,
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
        """
        self.scheduler.shutdown(wait=False)
        logger.info("TickerScheduler stopped")

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

                schedules.append({
                    "ticker": ticker,
                    "interval_days": interval_days,
                    "next_run_time": job.next_run_time,
                })

        return schedules

    def _self_heal(self):
        """Self-healing: Scan config and virtual_trade/tickers/ to restore schedules.

        Scans:
        1. config["schedules"] (List[{ticker, interval_days, initial_capital}])
        2. virtual_trade/tickers/ directory (existing trade.json files)
        """
        logger.info("Running self-heal scan...")

        # Scan config schedules
        config_schedules = self.config.get("schedules", [])
        for schedule in config_schedules:
            ticker = schedule.get("ticker")
            interval_days = schedule.get("interval_days", 4)
            initial_capital = schedule.get("initial_capital", 1000.0)

            if ticker:
                self.add_ticker(ticker, interval_days, initial_capital)

        # Scan virtual_trade/tickers/ directory
        trade_dir = self.trade_manager.base_dir
        if os.path.exists(trade_dir):
            for ticker_name in os.listdir(trade_dir):
                ticker_path = os.path.join(trade_dir, ticker_name)
                if os.path.isdir(ticker_path):
                    trade_json = os.path.join(ticker_path, "trade.json")
                    if os.path.exists(trade_json):
                        # Check if already scheduled
                        job_id = f"ticker_{ticker_name}"
                        if not self.scheduler.get_job(job_id):
                            # Add with default interval
                            logger.info(
                                f"Self-heal: Found existing trade for {ticker_name}, "
                                "adding to schedule with default interval (4 days)"
                            )
                            self.add_ticker(ticker_name, interval_days=4)

        logger.info("Self-heal scan complete")

    def _run_analysis_cycle(self, ticker: str):
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
            # Run analysis cycle
            self._run_analysis_cycle_impl(ticker)

        except Exception as e:
            logger.error(f"Analysis cycle failed for {ticker}: {e}")
            # Retry once
            logger.info(f"Retrying analysis cycle for {ticker}...")
            try:
                self._run_analysis_cycle_impl(ticker)
            except Exception as retry_e:
                logger.error(f"Retry failed for {ticker}: {retry_e}")

        finally:
            # Always release lock
            lock.release()

    def _run_analysis_cycle_impl(self, ticker: str):
        """Implementation of analysis cycle (called by _run_analysis_cycle)."""

        logger.info(f"Starting analysis cycle for {ticker}")

        # 1. Load trade state
        trade_state = self.trade_manager.load(ticker)
        logger.info(
            f"{ticker}: Loaded trade state - "
            f"cash=${trade_state['cash']:.2f}, "
            f"positions={len(trade_state['positions'])}"
        )

        # 2. Get current price (yfinance)
        current_price = self._get_current_price(ticker)
        if current_price is None:
            logger.error(
                f"{ticker}: Failed to fetch current price, skipping cycle"
            )
            return

        logger.info(f"{ticker}: Current price: ${current_price:.2f}")

        # 3. Get position summary
        position_summary = self.trade_manager.get_position_summary(ticker)

        # 4. Run G-ANT pipeline (propagate)
        today = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"{ticker}: Running G-ANT pipeline...")
        final_state, pipeline_decision = self.graph.propagate(
            company_name=ticker,
            trade_date=today,
            # Pass current_position when FR-017 is implemented
        )

        logger.info(f"{ticker}: Pipeline decision: {pipeline_decision}")

        # 5. Store report
        analysis_no = self.report_store.append(
            ticker=ticker,
            date=today,
            decision=pipeline_decision,
            strategy_summary=final_state.get("investment_plan", "")[:200],
            has_memory=self.graph._last_had_memory,
            state_summary={
                "market_report_excerpt": final_state.get("market_report", "")[:500],
                "final_decision_excerpt": final_state.get("final_trade_decision", "")[:500],
            }
        )

        logger.info(f"{ticker}: Stored report (analysis #{analysis_no})")

        # 6. Portfolio decision
        logger.info(f"{ticker}: Running portfolio agent...")
        portfolio_decision = self.portfolio_agent.decide(
            ticker=ticker,
            pipeline_decision=pipeline_decision,
            pipeline_state=final_state,
            current_price=current_price
        )

        logger.info(
            f"{ticker}: Portfolio decision: {portfolio_decision['action']} "
            f"(shares={portfolio_decision['shares']})"
        )

        # 7. Execute trade
        action = portfolio_decision["action"]
        rationale = portfolio_decision["rationale"]

        if action == "BUY":
            shares = portfolio_decision["shares"]
            if shares > 0:
                try:
                    self.trade_manager.open_position(
                        ticker, shares, current_price, today
                    )
                    self.trade_manager.append_history(
                        ticker, today, analysis_no, action,
                        f"Bought {shares} shares @ ${current_price:.2f}",
                        rationale
                    )
                    logger.info(f"{ticker}: BUY executed - {shares} shares")
                except ValueError as e:
                    logger.warning(f"{ticker}: BUY failed: {e}")
                    self.trade_manager.append_history(
                        ticker, today, analysis_no, "HOLD",
                        f"BUY attempt failed: {e}",
                        rationale
                    )

        elif action == "SELL":
            close_result = self.trade_manager.close_all_positions(
                ticker, current_price, today
            )
            self.trade_manager.append_history(
                ticker, today, analysis_no, action,
                f"Sold all positions @ ${current_price:.2f}",
                rationale
            )
            logger.info(
                f"{ticker}: SELL executed - "
                f"return {close_result['realized_return_pct']:.2f}%"
            )

            # 8. Reflect on closed position
            logger.info(f"{ticker}: Running reflection on closed position...")
            structured_context = {
                "ticker": ticker,
                "return_pct": close_result["realized_return_pct"],
                "holding_days": None,  # Calculate if needed
                "analysis_count": analysis_no,
                "has_memory": self.graph._last_had_memory,
                "schema_version": 1,
            }
            self.graph.reflect_and_remember(structured_context)
            logger.info(f"{ticker}: Reflection complete")

        elif action == "HOLD":
            self.trade_manager.append_history(
                ticker, today, analysis_no, action,
                "Maintaining current position",
                rationale
            )
            logger.info(f"{ticker}: HOLD - no trade executed")

        elif action == "MODIFY":
            # Update strategy parameters
            trade_state["strategy"].update(portfolio_decision["strategy_update"])
            self.trade_manager.append_history(
                ticker, today, analysis_no, action,
                "Modified strategy parameters",
                rationale
            )
            logger.info(f"{ticker}: MODIFY - strategy updated")

        # 9. Save trade state
        self.trade_manager.save(ticker)
        logger.info(f"{ticker}: Analysis cycle complete")

    def _get_current_price(self, ticker: str) -> Optional[float]:
        """Get current stock price using yfinance.

        Args:
            ticker: Ticker symbol

        Returns:
            Current price (close price of last trading day) or None if failed
        """
        try:
            import yfinance as yf

            ticker_obj = yf.Ticker(ticker)
            history = ticker_obj.history(period="1d")

            if history.empty:
                logger.warning(f"No price data returned for {ticker}")
                return None

            current_price = history["Close"].iloc[-1]
            return float(current_price)

        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return None


if __name__ == "__main__":
    print("TickerScheduler requires TradingAgentsGraph for testing.")
    print("See integration example in main.py or CLI.")
