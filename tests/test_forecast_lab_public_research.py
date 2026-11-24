import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from fastapi.testclient import TestClient
from tradingagents.forecast_lab.public_app import create_app, read_upstream


class PublicResearchViewerTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        dist = Path(self.temp.name)
        (dist / "assets").mkdir()
        (dist / "index.html").write_text(
            '<html><head><script type="module" src="/assets/index-a1.js"></script></head></html>',
            encoding="utf8",
        )
        for name in ("index-a1.js", "index-old.js", "source.js.map"):
            (dist / "assets" / name).write_text("0")
        self.summary = {
            "id": 29,
            "ticker": "KO",
            "market": "us",
            "status": "pending",
            "data_session": "2025-01-03",
            "entry_open_at": "2025-01-06T14:30:00Z",
            "exit_close_at": "2025-01-10T21:00:00Z",
        }
        self.detail = {
            **self.summary,
            "snapshot": {
                "currency": "USD",
                "bars": [
                    {"date": "2025-01-03", "close": 20, "private": "PRIVATE_TRACE"},
                    {"date": "2030-01-01", "close": 90},
                ],
                "diagnostic": "PRIVATE_TRACE",
            },
            "arms": [
                {
                    "method": "single",
                    "status": "published",
                    "published_at": "2025-01-03T21:00:00Z",
                    "probability": 0.7,
                    "rationale": "완료된 추세와 변동성을 비교했습니다.",
                    "audit": {"trace": "PRIVATE_TRACE"},
                },
                {"method": "memory", "status": "failed", "rationale": "PRIVATE_TRACE"},
                {
                    "method": "debate",
                    "status": "published",
                    "published_at": "2025-01-03T21:00:00Z",
                    "probability": 0.4,
                    "rationale": "postgresql://user:password@localhost/db",
                },
            ],
        }
        self.reader = Mock(
            side_effect={
                "/api/status": {
                    "tickers": [{"ticker": "KO", "market": "us"}],
                    "progress": {"phase": "issuing", "private": "PRIVATE_TRACE"},
                },
                "/api/stats?market=us": {"counts": {"pending": 1}, "comparisons": []},
                "/api/cases?limit=21&market=us&published_only=true": [self.summary],
                "/api/cases/29": self.detail,
            }.__getitem__
        )
        self.client = TestClient(create_app(self.reader, dist=dist))

    def test_shell_research_and_only_current_assets(self):
        root = self.client.get("/")
        self.assertIn(
            'name="forecast-console-access" content="public-readonly"', root.text
        )
        self.assertIn("frame-src 'self'", root.headers["content-security-policy"])
        self.assertIn("frame-ancestors 'self'", root.headers["content-security-policy"])
        self.assertEqual(self.client.get("/assets/index-old.js").status_code, 404)
        self.assertEqual(self.client.get("/assets/source.js.map").status_code, 404)
        self.assertEqual(self.client.get("/assets/index-a1.js").status_code, 200)
        page = self.client.get("/research/?embedded=1&case=29")
        self.assertIn('id="detail"', page.text)
        for asset in re.findall(r'(?:src|href)="(/[^"]+)"', page.text):
            self.assertEqual(self.client.get(asset).status_code, 200, asset)
        self.reader.assert_not_called()

    def test_only_frozen_prices_and_published_narratives(self):
        self.assertEqual(
            self.client.get("/api/status").json()["progress"]["phase"], "issuing"
        )
        self.assertEqual(
            self.client.get("/api/stats?market=us").json()["counts"]["pending"], 1
        )
        self.assertEqual(
            self.client.get("/api/cases?market=us&limit=21").json()[0]["id"], 29
        )
        detail = self.client.get("/api/cases/29")
        body = detail.json()
        self.assertEqual(len(body["snapshot"]["bars"]), 1)
        self.assertEqual([a["method"] for a in body["arms"]], ["single", "debate"])
        self.assertIn("변동성", body["arms"][0]["rationale"])
        self.assertIsNone(body["arms"][1]["rationale"])
        self.assertNotIn("PRIVATE_TRACE", detail.text)
        self.assertNotIn("password", detail.text)
        self.assertEqual(
            self.client.get(
                "/api/cases/29", headers={"If-None-Match": detail.headers["etag"]}
            ).status_code,
            304,
        )
        self.assertEqual(self.reader.call_count, 4)

    def test_no_unknown_filters_or_internal_paths(self):
        for path in (
            "/api/cases?limit=201",
            "/api/stats?market=else",
            "/api/cases?published_only=false",
            "/api/stats?market=us&market=kr",
            "/api/stats?from_date=2026-11-01&to_date=2026-01-01",
        ):
            self.assertEqual(self.client.get(path).status_code, 400)
        self.assertEqual(self.client.post("/api/cases").status_code, 405)
        for path in (
            "https://example.com/api/stats",
            "/api/cases?url=private",
            "/admin",
        ):
            with self.assertRaises(ValueError):
                read_upstream(path)
        self.reader.assert_not_called()
