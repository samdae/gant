"""Public console is an enumerated, read-only projection of the simulated account."""

import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from tradingagents.forecast_lab.console_public_reads import (
    install_console_reads,
    public_narrative,
)


class PublicConsoleTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.data = {
            "/workspace-api/reports?ticker=KO&limit=20": [],
            "/workspace-api/reports?limit=20&ticker=KO": [
                {
                    "id": 7,
                    "ticker": "KO",
                    "stored_decision_position": "BUY",
                    "final_trade_decision": "종가가 전일보다 상승했습니다. **근거**는 거래량입니다.",
                    "fundamentals_report": "매출은 11% 늘었습니다.",
                    "market_report": "영업이익률은 7.5%입니다.",
                    "pa_opinion": "Bearer PRIVATE_CREDENTIAL",
                    "rag_docs": {"secret": "PRIVATE_TRACE"},
                    "execution_trades": [
                        {
                            "action": "BUY",
                            "shares": 1.5,
                            "price": 123,
                            "currency": "USD",
                            "broker": "PRIVATE_BROKER",
                        }
                    ],
                }
            ],
            "/workspace-api/positions/market": [
                {
                    "position_id": 8,
                    "ticker": "KO",
                    "shares": 1.5,
                    "avg_cost": 110,
                    "private": "PRIVATE_X",
                }
            ],
            "/workspace-api/positions/closed": [],
            "/workspace-api/positions/8": {
                "position": {"id": 8, "ticker": "KO", "shares": 1.5},
                "trades": [],
                "reports": [],
            },
            "/workspace-api/portfolio/config": {
                "config": {
                    "initial_capital": 1000,
                    "available_cash": 550,
                    "total_fund": 1250,
                    "base_currency": "USD",
                    "status": "active",
                    "fee_enabled": False,
                    "private": "PRIVATE_CFG",
                }
            },
            "/workspace-api/portfolio/holdings": {
                "holdings": [
                    {"ticker": "KO", "current_value_base": 125, "shares": 1.5}
                ],
                "base_currency": "USD",
            },
            "/workspace-api/schedules?limit=100": [
                {
                    "ticker": "KO",
                    "interval_days": 2,
                    "latest_cycle": {
                        "id": 8,
                        "status": "failed",
                        "error_message": "PRIVATE_TRACE",
                    },
                }
            ],
            "/workspace-api/metrics": {"by_currency": {"USD": {"total_pnl": 21}}},
            "/workspace-api/queue": {"pending": ["KO"], "running": None, "total": 1},
            "/workspace-api/health": {
                "status": "healthy",
                "scheduler_running": True,
                "queue_length": 1,
            },
            "/workspace-api/schedules/summary": {"total": 2, "done": 1},
            "/workspace-api/activity?limit=100": [],
            "/workspace-api/reports/tickers": [],
        }

        def reader(path):
            self.calls.append(path)
            return self.data[path]

        self.app = FastAPI()
        install_console_reads(self.app, reader)
        self.client = TestClient(self.app)

    def test_original_narrative_and_simulated_balances_with_explicit_fields(self):
        item = self.client.get("/workspace-api/reports?ticker=KO&limit=1").json()[0]
        self.assertIn("**근거**", item["final_trade_decision"])
        self.assertEqual(item["fundamentals_report"], "매출은 11% 늘었습니다.")
        self.assertNotIn("PRIVATE", str(item))
        self.assertEqual(item["execution_trades"][0]["shares"], 1.5)
        cfg = self.client.get("/workspace-api/portfolio/config").json()["config"]
        self.assertEqual(cfg["available_cash"], 550)
        self.assertNotIn("private", cfg)
        self.assertEqual(
            self.client.get("/workspace-api/positions/8").json()["position"]["id"], 8
        )
        self.assertNotIn(
            "PRIVATE", self.client.get("/workspace-api/schedules?limit=100").text
        )
        self.assertEqual(
            self.client.get("/workspace-api/search/tickers?q=코카콜라").json()[0][
                "symbol"
            ],
            "KO",
        )

    def test_unknown_targets_queries_jobs_and_nonscalar_data(self):
        for url in (
            "live/KO/events",
            "schedules/KO/cycles/3/events",
            "retrospective/analyze",
            "queue/delete",
            "search",
            "admin",
        ):
            self.assertEqual(self.client.get("/workspace-api/" + url).status_code, 404)
        for url in (
            "reports?url=http://other.test",
            "reports?limit=1&limit=20",
            "schedules?limit=10000",
        ):
            self.assertEqual(self.client.get("/workspace-api/" + url).status_code, 400)
        self.assertEqual(
            self.client.post("/workspace-api/schedules", json={}).status_code, 405
        )
        self.assertEqual(self.calls, [])
        self.assertEqual(
            self.client.get("/workspace-api/positions/999").status_code, 404
        )
        self.assertNotIn("/workspace-api/positions/999", self.calls)

    def test_narrative_projection_rejects_operational_material_preserves_analysis(self):
        for private in (
            "OPENAI_API_KEY=hidden",
            "postgresql://operator:pass@host/db",
            "Traceback (most recent call last):",
            "C:\\Users\\name\\.env",
            "http://127.0.0.1/private",
            "secret_key: abc",
            "<script>hello()</script>",
            '{"role":"tool","content":"internal"}',
            "system: hidden instructions",
            "server 192.168.1.1",
        ):
            with self.subTest(private=private):
                self.assertIsNone(public_narrative(private))
        prose = "RSI는 35에서 41로 회복했습니다.\n\n- **거래량**은 전일 대비 12% 늘었습니다."
        self.assertEqual(public_narrative(prose), prose)

    def test_cold_dashboard_burst_is_queued_and_capped(self):
        lock = Lock()
        active = peak = 0

        def reader(path):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.12)
                return self.data[path]
            finally:
                with lock:
                    active -= 1

        app = FastAPI()
        install_console_reads(app, reader)
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=9) as threads:
            paths = [
                "metrics",
                "positions/market",
                "health",
                "queue",
                "schedules/summary",
                "portfolio/config",
                "portfolio/holdings",
                "activity",
                "reports/tickers",
            ]
            results = list(
                threads.map(lambda path: client.get("/workspace-api/" + path), paths)
            )
        self.assertEqual([r.status_code for r in results], [200] * len(paths))
        self.assertLessEqual(peak, 4)
