import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

from tradingagents.forecast_lab.classification import catalog_classification, classify
from tradingagents.forecast_lab.worker import Worker


class SectorWorkerTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.now = datetime(2026, 11, 24, 7, tzinfo=UTC)
        self.engine = Mock()
        self.worker = Worker(self.store, self.engine, Mock(), clock=lambda: self.now)
        self.case = {
            "id": 1,
            "snapshot": {
                "entry_open_at": (self.now + timedelta(hours=6)).isoformat(),
                "retrieval_policy": "sector-v1",
            },
            "arms": [{"method": m, "status": "published"} for m in ("baseline", "single", "debate")],
        }
        self.engine.forecast.side_effect = lambda snap, method, memory: {
            "method": method, "memory_id": memory["id"], "probability": 0.5
        }

    def test_catalog_and_unknown(self):
        self.assertEqual(classify("SPY", "ETF")["exposure"], "us_large_cap")
        self.assertEqual(classify("005930.KS", "EQUITY")["industry"], "diversified_electronics")
        self.assertIsNone(classify("009830.KS", "EQUITY")["sector"])
        self.assertEqual(catalog_classification("SPY", "us"), classify("SPY", "ETF"))
        self.assertEqual(catalog_classification("SPY", "kr")["asset_class"], "unknown")
        for key in ("BTC-USD", "UNREGISTERED", "SPY"):
            self.assertEqual(classify(key, "EQUITY")["asset_class"], "unknown")

    def test_catalog_preview_accepts_kosdaq_only_in_korean_market(self):
        with patch.dict("tradingagents.forecast_lab.classification.EQUITIES", {
            "FIXTURE.KQ": ("technology", "semiconductors"),
        }):
            self.assertEqual(catalog_classification("FIXTURE.KQ", "kr")["asset_class"], "equity")
            self.assertEqual(catalog_classification("FIXTURE.KQ", "us")["asset_class"], "unknown")

    def test_same_source_deduplicates_call_and_divergent_source_runs(self):
        for other in (8, 9):
            with self.subTest(other=other):
                self.store.reset_mock()
                self.engine.reset_mock()
                self.store.select_memory.side_effect = [{"id": 8}, {"id": other}]
                self.worker.issue_frozen(self.case, {})
                calls = self.engine.forecast.call_args_list
                if other == 8:
                    self.assertEqual(len(calls), 1)
                    self.store.record_arm.assert_called_with(1, "memory_sector", status="skipped", error="same_memory")
                else:
                    self.assertEqual([c.args[1] for c in calls], ["memory", "memory_sector"])
                    self.assertIs(calls[0].args[0], calls[1].args[0])
                    self.assertEqual(calls[1].kwargs["memory"]["id"], other)

    def test_retry_published_control_and_missing_candidate(self):
        self.case["arms"].append({"method": "memory", "status": "published", "memory_id": 8})
        self.store.select_memory.return_value = None
        self.worker.issue_frozen(self.case, {})
        self.store.record_arm.assert_called_once_with(1, "memory_sector", status="skipped", error="no_eligible_sector_memory")
        self.store.reset_mock()
        self.store.select_memory.return_value = {"id": 8}
        self.worker.issue_frozen(self.case, {})
        self.store.record_arm.assert_called_once_with(1, "memory_sector", status="skipped", error="same_memory")
        self.engine.forecast.assert_not_called()

    def test_failed_control_never_produces_a_comparison(self):
        self.store.select_memory.side_effect = [{"id": 8}, {"id": 9}]
        self.engine.forecast.side_effect = ValueError("mock failed control")
        self.worker.issue_frozen(self.case, {})
        self.assertEqual(self.engine.forecast.call_count, 1)
        self.assertEqual(self.store.record_arm.call_count, 1)
        self.assertEqual(self.store.record_arm.call_args.kwargs["status"], "failed")

    def test_unmarked_cases_and_closed_deadline(self):
        del self.case["snapshot"]["retrieval_policy"]
        self.store.select_memory.return_value = {"id": 8}
        self.worker.issue_frozen(self.case, {})
        self.store.select_memory.assert_called_once_with(1)
        self.store.reset_mock()
        self.now += timedelta(days=1)
        self.case["snapshot"]["retrieval_policy"] = "sector-v1"
        self.worker.issue_frozen(self.case, {})
        self.store.select_memory.assert_not_called()
