import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.evaluate_saved_signals import evaluate, outcome


class SavedSignalTests(unittest.TestCase):
    def test_next_open_fifth_close_and_missing_holiday(self):
        monday = date(2026, 11, 9)
        bars = {monday + timedelta(days=i): (50, 10) for i in range(5)}
        bars[monday + timedelta(days=4)] = (1, 55)
        self.assertEqual(outcome(monday - timedelta(days=3), [bars]), "UP")
        del bars[monday + timedelta(days=2)]
        self.assertIsNone(outcome(monday - timedelta(days=3), [bars]))

    @patch("scripts.evaluate_saved_signals.load_prices")
    def test_us_local_date_latest_abstention_and_paired_baselines(self, prices):
        monday = date(2026, 11, 9)
        prices.return_value = [{monday + timedelta(days=i): (50, 45) for i in range(5)}]
        friday = datetime(2026, 11, 6, 23, tzinfo=timezone.utc)
        row = dict(ticker="A", market="us", created_at=friday, automatic=False,
                   without_position=True, decision_position="BUY")
        rows = [row, dict(row, created_at=friday + timedelta(hours=2), decision_position="HOLD"),
                dict(row, ticker="B", decision_position="SELL"), dict(row, ticker="C", automatic=True),
                dict(row, ticker="BTC-USD")]
        score = evaluate(rows, Path())
        self.assertEqual(score["coverage"]["scored_without_position"], 1)
        self.assertEqual(score["coverage"]["hold_abstention"], 1)
        self.assertEqual(score["coverage"]["same_day_superseded"], 1)
        self.assertEqual(score["coverage"]["automatic_excluded"], 1)
        self.assertEqual(score["coverage"]["crypto_excluded"], 1)
        self.assertEqual(score["paired_accuracy_pct"], {"signal": 100, "always_up": 0, "always_down": 100})

    def test_probability_requires_json_number_in_nested_object(self):
        from scripts.evaluate_saved_signals import forecast_probability

        for strategy in (None, "{", "false", [], {"p_up": 0.5}, {"forecast_5s": []}):
            self.assertIsNone(forecast_probability(strategy))
        for value in ("0.4", True, float("nan"), float("inf"), -0.1, 2):
            self.assertIsNone(forecast_probability({"forecast_5s": {"p_up": value}}))
        self.assertEqual(forecast_probability('{"forecast_5s":{"p_up":0}}'), 0)

    @patch("scripts.evaluate_saved_signals.load_prices")
    def test_paired_brier_includes_hold_flat_and_missing_window(self, prices):
        monday = date(2026, 11, 9)
        bars = {monday + timedelta(days=i): (10, 10) for i in range(5)}
        prices.side_effect = [[bars], [], [bars]]
        row = dict(ticker="A", market="us", created_at=datetime(2026, 11, 6, 23, tzinfo=timezone.utc),
                   automatic=False, without_position=True, decision_position="BUY",
                   pipeline_strategy={"forecast_5s": {"p_up": 1}})
        rows = [row, dict(row, decision_position="HOLD", pipeline_strategy='{"forecast_5s":{"p_up":0.2}}'),
                dict(row, ticker="B"), dict(row, ticker="C", pipeline_strategy=None)]
        score = evaluate(rows, Path())
        forecast = score["forecast_5s"]
        self.assertEqual((forecast["n"], forecast["pending_or_missing_window"]), (1, 1))
        self.assertAlmostEqual(forecast["mean_brier"], 0.04)
        self.assertEqual(forecast["paired_brier_p_0_5"], 0.25)
        self.assertEqual(score["coverage"]["scored"], 1)
