"""Shared endpoints use V2 identities. The optional V3 archive cannot replace a forecast."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from tradingagents.forecast_lab.public_app import create_app
from tradingagents.forecast_lab.shared_view import SharedReader, build_shared_edge, empty_archive

CUTOFF = "2026-01-12T12:00:00+00:00"
ENTRY = "2026-01-13T14:30:00+00:00"
EXIT = "2026-01-20T21:00:00+00:00"


def fixture_row(i=1):
    return {"id": i, "ticker": "SPY", "market": "us", "data_session": "2026-01-12",
            "status": "awaiting", "entry_open_at": ENTRY, "exit_close_at": EXIT}


class SharedViewTests(unittest.TestCase):
    def test_forecast_directory_reads_shared_data_and_exposes_only_public_fields(self):
        supplement = Mock()
        supplement.forecast_tickers.return_value = [
            {**fixture_row(), "secret": "private", "forecast_probabilities": {"single": 0.0, "trace": "private"}},
            {**fixture_row(2), "market": "invalid"},
        ]
        reader = SharedReader(supplement, Mock(side_effect=AssertionError))
        client = TestClient(create_app(reader, shared_role="core"))
        path = "/api/forecast-tickers"
        expected = [{"id": 1, "ticker": "SPY", "market": "us", "data_session": "2026-01-12",
                     "forecast_probabilities": {"single": 0.0}}]
        self.assertEqual(client.get(path).json(), expected)
        self.assertEqual(client.get(path).json(), expected)
        supplement.forecast_tickers.assert_called_once_with()
        self.assertEqual(client.get(path + "?ticker=SPY").status_code, 400)
        self.assertEqual(client.post(path).status_code, 405)
        with patch("tradingagents.forecast_lab.shared_view.private_get", return_value=expected) as core:
            self.assertEqual(TestClient(build_shared_edge()).get(path).json(), expected)
            core.assert_called_once_with(path)

    def test_only_batch_missing_probabilities_and_check_identity(self):
        rows = [fixture_row(i) for i in range(1, 101)]
        supplement = Mock()
        supplement.probabilities.side_effect = lambda ids: {str(i): {
            "ticker": "SPY", "data_session": "2026-01-12", "probabilities": {"single": .29}} for i in ids}
        reader = SharedReader(supplement, lambda _: copy.deepcopy(rows))
        projected = reader("/api/cases?limit=100")
        self.assertEqual([40, 40, 20], [len(c.args[0]) for c in supplement.probabilities.call_args_list])
        self.assertTrue(all(x["forecast_probabilities"] == {"single": .29} for x in projected))
        rows[0]["ticker"] = "NVDA"
        with self.assertRaises(HTTPException):
            reader("/api/cases")

    def test_case_never_borrows_old_numeric_ids(self):
        row = {**fixture_row(), "snapshot": {"observed_at": CUTOFF}, "arms": []}
        supplement = Mock()
        reader = SharedReader(supplement, lambda _: copy.deepcopy(row))
        for wrong in ({"ticker":"NVDA"}, {"as_of": ENTRY}, {"id":2}):
            supplement.evidence.return_value = {"ticker":"SPY","as_of":CUTOFF,"id":1,
                **empty_archive(CUTOFF, "uncollected"), **wrong}
            view = reader("/api/cases/1")
            self.assertEqual(view["ticker"], "SPY")
            self.assertEqual(view["issues"]["status"], "failed")
            self.assertEqual(view["issues"]["items"], [])

    def test_report_uncollected_is_readable_and_missing_identity_404(self):
        supplement = Mock()
        supplement.evidence.return_value = {"id":18,"ticker":"SPY","as_of":CUTOFF,**empty_archive(CUTOFF,"uncollected")}
        reader = SharedReader(supplement, Mock(side_effect=AssertionError))
        client = TestClient(create_app(reader, shared_role="edge"))
        view = client.get("/api/report-sources/18").json()
        self.assertEqual(view["issues"]["provenance"], "v3_archive_as_of")
        self.assertEqual(view["last30days"]["status"], "uncollected")
        supplement.evidence.side_effect = HTTPException(404)
        self.assertEqual(client.get("/api/report-sources/19").status_code, 404)
        self.assertEqual(client.post("/api/report-sources/18").status_code, 405)

    def test_edge_never_exposes_supplement_or_admin(self):
        client = TestClient(build_shared_edge())
        self.assertEqual(client.get("/healthz").json()["source"], "v2")
        for path in ("/_shared/probabilities?ids=1", "/_shared/case/1","/workspace-api/admin"):
            self.assertIn(client.get(path).status_code, (400,404))
        self.assertEqual(client.post("/workspace-api/run").status_code,405)

    def test_source_outage_never_switches_to_the_old_v3_store(self):
        reader = Mock(side_effect=HTTPException(503, "private diagnostic"))
        client = TestClient(create_app(reader, shared_role="core"))
        self.assertEqual(client.get("/healthz").status_code, 200)
        for route in ("/ready", "/api/cases?limit=1", "/api/cases/1", "/api/status"):
            result = client.get(route)
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("private diagnostic", result.text)

    def test_shared_cli_refuses_writers_before_config_loading(self):
        from tradingagents.forecast_lab import app
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"LOCALAPPDATA":temp}):
            runtime = Path(temp, "TradingAgentsV3")
            runtime.mkdir()
            (runtime / "shared-viewer.enabled").touch()
            for argv in (["lab","serve","--console"],["lab","run-once"],["lab","seed"]):
                with patch("sys.argv",argv), self.assertRaises(SystemExit) as error:
                    app.main()
                self.assertEqual(error.exception.code,2)
