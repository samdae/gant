"""Portfolio daily/weekly orchestration pipeline."""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.agents.briefing_agent import BriefingAgent
from tradingagents.graph.portfolio_reflection import PortfolioReflector
from tradingagents.storage import (
    PortfolioConfigRepository,
    PortfolioDecisionRepository,
    PortfolioHoldingRepository,
    PortfolioReflectionRepository,
    PortfolioTradeRepository,
)
from tradingagents.virtual_trade.exchange_rate import ExchangeRateService
from tradingagents.virtual_trade.fee_calculator import FeeCalculator
from tradingagents.virtual_trade.portfolio_manager_agent import PortfolioManagerAgent

logger = logging.getLogger(__name__)


class PortfolioPipeline:
    """Run portfolio mode daily and weekly jobs."""

    def __init__(
        self,
        db,
        config: Dict[str, Any],
        llm,
        hybrid_memory=None,
    ):
        self.db = db
        self.config = config
        self.hybrid_memory = hybrid_memory

        self.config_repo = PortfolioConfigRepository(db)
        self.decision_repo = PortfolioDecisionRepository(db)
        self.trade_repo = PortfolioTradeRepository(db)
        self.holding_repo = PortfolioHoldingRepository(db)
        self.reflection_repo = PortfolioReflectionRepository(db)

        self.briefing_agent = BriefingAgent(llm)
        self.pm_agent = PortfolioManagerAgent(llm, hybrid_memory=hybrid_memory, retry_budget=1)
        self.fee_calculator = FeeCalculator()
        self.exchange_rate_service = ExchangeRateService()
        self.reflector = PortfolioReflector(llm, db, hybrid_memory=hybrid_memory)

        self.snapshot_retention_days = int(os.getenv("PORTFOLIO_SNAPSHOT_RETENTION_DAYS", "14"))

    @staticmethod
    def _today_kst() -> datetime:
        try:
            import pytz

            return datetime.now(pytz.timezone("Asia/Seoul"))
        except Exception:
            return datetime.now()

    @staticmethod
    def _ticker_currency_market(ticker: str) -> Tuple[str, str]:
        tk = str(ticker).upper()
        if tk.endswith(".KS") or tk.endswith(".KQ"):
            return "KRW", "kr"
        if tk.endswith("-USD"):
            return "USD", "crypto"
        return "USD", "us"

    @staticmethod
    def _to_krw(amount: float, currency: str, exchange_rate: float) -> float:
        if str(currency).upper() == "KRW":
            return float(amount)
        return float(amount) * float(exchange_rate)

    @staticmethod
    def _to_base(amount: float, currency: str, base_currency: str, exchange_rate: float) -> float:
        amount = float(amount)
        currency = str(currency).upper()
        base = str(base_currency).upper()
        if currency == base:
            return amount
        if base == "KRW" and currency == "USD":
            return amount * float(exchange_rate)
        if base == "USD" and currency == "KRW":
            fx = float(exchange_rate) if float(exchange_rate) > 0 else 1.0
            return amount / fx
        return amount

    def _fetch_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        tickers = sorted({str(t).upper() for t in tickers if t})
        if not tickers:
            return {}
        try:
            import yfinance as yf

            data = yf.download(
                tickers=tickers,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                group_by="ticker",
            )
        except Exception as exc:
            logger.warning("Portfolio price fetch failed: %s", exc)
            return {}

        if data is None or data.empty:
            return {}

        prices: Dict[str, float] = {}
        multi = len(tickers) > 1
        for ticker in tickers:
            try:
                close_series = data[ticker]["Close"] if multi else data["Close"]
                price = float(close_series.iloc[-1])
                if price > 0:
                    prices[ticker] = price
            except Exception:
                continue
        return prices

    def _get_active_config(self, config_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if config_id:
            cfg = self.config_repo.get_by_id(int(config_id))
            if cfg and cfg.get("status") == "active":
                return cfg
            return None
        return self.config_repo.get_active()

    def _load_today_reports(self, kst_date: str) -> List[Dict[str, Any]]:
        rows = self.db.get_connection().execute(
            """
            SELECT DISTINCT ON (sc.ticker)
                   sc.ticker,
                   r.id AS report_id,
                   r.market_report,
                   r.final_trade_decision,
                   r.decision_position,
                   r.portfolio_action,
                   r.portfolio_shares,
                   r.pa_opinion,
                   r.created_at
            FROM reports r
            JOIN schedule_jobs sj ON r.schedule_job_id = sj.id
            JOIN schedule_configs sc ON sj.schedule_config_id = sc.id
            WHERE DATE(r.created_at AT TIME ZONE 'Asia/Seoul') = %s
            ORDER BY sc.ticker, r.id DESC
            """,
            (kst_date,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _load_today_skipped_tickers(self, kst_date: str) -> List[str]:
        """Return tickers skipped today because market data was not updated."""
        rows = self.db.get_connection().execute(
            """
            SELECT sc.ticker,
                   sc.last_data_date,
                   sj.status AS latest_status,
                   sj.created_at AS latest_created_at
            FROM schedule_configs sc
            LEFT JOIN LATERAL (
                SELECT status, created_at
                FROM schedule_jobs
                WHERE schedule_config_id = sc.id
                ORDER BY created_at DESC
                LIMIT 1
            ) sj ON TRUE
            ORDER BY sc.ticker
            """
        ).fetchall()

        skipped: List[str] = []
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            if not ticker:
                continue

            latest_status = str(row.get("latest_status") or "").lower()
            latest_created_at = row.get("latest_created_at")
            latest_created_date = ""
            if hasattr(latest_created_at, "date"):
                latest_created_date = latest_created_at.date().isoformat()
            elif latest_created_at:
                latest_created_date = str(latest_created_at)[:10]

            if latest_created_date == kst_date and latest_status == "skipped":
                skipped.append(ticker)
                continue

            # No today's job row but last_data_date already moved to today => stale-data skip.
            last_data_date = row.get("last_data_date")
            if hasattr(last_data_date, "isoformat"):
                last_data_date = last_data_date.isoformat()
            if str(last_data_date or "")[:10] == kst_date and latest_created_date != kst_date:
                skipped.append(ticker)

        return skipped

    def _load_latest_holdings_state(self, config_id: int) -> Dict[str, Dict[str, Any]]:
        state: Dict[str, Dict[str, Any]] = {}
        for row in self.holding_repo.list_latest(config_id):
            ticker = str(row["ticker"]).upper()
            state[ticker] = {
                "ticker": ticker,
                "shares": float(row.get("shares") or 0.0),
                "avg_cost": float(row.get("avg_cost") or 0.0),
                "currency": str(row.get("currency") or "USD").upper(),
            }
        return state

    def _rebuild_snapshots(
        self,
        config_id: int,
        snapshot_date: str,
        holdings_state: Dict[str, Dict[str, Any]],
        base_currency: str,
        exchange_rate: float,
        available_cash_base: float,
    ) -> float:
        tickers = [ticker for ticker, row in holdings_state.items() if float(row.get("shares") or 0) > 0]
        prices = self._fetch_current_prices(tickers)

        total_value_base = max(float(available_cash_base), 0.0)
        per_ticker_values_base: Dict[str, float] = {}
        per_ticker_values_krw: Dict[str, float] = {}

        for ticker, row in holdings_state.items():
            shares = float(row.get("shares") or 0.0)
            if shares <= 0:
                continue
            currency = str(row.get("currency") or "USD").upper()
            price = float(prices.get(ticker) or row.get("avg_cost") or 0.0)
            value_local = shares * price
            value_base = self._to_base(value_local, currency, base_currency, exchange_rate)
            value_krw = self._to_krw(value_local, currency, exchange_rate)
            per_ticker_values_base[ticker] = value_base
            per_ticker_values_krw[ticker] = value_krw
            total_value_base += value_base

        denom = total_value_base if total_value_base > 0 else 1.0
        for ticker, row in holdings_state.items():
            shares = float(row.get("shares") or 0.0)
            if shares <= 0:
                continue
            allocation_pct = (per_ticker_values_base.get(ticker, 0.0) / denom) * 100.0
            self.holding_repo.create_snapshot(
                config_id=config_id,
                snapshot_date=snapshot_date,
                ticker=ticker,
                shares=shares,
                avg_cost=float(row.get("avg_cost") or 0.0),
                currency=str(row.get("currency") or "USD"),
                current_value_krw=per_ticker_values_krw.get(ticker, 0.0),
                allocation_pct=allocation_pct,
                commit=False,
            )

        self.db.get_connection().commit()
        return total_value_base

    def _execute_trades(
        self,
        decision_id: int,
        plan: List[Dict[str, Any]],
        config_row: Dict[str, Any],
        exchange_rate: float,
    ) -> Dict[str, Any]:
        base_currency = str(config_row.get("base_currency") or "KRW").upper()
        available_cash_base = float(config_row.get("available_cash") or 0.0)
        holdings_state = self._load_latest_holdings_state(int(config_row["id"]))
        prices = self._fetch_current_prices([item.get("ticker", "") for item in plan])
        trade_rows: List[Dict[str, Any]] = []
        errors: List[str] = []

        for item in plan:
            ticker = str(item.get("ticker") or "").upper()
            action = str(item.get("action") or "HOLD").lower()
            shares = max(float(item.get("shares") or 0.0), 0.0)
            if not ticker or action not in {"buy", "sell", "hold"}:
                continue

            currency, market = self._ticker_currency_market(ticker)
            price = float(prices.get(ticker) or 0.0)
            if action in {"buy", "sell"} and (price <= 0 or shares <= 0):
                errors.append(f"{ticker}: invalid price/shares")
                continue

            if action == "hold":
                trade_rows.append(
                    {
                        "portfolio_decision_id": decision_id,
                        "ticker": ticker,
                        "action": "hold",
                        "shares": 0.0,
                        "price": 0.0,
                        "currency": currency,
                        "exchange_rate": exchange_rate,
                        "fee_rate": 0.0,
                        "fee_amount": 0.0,
                        "amount_local": 0.0,
                        "amount_krw": 0.0,
                        "executed_at": datetime.now().isoformat(),
                    }
                )
                continue

            if action == "buy":
                amount_local = shares * price
                amount_base = self._to_base(amount_local, currency, base_currency, exchange_rate)
                amount_krw = self._to_krw(amount_local, currency, exchange_rate)
                fee = self.fee_calculator.calculate(market, action, amount_base, config=config_row)
                fee_krw = (
                    fee.amount
                    if base_currency == "KRW"
                    else self._to_krw(fee.amount, "USD", exchange_rate)
                )
                total_spend_base = amount_base + fee.amount
                if total_spend_base > available_cash_base + 1e-9:
                    errors.append(f"{ticker}: insufficient cash")
                    continue
                available_cash_base -= total_spend_base
                prev = holdings_state.get(
                    ticker,
                    {"ticker": ticker, "shares": 0.0, "avg_cost": 0.0, "currency": currency},
                )
                prev_shares = float(prev.get("shares") or 0.0)
                prev_avg = float(prev.get("avg_cost") or 0.0)
                new_shares = prev_shares + shares
                new_avg = ((prev_shares * prev_avg) + (shares * price)) / new_shares if new_shares > 0 else 0.0
                holdings_state[ticker] = {
                    "ticker": ticker,
                    "shares": new_shares,
                    "avg_cost": new_avg,
                    "currency": currency,
                }
            else:
                prev = holdings_state.get(ticker)
                if not prev or float(prev.get("shares") or 0.0) <= 0:
                    errors.append(f"{ticker}: nothing to sell")
                    continue
                prev_shares = float(prev.get("shares") or 0.0)
                sell_shares = min(shares, prev_shares)
                shares = sell_shares
                amount_local = shares * price
                amount_base = self._to_base(amount_local, currency, base_currency, exchange_rate)
                amount_krw = self._to_krw(amount_local, currency, exchange_rate)
                fee = self.fee_calculator.calculate(market, action, amount_base, config=config_row)
                fee_krw = (
                    fee.amount
                    if base_currency == "KRW"
                    else self._to_krw(fee.amount, "USD", exchange_rate)
                )
                proceeds_base = max(amount_base - fee.amount, 0.0)
                available_cash_base += proceeds_base
                remain = prev_shares - sell_shares
                if remain <= 1e-8:
                    holdings_state.pop(ticker, None)
                else:
                    prev["shares"] = remain
                    holdings_state[ticker] = prev

            trade_rows.append(
                {
                    "portfolio_decision_id": decision_id,
                    "ticker": ticker,
                    "action": action,
                    "shares": shares,
                    "price": price,
                    "currency": currency,
                    "exchange_rate": exchange_rate,
                    "fee_rate": fee.rate,
                    "fee_amount": fee_krw,
                    "amount_local": amount_local,
                    "amount_krw": amount_krw,
                    "executed_at": datetime.now().isoformat(),
                }
            )

        trade_ids = self.trade_repo.create_batch(trade_rows) if trade_rows else []

        snapshot_date = self._today_kst().date().isoformat()
        total_fund_base = self._rebuild_snapshots(
            config_id=int(config_row["id"]),
            snapshot_date=snapshot_date,
            holdings_state=holdings_state,
            base_currency=base_currency,
            exchange_rate=exchange_rate,
            available_cash_base=available_cash_base,
        )

        self.config_repo.update_fund(
            config_id=int(config_row["id"]),
            total_fund=total_fund_base,
            available_cash=available_cash_base,
        )
        self.holding_repo.cleanup_old_snapshots(
            config_id=int(config_row["id"]),
            days=self.snapshot_retention_days,
        )

        return {
            "trade_ids": trade_ids,
            "errors": errors,
            "total_fund_base": total_fund_base,
            "available_cash_base": available_cash_base,
        }

    def run_daily(self, config_id: Optional[int] = None) -> Dict[str, Any]:
        cfg = self._get_active_config(config_id)
        if not cfg:
            return {"status": "skipped", "reason": "no active config"}

        today = self._today_kst().date().isoformat()
        existing = self.decision_repo.get_by_date(int(cfg["id"]), today)
        if existing and existing.get("status") == "completed":
            return {"status": "skipped", "reason": "already completed", "decision": existing}

        reports = self._load_today_reports(today)
        skipped_tickers = self._load_today_skipped_tickers(today)
        if not reports and not skipped_tickers:
            return {"status": "skipped", "reason": "no reports"}

        if skipped_tickers:
            report_tickers = {str(item.get("ticker") or "").upper() for item in reports}
            for ticker in skipped_tickers:
                if ticker in report_tickers:
                    continue
                reports.append(
                    {
                        "ticker": ticker,
                        "market_report": "오늘 분석 없음 (데이터 미갱신)",
                        "final_trade_decision": "HOLD",
                        "decision_position": "HOLD",
                        "portfolio_action": "HOLD",
                        "portfolio_shares": 0.0,
                        "pa_opinion": "오늘 분석 없음 (데이터 미갱신)",
                        "analysis_skipped": True,
                        "skip_reason": "오늘 분석 없음 (데이터 미갱신)",
                    }
                )

        latest_holdings = self.holding_repo.list_latest(int(cfg["id"]))
        briefing = self.briefing_agent.generate_briefing(reports, latest_holdings)
        tickers = [str(item.get("ticker") or "").upper() for item in (briefing.get("items") or [])]
        current_prices = self._fetch_current_prices(tickers)
        exchange_rate = self.exchange_rate_service.get_usd_krw()

        plan_payload = self.pm_agent.decide_allocation(
            briefing=briefing,
            holdings=latest_holdings,
            available_cash=float(cfg.get("available_cash") or 0.0),
            exchange_rate=exchange_rate,
            current_prices=current_prices,
        )

        decision_id = self.decision_repo.create(
            portfolio_config_id=int(cfg["id"]),
            decision_date=today,
            briefing_summary=briefing,
            allocation_plan=plan_payload.get("allocation_plan") or [],
            rationale=plan_payload.get("rationale"),
            total_fund_snapshot=float(cfg.get("total_fund") or 0.0),
            available_cash_snapshot=float(cfg.get("available_cash") or 0.0),
            exchange_rate_snapshot=exchange_rate,
            status="executing",
            error_message=None,
        )

        execution = self._execute_trades(
            decision_id=decision_id,
            plan=plan_payload.get("allocation_plan") or [],
            config_row=cfg,
            exchange_rate=exchange_rate,
        )
        errors = execution.get("errors") or []
        if errors:
            status = "partial_failed" if execution.get("trade_ids") else "failed"
            self.decision_repo.update_status(decision_id, status, error_message="; ".join(errors)[:1000])
        else:
            self.decision_repo.update_status(decision_id, "completed")

        decision = self.decision_repo.get_by_id(decision_id)
        return {
            "status": decision.get("status") if decision else "failed",
            "decision_id": decision_id,
            "errors": errors,
            "decision": decision,
        }

    @staticmethod
    def _aggregate_weekly_totals(holdings: List[Dict[str, Any]]) -> Dict[str, float]:
        by_date: Dict[str, float] = defaultdict(float)
        for row in holdings:
            snapshot = row.get("snapshot_date")
            if hasattr(snapshot, "isoformat"):
                key = snapshot.isoformat()
            else:
                key = str(snapshot)
            by_date[key] += float(row.get("current_value_krw") or 0.0)
        return dict(by_date)

    def run_weekly(self, config_id: Optional[int] = None) -> Dict[str, Any]:
        cfg = self._get_active_config(config_id)
        if not cfg:
            return {"status": "skipped", "reason": "no active config"}

        today = self._today_kst().date()
        week_end = today.isoformat()
        week_start = (today - timedelta(days=6)).isoformat()

        decisions = self.decision_repo.list_by_week(int(cfg["id"]), week_start, week_end)
        if not decisions:
            return {"status": "skipped", "reason": "no weekly decisions"}
        trades = self.trade_repo.list_by_week(int(cfg["id"]), week_start, week_end)
        holdings = self.holding_repo.list_by_date_range(int(cfg["id"]), week_start, week_end)

        totals = self._aggregate_weekly_totals(holdings)
        sorted_days = sorted(totals.keys())
        total_return_pct: Optional[float] = None
        if len(sorted_days) >= 2:
            start_value = totals.get(sorted_days[0], 0.0)
            end_value = totals.get(sorted_days[-1], 0.0)
            if start_value > 0:
                total_return_pct = ((end_value - start_value) / start_value) * 100.0

        reflection = self.reflector.reflect_weekly(
            config_id=int(cfg["id"]),
            week_start_date=week_start,
            week_end_date=week_end,
            decisions=decisions,
            trades=trades,
            holdings=holdings,
            total_return_pct=total_return_pct,
        )
        return {
            "status": "completed",
            "reflection": reflection,
        }
