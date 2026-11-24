"""Contracts for selected-ticker validation and report-linked fill attribution."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import unittest
from unittest.mock import patch
from fastapi import HTTPException
from tradingagents.api import app, routes
from tradingagents.storage import PositionRepository


class ConsoleEvidenceTests(unittest.TestCase):
    def test_attaches_only_explicitly_linked_fills_and_preserves_missing_decision(self):
        reports = [{"id": 11, "decision_position": None}, {"id": 12, "decision_position": "SELL"}]
        fill = dict(report_id=12, action="BUY", shares=0.5, price=120, currency="USD",
                    executed_at="2026-11-23T12:00:00Z")
        routes._attach_report_evidence(reports, [fill, {**fill, "report_id": 15}])
        assert reports[0]["stored_decision_position"] is None
        assert reports[0]["execution_trades"] == []
        assert reports[1]["stored_decision_position"] == "SELL"
        assert reports[1]["execution_trades"] == [{k: v for k, v in fill.items() if k != "report_id"}]



    def test_mixed_and_missing_selected_ids_reject_whole_request(self):
        for second in (None, {"id": 22, "ticker": "B", "status": "active"}):
            db = Mock()
            positions = {11: {"id": 11, "ticker": "A", "status": "active"}, 22: second}
            request = routes.RetrospectiveAnalyzeRequest(mode="ticker", ticker="A", position_ids=[11, 22])
            with self.subTest(second=second), patch.object(routes.app_module, "scheduler", SimpleNamespace(db=db)), \
                    patch.object(PositionRepository, "get_by_id", side_effect=positions.get), \
                    self.assertRaises(HTTPException) as error:
                asyncio.run(routes.request_retrospective_analysis(request, True))
            self.assertEqual(error.exception.status_code, 400)
            db.get_connection.return_value.execute.assert_not_called()

    def test_legacy_selection_and_normalized_match(self):
        for ticker in (None, " a "):
            request = routes.RetrospectiveAnalyzeRequest(mode="ticker", ticker=ticker, position_ids=[11])
            with self.subTest(ticker=ticker), patch.object(routes.app_module, "scheduler", SimpleNamespace(db=Mock())), \
                    patch.object(PositionRepository, "get_by_id", return_value={"ticker": "A", "status": "reset"}):
                self.assertEqual(asyncio.run(routes.request_retrospective_analysis(request, True))["enqueued"], [])


    def test_public_report_detail_preserves_legacy_fallback_and_uses_one_fill_query(self):
        from fastapi.testclient import TestClient
        db = Mock()
        execute = db.get_connection.return_value.execute
        execute.return_value.fetchall.side_effect = [
            [{"id": 7, "decision_position": None, "final_trade_decision": "decision: BUY",
              "portfolio_action": "SELL", "portfolio_shares": 0}],
            [],
        ]
        with patch.object(app, "scheduler", SimpleNamespace(db=db)):
            response = TestClient(app.app).get("/reports?ticker=QA&limit=1")
        self.assertEqual(response.status_code, 200)
        row, = response.json()
        self.assertEqual(row["decision_position"], "BUY")
        self.assertIsNone(row["stored_decision_position"])
        self.assertEqual(row["execution_trades"], [])
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(execute.call_args.args[1], ([7],))
