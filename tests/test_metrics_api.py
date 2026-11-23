import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from tradingagents.api.app import app as application


class ApiMetricsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(application)

    def test_ledger_currency_groups_and_mixed_total(self):
        rows = [
            dict(id=i, ticker=symbol, status="closed", shares=1, avg_cost=100,
                 return_pct=10, currency=currency, action=action, fill_shares=1,
                 price=price, fill_currency=currency)
            for i, symbol, currency in [(1, "US", "USD"), (2, "KR", "KRW")]
            for action, price in [("BUY", 100), ("SELL", 110)]
        ]
        ledger, scores = Mock(), Mock()
        ledger.fetchall.return_value = rows
        scores.fetchone.return_value = {}
        db = Mock()
        db.get_connection.return_value.execute.side_effect = [ledger, scores]
        with patch("tradingagents.api.app.scheduler", SimpleNamespace(db=db)):
            res = self.client.get("/metrics")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertIsNone(payload["total_return_pct"])
        self.assertEqual(payload["by_currency"]["USD"]["total_return_pct"], 10)
        self.assertEqual(payload["by_currency"]["KRW"]["total_return_pct"], 10)
        self.assertEqual(payload["closed_positions"], 2)

    def test_write_requires_auth_before_any_scheduler_work(self):
        with patch.dict("os.environ", {"TRADINGAGENTS_ADMIN_TOKEN": "fixture-admin-token"}):
            denied = self.client.post("/reflections/retry/1")
            self.assertIn(denied.status_code, (401, 403))
            with self.assertLogs("tradingagents.api.auth", "WARNING") as logs:
                denied = self.client.post("/reflections/retry/1", headers={"Authorization": "Bearer SECRET-MUST-NOT-APPEAR"})
            self.assertEqual(denied.status_code, 401)
            self.assertNotIn("SECRET", "".join(logs.output))


if __name__ == "__main__":
    unittest.main()
