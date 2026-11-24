"""List endpoints must preserve historical fields without per-ticker database calls."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from tradingagents.api.app import app


class ListEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = Mock()
        self.execute = self.db.get_connection.return_value.execute
        self.scheduler = SimpleNamespace(db=self.db, scheduler=Mock())
        self.scheduler.scheduler.get_jobs.return_value = []

    def test_report_fallback_and_absent_actions(self):
        self.execute.return_value.fetchall.return_value = [
            dict(ticker="X", report_count=2, latest_at="d", latest_cycle=10,
                 final_trade_decision="decision: SELL", decision_position=None,
                 portfolio_action=None, portfolio_shares=None, trade_action=None, trade_shares=None),
            dict(ticker="Y", report_count=1, latest_at="d", latest_cycle=1,
                 final_trade_decision=None, decision_position="BUY",
                 portfolio_action="HOLD", portfolio_shares=0, trade_action="SELL", trade_shares=1),
        ]
        with patch("tradingagents.api.app.scheduler", self.scheduler):
            response = self.client.get("/reports/tickers")
        self.assertEqual(response.status_code, 200)
        old, new = response.json()
        self.assertEqual((old["decision_position"], old["stored_decision_position"]), ("SELL", None))
        self.assertNotIn("trade_action", old)
        self.assertNotIn("portfolio_shares", old)
        self.assertEqual((new["stored_decision_position"], new["last_decision"], new["portfolio_shares"]),
                         ("BUY", "", 0))
        self.assertEqual(new["trade_shares"], 1)
        self.execute.assert_called_once()

    def test_schedule_page_failed_and_missing_latest(self):
        date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.execute.return_value.fetchall.return_value = [
            dict(ticker="A", interval_days=2, id=8, scheduled_cycle=3, status="failed",
                 error_type="provider", error_message="unavailable", created_at=date),
            dict(ticker="B", interval_days=1, id=None, scheduled_cycle=None, status=None,
                 error_type=None, error_message=None, created_at=None),
        ]
        with patch("tradingagents.api.app.scheduler", self.scheduler):
            response = self.client.get("/schedules?cursor=2&limit=5")
        self.assertEqual(response.status_code, 200)
        failed, empty = response.json()
        self.assertEqual(failed["latest_cycle"]["error_message"], "unavailable")
        self.assertEqual(failed["latest_cycle"]["id"], 8)
        self.assertIsNone(empty["latest_cycle"])
        self.assertIsNone(empty["next_run_time"])
        self.execute.assert_called_once()
        self.assertEqual(self.execute.call_args.args[1], (5, 2))
