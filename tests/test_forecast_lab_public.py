"""Public HTTP boundary runs without store, credentials or scheduler."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import TestCase
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from tradingagents.forecast_lab.public_app import (
    CASE_LIST,
    REPORTS,
    STATS,
    ProjectionCache,
    create_app,
    read_upstream,
)


class PublicReaderTests(TestCase):
    def setUp(self):
        self.case = {
            "id": 10,
            "ticker": "KO",
            "market": "us",
            "data_session": "2025-01-03",
            "entry_open_at": "2025-01-06T14:30:00Z",
            "exit_close_at": "2025-01-10T21:00:00Z",
            "status": "matured",
        }
        arm = {
            "method": "single",
            "status": "published",
            "probability": 0.62,
            "published_at": "2025-01-03T23:00:00Z",
            "brier": 0.1444,
            "rationale": "PRIVATE_REASON",
            "audit": {"trace": "PRIVATE_TRACE"},
        }
        report = {
            "id": 76,
            "ticker": "005930.KS",
            "stored_decision_position": "BUY",
            "created_at": "2025-01-03T21:30:00Z",
            "market_report": "종가는 62,800원으로 올랐습니다. PRIVATE_PROMPT",
            "fundamentals_report": "영업이익률은 7.5%로 개선되었습니다. PRIVATE_BROKER",
            "final_trade_decision": "PRIVATE_ORDER",
            "execution_trades": [{"private": "PRIVATE_TRADE"}],
            "display_name": "PRIVATE_DISPLAY_NAME",
        }
        data = {
            CASE_LIST: [
                self.case,
                {**self.case, "id": 11, "status": "pending"},
                {**self.case, "id": 12, "status": "unpublished"},
            ],
            STATS: {
                "comparisons": [],
                "sector_coverage": {
                    "published": 1,
                    "scored": 0,
                    "failed": "PRIVATE_ERROR",
                },
            },
            REPORTS: [report],
            "/api/cases/10": {
                **self.case,
                "snapshot": {"private": "PRIVATE_NEWS"},
                "arms": [
                    arm,
                    {**arm, "method": "memory", "status": "skipped"},
                    {**arm, "published_at": "2030-01-01T00:00:00Z"},
                ],
                "outcome": {
                    "status": "scored",
                    "actual": 1,
                    "entry_open": 60,
                    "exit_close": 61,
                    "audit": "PRIVATE_REFERENCE",
                },
            },
        }
        self.reader = Mock(side_effect=data.__getitem__)
        self.client = TestClient(create_app(self.reader))

    def test_only_published_results_and_public_fact_templates(self):
        overview = self.client.get("/public-api/overview")
        self.assertEqual([r["id"] for r in overview.json()["cases"]], [10])
        detail = self.client.get("/public-api/cases/10")
        self.assertEqual(detail.json()["name"], "코카콜라")
        self.assertEqual([a["method"] for a in detail.json()["forecasts"]], ["single"])
        self.assertEqual(
            detail.json()["outcome"], {"actual": 1, "entry_open": 60, "exit_close": 61}
        )
        listing = self.client.get("/public-api/reports")
        report = self.client.get("/public-api/reports/76")
        self.assertEqual(report.json()["decision"], "BUY")
        self.assertIn("62,800원", report.json()["sections"][1]["text"])
        self.assertIn("7.5%", report.json()["sections"][1]["text"])
        self.assertNotIn("sections", listing.json()["reports"][0])
        for response in (overview, detail, listing, report):
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("PRIVATE_", response.text)
            self.assertIn("nosniff", response.headers["x-content-type-options"])

    def test_v1_service_worker_retirement(self):
        for path in ("/sw.js", "/sw.js?build=%2Fassets%2Findex-CCH7LmLo.js"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("javascript", response.headers["content-type"])
            self.assertIn("no-store", response.headers["cache-control"])
            self.assertIn("self.registration.unregister()", response.text)
            self.assertNotIn("clear-site-data", response.headers)
        for query in ("foo=1", "build=../../other.js", "build=/assets/index-A.js&build=/assets/index-B.js"):
            self.assertEqual(self.client.get("/sw.js?" + query).status_code, 400)
        self.assertEqual(self.reader.call_count, 0)

    def test_unknown_ids_and_queries_do_not_trigger_unbounded_internal_reads(self):
        for i in range(51, 71):
            self.assertEqual(self.client.get(f"/public-api/cases/{i}").status_code, 404)
            self.assertEqual(
                self.client.get(f"/public-api/reports/{i}").status_code, 404
            )
        self.assertEqual(self.reader.call_count, 2)
        self.assertEqual(
            self.client.get("/public-api/overview?limit=99999999").status_code, 400
        )
        self.assertEqual(
            self.client.get("/public-api/cases/" + "8" * 5000).status_code, 404
        )
        self.assertEqual(self.reader.call_count, 2)

    def test_private_routes_methods_and_assets(self):
        self.assertEqual(
            self.client.get("/healthz").json(),
            {"service": "forecast-lab-public", "ok": True},
        )
        for path in (
            "/docs",
            "/redoc",
            "/openapi.json",
            "/research/lab.js",
            "/admin",
        ):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        for method in ("HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual(
                self.client.request(method, "/public-api/reports").status_code, 405
            )
        for path in (
            "/",
            "/?case=10",
            "/research/",
            "/research/?case=10",
            "/lab.js?v=20261124-5",
            "/research/workspace-tokens.css?v=20261124-1",
            "/public.css",
            "/public.js",
        ):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.reader.assert_not_called()
        with self.assertRaises(ValueError):
            read_upstream("/admin")

    def test_private_errors_hidden_and_briefly_cached(self):
        self.reader.side_effect = RuntimeError("PRIVATE_TRACE")
        for _ in range(2):
            response = self.client.get("/public-api/overview")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("PRIVATE_TRACE", response.text)
        self.reader.assert_called_once()

    def test_concurrent_reads_coalesce_and_bound_fanout(self):
        cache = ProjectionCache()
        started, release = Event(), Event()
        calls = []

        def work(key):
            calls.append(key)
            if len(calls) == 4:
                started.set()
            release.wait(3)
            return key

        with ThreadPoolExecutor(max_workers=6) as pool:
            jobs = [pool.submit(cache.get, i, lambda i=i: work(i)) for i in range(4)]
            self.assertTrue(started.wait(3))
            duplicate = pool.submit(cache.get, 0, lambda: work(0))
            with self.assertRaises(HTTPException):
                cache.get(4, lambda: work(4))
            release.set()
            self.assertEqual([f.result() for f in jobs], [0, 1, 2, 3])
            self.assertEqual(duplicate.result(), 0)
            self.assertCountEqual(calls, [0, 1, 2, 3])

    def test_public_indicators_skip_ambiguous_targets_and_private_identifiers(self):
        from tradingagents.forecast_lab.public_projection import reported_facts

        self.assertEqual(
            reported_facts(
                {
                    "market_report": "목표 종가는 900달러로 설정했다. 비공개종가는 300원으로 계산했다. 종가는 $35 이상이면 검토한다. "
                    "RSI는 24.1에서 35.7로 올라갔다. ATR은 $1.83으로 집계했다."
                }
            ),
            ["RSI 변화 24.1 → 35.7", "ATR 1.83달러"],
        )
