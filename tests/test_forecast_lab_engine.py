import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import exchange_calendars as calendars
from tradingagents.forecast_lab.engine import (
    ForecastEngine,
    ForecastUnavailable,
    _baseline,
    _parse_probability,
    _risk_forecast,
)


def at(value):
    return datetime.fromisoformat(value).astimezone(UTC)


class Bars:
    def __init__(self):
        self.missing = set()
        self.split = set()
        self.wrong_market = False
        self.calls = []

    def fetch(self, ticker, start, end):
        self.calls.append((ticker, start, end))
        name = "XKRX" if ticker.endswith(".KS") else "XNYS"
        cal = calendars.get_calendar(name)
        days = [s.date().isoformat() for s in cal.sessions_in_range(start, end)]
        rows = []
        for i, day in enumerate(days):
            if day in self.missing:
                continue
            rows.append(
                {
                    "date": day,
                    "open": 50 + i,
                    "high": 52 + i,
                    "low": 49 + i,
                    "close": 51 + i,
                    "volume": 100,
                    "split": 2 if day in self.split else 0,
                }
            )
        return {
            "symbol": ticker,
            "instrumentType": "ETF",
            "currency": "WRONG" if self.wrong_market else "USD",
            "exchangeTimezoneName": "America/New_York",
            "exchangeName": "PCX",
        }, rows


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.now = at("2026-11-25T22:00:00+00:00")
        self.bars = Bars()
        self.llm = Mock()
        self.engine = ForecastEngine(
            provider=self.bars, clock=lambda: self.now, llm=self.llm, model="fixture"
        )

    def snapshot(self):
        return self.engine.snapshot("XYZ", "us")

    def test_holiday_early_close_and_provider_delay(self):
        case = self.snapshot()
        self.assertEqual(case["data_session"], "2026-11-25")
        self.assertEqual(case["entry_open_at"], "2026-11-27T14:30:00+00:00")
        self.assertEqual(case["exit_date"], "2026-12-03")
        self.assertEqual(case["benchmark"]["status"], "available")
        self.assertEqual(case["baseline"]["windows"], 61)
        self.assertEqual(case["baseline"]["probability"], 62 / 63)
        self.assertTrue(
            all(call[2] <= case["data_session"] for call in self.bars.calls)
        )
        self.now = at("2026-11-27T18:19:59+00:00")
        with self.assertRaises(ForecastUnavailable):
            self.snapshot()
        self.now += timedelta(seconds=1)
        self.assertEqual(self.snapshot()["data_session"], "2026-11-27")

    def test_warmup_and_identity_guard(self):
        self.bars.missing.add("2026-11-25")
        with self.assertRaises(ForecastUnavailable):
            self.snapshot()
        self.bars.wrong_market = True
        with self.assertRaisesRegex(ForecastUnavailable, "metadata"):
            self.snapshot()

    def test_history_no_gap_splicing_or_split_windows(self):
        days = list(range(65))
        bars = {
            i: {"open": 1, "close": 2, "split": 2 if i == 10 else 0}
            for i in days
            if i != 40
        }
        self.assertEqual(_baseline(days, bars)["windows"], 51)

    def test_label_requires_entire_window_and_excludes_split(self):
        case = self.snapshot()
        self.assertIsNone(self.engine.outcome(case))
        self.now = at(case["exit_close_at"]) + timedelta(minutes=20)
        self.bars.missing.add(case["sessions"][2])
        self.assertIsNone(self.engine.outcome(case))
        self.now += timedelta(days=7)
        self.assertEqual(self.engine.outcome(case)["status"], "excluded")
        self.bars.missing.clear()
        self.bars.split.add(case["sessions"][3])
        self.assertEqual(self.engine.outcome(case)["status"], "excluded")
        self.bars.split.clear()
        result = self.engine.outcome(case)
        self.assertEqual(
            (result["actual"], result["entry_open"], result["exit_close"]), (1, 50, 55)
        )

    def test_invalid_probability_and_deadline_after_inference(self):
        for value in ["null", "true", '"0.5"', "1.01", "NaN", "-0.1", "1e999"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _parse_probability('{"probability":' + value + ',"rationale":"x"}')
        case = self.snapshot()

        def slow(_):
            self.now = at(case["entry_open_at"])
            return SimpleNamespace(content='{"probability":0.5,"rationale":"x"}')

        self.llm.invoke.side_effect = slow
        with self.assertRaises(ForecastUnavailable):
            self.engine.forecast(case, "single")

    def test_only_memory_contains_lesson_and_no_forecast_contains_baseline_output(self):
        case = self.snapshot()
        self.llm.invoke.side_effect = [
            SimpleNamespace(content=t)
            for t in [
                "bad",
                '{"probability":0.4,"rationale":"x"}',
                '{"probability":0.7,"rationale":"y"}',
                '{"probability":0.7,"rationale":"y"}',
            ]
        ]
        single = self.engine.forecast(case, "single")
        prior = {
            "id": 1,
            "rationale": "unique prior event",
            "actual": 0,
            "market": case["market"],
            "experiment_version": case["experiment_version"],
            "observed_at": self.now - timedelta(days=2),
            "created_at": self.now - timedelta(days=1),
        }
        memory = self.engine.forecast(case, "memory", prior)
        treatment = self.engine.forecast(case, "memory_sector", prior)
        self.assertEqual(memory["audit"]["prompt_sha256"], treatment["audit"]["prompt_sha256"])
        self.assertEqual(memory["audit"]["market_input_sha256"], single["audit"]["market_input_sha256"])
        self.assertEqual(treatment["model"], memory["model"])
        legacy = dict(case)
        del legacy["retrieval_policy"]
        with self.assertRaises(ValueError):
            self.engine.forecast(legacy, "memory_sector", prior)
        with self.assertRaises(ForecastUnavailable):
            self.engine.forecast(case, "memory", dict(prior, created_at=self.now))
        prompts = [call.args[0] for call in self.llm.invoke.call_args_list]
        self.assertEqual(prompts[-2], prompts[-1])
        self.assertNotIn("classification", prompts[-1])
        self.assertNotIn("retrieval_policy", prompts[-1])
        self.assertNotIn("unique prior event", prompts[0])
        self.assertNotIn('"baseline":', prompts[0])
        self.assertTrue(prompts[-1].startswith(prompts[0]))
        self.assertIn("unique prior event", prompts[-1])
        self.assertEqual(single["audit"]["attempts"], 2)
        self.assertEqual(single["version"], memory["version"])

    def test_original_eight_nodes_risk_judge_probability_and_explicit_target(self):
        case = self.snapshot()

        def answer(messages):
            prompt = messages[-1]["content"]
            if "Risk Management Judge" in prompt:
                self.assertNotIn("report publication date", prompt)
                self.assertIn(case["exit_date"], prompt)
                self.assertIn(case["entry_date"], prompt)
                return SimpleNamespace(
                    content='Reasons\n```strategy_json\n{"forecast_5s":{"p_up":0.31}}\n```'
                )
            return SimpleNamespace(content="trace from the original node")

        self.llm.invoke.side_effect = answer
        result = self.engine.forecast(case, "debate")
        self.assertEqual(result["probability"], 0.31)
        self.assertEqual(
            [n["role"] for n in result["audit"]["debate"]],
            [
                "create_bull_researcher",
                "create_bear_researcher",
                "create_research_manager",
                "create_trader",
                "create_aggressive_debator",
                "create_conservative_debator",
                "create_neutral_debator",
                "create_risk_manager",
            ],
        )
        with self.assertRaises(ValueError):
            _risk_forecast(
                'Reason\n```strategy_json\n{"forecast_5s":{"p_up":true}}\n```'
            )

    def test_uncertain_corporate_action_is_rejected_in_every_window(self):
        real_fetch = self.bars.fetch

        def broken(symbol, *args):
            meta, rows = real_fetch(symbol, *args)
            if symbol == "SPY":
                rows[-1]["adjustment_uncertain"] = True
            return meta, rows

        self.bars.fetch = broken
        case = self.snapshot()
        self.assertEqual(case["benchmark"]["status"], "unavailable")
        self.assertNotIn("benchmark_trend_20d", case["features"])
        with self.assertRaises(ForecastUnavailable):
            self.engine.snapshot("SPY", "us")

        def future(symbol, *args):
            meta, rows = real_fetch(symbol, *args)
            rows[2]["adjustment_uncertain"] = True
            return meta, rows

        self.bars.fetch = future
        self.now = at(case["exit_close_at"]) + timedelta(minutes=21)
        self.assertIn("adjustment", self.engine.outcome(case)["reason"])
        days = list(range(65))
        bars = {
            d: {"open": 1, "close": 2, "split": 0, "adjustment_uncertain": d == 40}
            for d in days
        }
        self.assertEqual(_baseline(days, bars)["windows"], 56)

    def test_revised_calendar_excluded_before_prices_and_future_snapshot_rejected(self):
        case = self.snapshot()
        future = dict(case, observed_at=(self.now + timedelta(minutes=1)).isoformat())
        with self.assertRaisesRegex(ForecastUnavailable, "observed"):
            self.engine.forecast(future, "baseline")
        case["sessions"][1] = case["sessions"][0]
        with self.assertRaisesRegex(ForecastUnavailable, "calendar"):
            self.engine.forecast(case, "single")
        calls = len(self.bars.calls)
        self.now = at(case["exit_close_at"]) + timedelta(minutes=21)
        self.assertIn("calendar", self.engine.outcome(case)["reason"])
        self.assertEqual(len(self.bars.calls), calls)

    def test_watchdog_stops_its_entire_descendant_tree(self):
        import json
        import sys
        import tempfile
        import time
        from pathlib import Path

        from tradingagents.forecast_lab.bounded_process import bounded_run

        with tempfile.TemporaryDirectory() as folder:
            started = Path(folder) / "started"
            survived = Path(folder) / "survived"
            grandchild = (
                "from pathlib import Path; import time; "
                f"Path({str(started)!r}).touch(); time.sleep(1.6); Path({str(survived)!r}).touch()"
            )
            child = (
                "import json,subprocess,sys,time; "
                "subprocess.Popen([sys.executable, '-c', json.load(sys.stdin)]); time.sleep(30)"
            )
            started_at = time.monotonic()
            with self.assertRaises(TimeoutError):
                bounded_run(
                    [sys.executable, "-c", child], json.dumps(grandchild), 1, "fixture"
                )
            self.assertLess(time.monotonic() - started_at, 4)
            self.assertTrue(started.exists())
            time.sleep(1)
            self.assertFalse(survived.exists())

    def test_missing_price_evidence_expires_but_transport_outage_remains_retryable(
        self,
    ):
        from yfinance.exceptions import YFPricesMissingError, YFRateLimitError

        case = self.snapshot()
        self.now = at(case["exit_close_at"]) + timedelta(days=1)
        self.bars.fetch = Mock(
            side_effect=YFPricesMissingError("XYZ", "no weekday observations")
        )
        self.assertIsNone(self.engine.outcome(case))
        self.now += timedelta(days=7)
        self.assertEqual(self.engine.outcome(case)["status"], "excluded")
        self.bars.fetch.side_effect = YFRateLimitError()
        with self.assertRaises(YFRateLimitError):
            self.engine.outcome(case)
