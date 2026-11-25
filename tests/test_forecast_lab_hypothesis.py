import unittest

from test_forecast_lab_engine import Bars, at
from tradingagents.forecast_lab import hypothesis
from tradingagents.forecast_lab.engine import ForecastEngine


class HypothesisTests(unittest.TestCase):
    def setUp(self):
        self.clock = at("2026-11-25T22:00:00+00:00")
        self.engine = ForecastEngine(provider=Bars(), clock=lambda: self.clock)
        self.snapshot = self.engine.snapshot("XYZ", "us")

    def test_reference_prices_provenance_and_unchanged_forecast_evidence(self):
        snap = self.snapshot
        card = snap["hypothesis"]
        self.assertEqual(
            card["conditions"][0]["threshold"],
            max(b["high"] for b in snap["bars"][-5:]),
        )
        self.assertEqual(
            card["conditions"][1]["threshold"], min(b["low"] for b in snap["bars"][-5:])
        )
        self.assertEqual(card["reference_close"], snap["bars"][-1]["close"])
        self.assertEqual(card["currency"], "USD")
        plain = {k: v for k, v in snap.items() if k != "hypothesis"}
        a = self.engine.forecast(snap, "baseline")
        b = self.engine.forecast(plain, "baseline")
        self.assertEqual(a["probability"], b["probability"])
        self.assertEqual(
            a["audit"]["market_input_sha256"], b["audit"]["market_input_sha256"]
        )
        for bad in (
            {**snap, "currency": "KRW"},
            {**snap, "bars": [*snap["bars"], snap["bars"][-1]]},
        ):
            with self.assertRaises(ValueError):
                hypothesis.freeze(bad, snap["history_sessions"][-5:])

    def test_equality_is_not_crossing_and_earliest_equal_low_is_recorded(self):
        c = self.snapshot["hypothesis"]
        high, low = [r["threshold"] for r in c["conditions"]]
        bars = [
            {"close": v, "date": d}
            for v, d in zip([low, low, high, high, high], self.snapshot["sessions"])
        ]
        result = hypothesis.evaluate(c, bars)
        self.assertEqual([r["status"] for r in result], ["not_met", "not_met"])
        self.assertEqual(result[1]["observed_session"], bars[0]["date"])
        bars[-1]["close"] += 1
        bars[1]["close"] -= 1
        self.assertEqual(
            [r["status"] for r in hypothesis.evaluate(c, bars)], ["met", "met"]
        )
        for outcome, expected in (
            (None, "pending"),
            ({"status": "excluded"}, "unavailable"),
        ):
            view = hypothesis.public_hypothesis(
                hypothesis.detail(self.snapshot, outcome)
            )
            self.assertEqual(
                [r["status"] for r in view["conditions"]], [expected, expected]
            )
        self.assertIsNone(hypothesis.detail({}, None))

    def test_public_read_revalidates_issue_url_and_pending_condition_state(self):
        from tradingagents.forecast_lab.public_projection import case_evidence

        snap = self.snapshot
        detail = hypothesis.detail(snap, None)
        detail["conditions"][0].update(
            status="met", observed_value=999, observed_session=snap["sessions"][-1]
        )
        raw = {
            "status": "pending",
            "ticker": snap["ticker"],
            "data_session": snap["data_session"],
            "snapshot": snap,
            "hypothesis": detail,
            "issues": {
                "status": "available",
                "source": "Google News RSS",
                "as_of": snap["observed_at"],
                "collected_at": None,
                "items": [
                    {
                        "title": "fixture",
                        "publisher": "fixture",
                        "source": "Google News RSS",
                        "url": "http://localhost/admin",
                        "first_seen_at": "2026-11-24T00:00:00Z",
                        "published_at": "2026-11-23T00:00:00Z",
                    }
                ],
            },
        }
        projection = case_evidence(raw)
        self.assertEqual(projection["issues"]["items"], [])
        visible = projection["hypothesis"]["conditions"][0]
        self.assertEqual(
            (visible["status"], visible["observed_value"]), ("pending", None)
        )
        raw["issues"]["as_of"] = "2026-11-26T22:00:00Z"
        self.assertIsNone(case_evidence(raw)["issues"])
