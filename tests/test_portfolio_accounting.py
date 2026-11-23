import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pandas as pd
from tradingagents.graph.portfolio_reflection import PortfolioReflector
from tradingagents.scheduler.portfolio_pipeline import PortfolioPipeline
from tradingagents.virtual_trade.portfolio_manager_agent import PortfolioManagerAgent


class PortfolioAccountingTests(unittest.TestCase):
    def test_single_ticker_multiindex_with_market_holiday(self):
        frame = pd.DataFrame([[10], [float("nan")]], columns=pd.MultiIndex.from_tuples([("ABC", "Close")]))
        with patch("yfinance.download", return_value=frame):
            self.assertEqual(PortfolioPipeline._fetch_current_prices(None, ["ABC"]), {"ABC": 10})

    def test_missing_mark_aborts_snapshot(self):
        pipeline = PortfolioPipeline.__new__(PortfolioPipeline)
        pipeline.holding_repo = Mock()
        with self.assertRaisesRegex(ValueError, "ABC"):
            pipeline._rebuild_snapshots(1, "2026-01-01", {"ABC": {"shares": 2, "avg_cost": 7}},
                                        "USD", 1400, 100, {}, None)
        pipeline.holding_repo.create_snapshot.assert_not_called()

    def test_weekly_return_includes_cash(self):
        pipeline = Mock()
        pipeline._get_active_config.return_value = {"id": 1, "total_fund": 99}
        pipeline._today_kst.return_value.date.return_value = date(2026, 11, 22)
        pipeline.decision_repo.list_by_week.return_value = [{"status": "completed", "total_fund_snapshot": 100}]
        pipeline.holding_repo.list_by_date_range.return_value = []
        PortfolioPipeline.run_weekly(pipeline)
        self.assertAlmostEqual(pipeline.reflector.reflect_weekly.call_args.kwargs["total_return_pct"], -1)

    def test_reflection_uses_observed_return_and_handles_db_types(self):
        obj = PortfolioReflector(Mock(), Mock(), Mock())
        obj.repo = Mock()
        obj.llm.invoke.return_value.content = '{"reflection_content":"text","key_lessons":"lesson","total_return_pct":92}'
        args = (1, "start", "end", [{"decision_date": date.today(), "nav": Decimal("100")}], [], [])
        obj.reflect_weekly(*args, -2)
        self.assertEqual(obj.repo.create.call_args.kwargs["total_return_pct"], -2)
        self.assertEqual(obj.hybrid_memory.add_external_document.call_args.kwargs["metadata"]["outcome"], "loss")
        obj.repo.reset_mock()
        obj.hybrid_memory.reset_mock()
        obj.llm.invoke.side_effect = RuntimeError("offline")
        with self.assertRaises(RuntimeError):
            obj.reflect_weekly(*args, None)
        obj.repo.create.assert_not_called()
        obj.hybrid_memory.add_external_document.assert_not_called()

    def test_rounded_shares_stay_within_cash(self):
        pm = PortfolioManagerAgent(Mock())
        item = {"ticker": "ABC", "action": "BUY", "shares": 1, "allocation_pct": 100}
        result = pm._validate_plan({"allocation_plan": [item]}, 100, {"ABC": 101})
        self.assertLessEqual(result["allocation_plan"][0]["shares"] * 101, 100)

    def test_nonfinite_llm_shares_rejected(self):
        pm = PortfolioManagerAgent(Mock())
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            pm._parse_plan('{"allocation_plan":[{"ticker":"ABC","shares":"NaN"}]}')
