import json
import unittest
from datetime import UTC, datetime
from unittest.mock import Mock

from tradingagents.forecast_lab.incumbent import IncumbentCollector, match


class IncumbentTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "id": 1,
            "ticker": "SPY",
            "market": "us",
            "data_session": "2026-03-02",
            "entry_open_at": "2026-03-03T14:30:00+00:00",
        }
        self.clock = datetime(2026, 3, 2, 22, 30, tzinfo=UTC)
        self.forecast = {
            "p_up": 0.7,
            "judge_model": "production-judge",
            "market_data_date": "2026-03-02",
        }
        self.row = {
            "id": 4,
            "ticker": "SPY",
            "created_at": "2026-03-02T22:00:00+00:00",
            "pipeline_strategy": json.dumps({"forecast_5s": self.forecast}),
        }

    def test_strict_snapshot_and_publication(self):
        value = match(self.case, self.row, self.clock)
        self.assertEqual(value["source_report_id"], 4)
        self.assertEqual(value["probability"], 0.7)
        for key, bad in (
            ("p_up", True),
            ("p_up", "0.7"),
            ("p_up", float("nan")),
            ("judge_model", ""),
            ("market_data_date", "2026-03-01"),
        ):
            row = dict(
                self.row,
                pipeline_strategy={"forecast_5s": dict(self.forecast, **{key: bad})},
            )
            self.assertIsNone(match(self.case, row, self.clock))
        for stamp in (
            "2026-03-02T10:00:00+00:00",
            "2026-03-02T22:00:00",
            "2026-03-02T22:31:00+00:00",
        ):
            self.assertIsNone(
                match(self.case, dict(self.row, created_at=stamp), self.clock)
            )
        self.assertIsNone(
            match(
                self.case, self.row, datetime.fromisoformat(self.case["entry_open_at"])
            )
        )
        day_of_open = datetime(2026, 3, 3, 13, tzinfo=UTC)
        self.assertIsNone(
            match(
                self.case,
                dict(self.row, created_at=day_of_open.isoformat()),
                day_of_open,
            )
        )
        self.assertIsNone(match(self.case, dict(self.row, ticker="QQQ"), self.clock))

    def test_source_outage_does_not_block_each_ticker_and_latest_valid_wins(self):
        store = Mock()
        store.record_reference.return_value = True
        fetch = Mock(
            return_value=[
                self.row,
                dict(self.row, id=5),
                dict(self.row, id=6, ticker="QQQ"),
            ]
        )
        collector = IncumbentCollector(store, fetch, lambda: self.clock)
        self.assertEqual(collector.capture([self.case]), 1)
        self.assertEqual(store.record_reference.call_args.kwargs["source_report_id"], 5)
        fetch.side_effect = ConnectionRefusedError()
        self.assertEqual(collector.capture([self.case, self.case]), 0)
        self.assertEqual(collector.capture([self.case]), 0)
        self.assertEqual(fetch.call_count, 2)
