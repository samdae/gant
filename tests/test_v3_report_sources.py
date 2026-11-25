"""Report archives use the saved report identity and two point-in-time source groups."""

from datetime import UTC, datetime
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradingagents.forecast_lab.app import application
from tradingagents.forecast_lab.issue_collector import EXPORT, SOURCE
from tradingagents.forecast_lab.public_app import create_app


class ReportArchiveTests(TestCase):
    def test_only_persisted_identity_controls_private_query(self):
        store = Mock()
        when = datetime(2025, 1, 6, tzinfo=UTC)
        store.report_sources.return_value = {"issues": None, "last30days": None}
        with patch("tradingagents.forecast_lab.console.mount_frontend"):
            client = TestClient(
                application(store, Mock(), Mock(), False, console=FastAPI())
            )
        with patch(
            "tradingagents.forecast_lab.console.report_identity",
            return_value=("NVDA", when),
        ) as identity:
            self.assertEqual(
                client.get("/api/report-sources/3?ticker=SPY").status_code, 404
            )
            identity.assert_not_called()
            self.assertEqual(
                client.get("/api/report-sources/3").json()["ticker"], "NVDA"
            )
            identity.assert_called_once_with(3)
            store.report_sources.assert_called_once_with("NVDA", when)
            identity.return_value = None
            self.assertEqual(client.get("/api/report-sources/8").status_code, 404)
        standalone = TestClient(application(store, Mock(), Mock(), False))
        self.assertEqual(standalone.get("/api/report-sources/3").status_code, 404)

    def test_integrated_bookmarks_and_standalone_reader(self):
        reader = Mock()
        public = TestClient(create_app(reader))
        with patch("tradingagents.forecast_lab.console.mount_frontend"):
            private = TestClient(
                application(Mock(), Mock(), Mock(), False, console=FastAPI())
            )
        for client in (private, public):
            self.assertIn(
                "/research/workspace-bookmark.js", client.get("/research/").text
            )
            script = client.get("/research/workspace-bookmark.js").text
            self.assertIn('"#observe": "/observe"', script)
            self.assertIn('"#results": "/results"', script)
            self.assertIn('id="detail"', client.get("/research/?embedded=1").text)
            self.assertEqual(
                client.get("/research/?case=1", follow_redirects=False).headers[
                    "location"
                ],
                "/#/research/1",
            )
        standalone = TestClient(application(Mock(), Mock(), Mock(), False))
        self.assertIn('id="detail"', standalone.get("/research/?case=1").text)
        reader.assert_not_called()

    def test_public_projection_rejects_cutoff_mismatch_and_extra_fields(self):
        cutoff = "2025-01-06T00:00:00+00:00"
        group = {
            "as_of": cutoff,
            "status": "uncollected",
            "source": SOURCE,
            "items": [],
            "collected_at": None,
            "private": "internal",
        }
        raw = {
            "ticker": "NVDA",
            "id": 3,
            "as_of": cutoff,
            "issues": group,
            "last30days": {**group, "source": EXPORT, "as_of": "2025-02-06T00:00:00Z"},
            "private": "internal",
        }
        reader = Mock(return_value=raw)
        client = TestClient(create_app(reader))
        self.assertEqual(client.get("/api/report-sources/3?as_of=now").status_code, 400)
        self.assertEqual(client.post("/api/report-sources/3").status_code, 405)
        reader.assert_not_called()
        response = client.get("/api/report-sources/3")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("internal", response.text)
        self.assertIsNone(response.json()["last30days"])
        self.assertEqual(response.json()["issues"]["status"], "uncollected")
        reader.assert_called_once_with("/api/report-sources/3")
        self.assertEqual(client.get("/api/report-sources/8").status_code, 404)
