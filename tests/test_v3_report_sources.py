"""Report archives use the saved report identity and two point-in-time source groups."""

from datetime import UTC, datetime
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradingagents.forecast_lab.app import application
from tradingagents.forecast_lab.issue_collector import EXPORT, SOURCE
from tradingagents.forecast_lab.public_app import create_app
from tradingagents.forecast_lab.public_projection import news_evidence_projection
from tradingagents.forecast_lab.shared_archive import LocalSupplement
from tradingagents.forecast_lab.shared_view import SharedReader
from fastapi import HTTPException


class ReportArchiveTests(TestCase):
    def test_input_keeps_reference_order_and_citations_across_two_full_sources(self):
        cutoff = "2025-01-06T00:00:00+00:00"
        rows = []
        for i in range(1, 81):
            rss = i % 2 == 0
            rows.append({
                "ref": f"N{i}", "source": SOURCE if rss else EXPORT,
                "title": f"Headline {i}", "publisher": "News" if rss else "github",
                "url": f"https://news.google.com/rss/articles/stored-{i}" if rss else f"https://github.com/public/research/issues/{i}",
                "published_at": "2025-01-03T00:00:00Z", "first_seen_at": "2025-01-04T00:00:00Z",
            })
        for count in (16, 80):
            with self.subTest(count=count):
                last = f"N{count}"
                packet = {"version": 1, "ticker": "NVDA", "as_of": cutoff, "status": "available",
                          "items": rows[:count], "analyst_cited": ["N1", last], "decision_cited": [last]}
                clean = news_evidence_projection(packet, "NVDA", cutoff)
                self.assertEqual([row["ref"] for row in clean["items"]], [row["ref"] for row in rows[:count]])
                self.assertEqual(clean["items"][-1]["url"], rows[count - 1]["url"])
                self.assertEqual(clean["decision_cited"], [last])
                self.assertEqual(news_evidence_projection(clean, "NVDA", cutoff), clean)
        # 41 RSS + 39 export records are outside the per-source archive contract.
        unbalanced = [{**rows[1], "ref": "N1", "url": "https://news.google.com/rss/articles/other-123"}, *rows[1:]]
        self.assertEqual(news_evidence_projection({**packet, "items": unbalanced}, "NVDA", cutoff), {"status": "unverified"})

    def test_frozen_news_input_survives_archive_outage_and_both_public_projections(self):
        cutoff = "2025-01-06T00:00:00+00:00"
        item = {
            "ref": "N1", "source": SOURCE, "publisher": "시장 뉴스", "title": "분석 당시 제목",
            "url": "https://news.google.com/rss/articles/stored-123",
            "published_at": "2025-01-03T00:00:00Z", "first_seen_at": "2025-01-04T00:00:00Z",
            "private_notes": "SECRET",
        }
        packet = {"version": 1, "ticker": "NVDA", "as_of": cutoff, "status": "available",
                  "items": [item], "analyst_cited": ["N1"], "decision_cited": ["N1"], "prompt": "SECRET"}
        identity = {"ticker": "NVDA", "cutoff": datetime(2025, 1, 7, tzinfo=UTC), "news_evidence": packet}
        db = Mock()
        db.execute.return_value.fetchone.return_value = identity
        local = object.__new__(LocalSupplement)

        @contextmanager
        def connect(key):
            if key == "v3_archive":
                raise HTTPException(503)
            self.assertEqual(key, "v2_console")
            yield db

        def read():
            core = TestClient(create_app(SharedReader(local), shared_role="core"))
            edge = TestClient(create_app(lambda path: core.get(path).json(), shared_role="edge"))
            return edge.get("/api/report-sources/3").json()

        with patch.object(local, "connect", connect):
            data = read()
            stored = data["news_evidence"]
            self.assertEqual(data["issues"]["status"], "failed")
            self.assertNotIn("SECRET", str(data))
            self.assertEqual(stored["items"][0]["ref"], "N1")
            self.assertEqual(stored["items"][0]["title"], item["title"])
            self.assertEqual(stored["decision_cited"], ["N1"])
            self.assertEqual(stored["as_of"], cutoff)
            self.assertIn("r.news_evidence", db.execute.call_args.args[0])
            self.assertEqual(db.execute.call_args.args[1], (3,))
            for change in ({"ticker": "SPY"}, {"as_of": "2025-01-08T00:00:00Z"},
                           {"items": [{**item, "first_seen_at": cutoff}]}, {"decision_cited": ["N9"]},
                           {"items": [{**item, "url": "https://internal.local/private"}]}):
                with self.subTest(change=change):
                    identity["news_evidence"] = {**packet, **change}
                    self.assertEqual(read()["news_evidence"], {"status": "unverified"})
            identity["news_evidence"] = None
            self.assertIsNone(read()["news_evidence"])

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
