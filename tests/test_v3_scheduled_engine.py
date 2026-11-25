import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from tradingagents.forecast_lab import scheduled_engine as engine
from tradingagents.forecast_lab.issue_collector import parse_export


class ScheduledEngineTests(unittest.TestCase):
    def test_query_and_isolation(self):
        with tempfile.TemporaryDirectory() as root:
            programs = Path(root)
            for name in (
                "last30days-python/Scripts/python.exe",
                "last30days-python/Scripts/yt-dlp.exe",
                "last30days/skills/last30days/scripts/last30days.py",
            ):
                path = programs / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            responses = {
                "schema_version": "1.1",
                "window_days": 30,
                "query": "우리금융지주",
                "source_status": {"youtube": "ok"},
                "results": [
                    {"source": "youtube", "title": "우리금융지주 분기 실적 발표"},
                    {"source": "youtube", "title": "우리 가족의 주식 이야기"},
                ],
            }

            def inspect_command(cmd, payload, timeout, label, **kwargs):
                env = kwargs["env"]
                self.assertNotIn("FORECAST_LAB_DSN", env)
                self.assertNotIn("OPENAI_API_KEY", env)
                self.assertEqual(env["LAST30DAYS_CONFIG_DIR"], kwargs["cwd"])
                self.assertEqual(env["FROM_BROWSER"], "off")
                self.assertIn("--no-browser-cookies", cmd)
                self.assertEqual(cmd[cmd.index("--search") + 1], "youtube")
                self.assertEqual(cmd[cmd.index("--days") + 1], "30")
                query = json.loads(payload)["subqueries"][0]["search_query"]
                self.assertEqual(query, "우리금융지주 실적 발표")
                return json.dumps(responses)

            with (
                patch.dict(
                    os.environ, {"SystemRoot": root, "OPENAI_API_KEY": "unused"}
                ),
                patch.object(engine, "bounded_run", side_effect=inspect_command),
            ):
                state, rows = engine._collect_source(
                    "youtube", "316140.KS", "kr", "우리금융지주", programs
                )
                self.assertEqual((state, len(rows)), ("ok", 1))
                responses["query"] = "unrelated"
                with self.assertRaises(engine.EngineFailure):
                    engine._collect_source(
                        "youtube", "316140.KS", "kr", "우리금융지주", programs
                    )

    def test_timeout_preserves_other_source_and_verified_origin_date(self):
        row = {
            "source": "hackernews",
            "url": "https://news.ycombinator.com/item?id=1983",
            "published_at": "2026-11-20",
            "title": "Nvidia earnings",
            "ignored": "external payload",
        }

        def collect(source, *_):
            if source == "youtube":
                raise TimeoutError()
            return "ok", [row]

        with (
            patch.dict(os.environ, {"LOCALAPPDATA": "unused"}),
            patch.object(engine, "_collect_source", side_effect=collect),
        ):
            report = engine.run_export("NVDA", "us")
        self.assertTrue(engine.has_source_failure(report))
        self.assertEqual(
            report["source_status"], {"youtube": "timeout", "hackernews": "ok"}
        )
        rows = parse_export(
            json.dumps(report), datetime(2026, 11, 25, tzinfo=UTC), "NVDA"
        )
        self.assertEqual(len(rows), 1)
        self.assertNotIn("ignored", report["results"][0])
        self.assertFalse(
            engine.has_source_failure(
                {"source_status": dict.fromkeys(engine.SOURCES, "no-results")}
            )
        )
        self.assertTrue(
            engine.has_source_failure({"source_status": {"hackernews": "no-results"}})
        )

    def test_title_identifies_issuer_and_subject(self):
        self.assertTrue(
            engine._relevant(
                "SK Hynix announces quarterly revenue", "000660.KS", "SK하이닉스"
            )
        )
        self.assertTrue(
            engine._relevant("현대차의 주가 전망", "005380.KS", "현대자동차")
        )
        self.assertFalse(engine._relevant("What I bought at Walmart", "WMT", "Walmart"))
        self.assertFalse(
            engine._relevant(
                "A browser extension to spy on stock prices", "SPY", "SPDR S&P 500 ETF"
            )
        )
        self.assertFalse(engine._relevant("Tesla's stock rose", "KO", "Coca-Cola"))
        self.assertFalse(
            engine._relevant(
                "우리금융지주 주가 폭등! 세력의 속셈", "316140.KS", "우리금융지주"
            )
        )
        self.assertTrue(
            engine._relevant("SPY ETF price rises", "SPY", "SPDR S&P 500 ETF")
        )
        self.assertTrue(engine._relevant("AAPL earnings report", "AAPL", "AAPL"))
        self.assertEqual(engine._issuer("BTC-USD", "us"), "Bitcoin")
        self.assertIn("inflation", engine.MARKET_QUERIES["SCHP"])
