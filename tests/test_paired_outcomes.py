import unittest
from types import SimpleNamespace
import pandas as pd
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from tradingagents.memory.hybrid_memory import HybridMemory
from tradingagents.rag_validator.outcome import _decision_pair, _evidence, _load_bars


PAIR = {"reflection_id": 5, "before": {"action": "SELL", "shares": 9},
        "after": {"action": "BUY", "shares": 12}, "cash": 25, "holdings": .75}
ROW = {"created_at": datetime(2024, 11, 27, 2, tzinfo=timezone.utc), "market": "us", "ticker":"TEST"}


class PairedOutcomeTests(unittest.TestCase):
    def test_exchange_holiday_timezone_and_fractional_caps(self):
        def bars(ticker, days, tz):
            self.assertEqual([d.day for d in days], [27, 29, 2, 3, 4])
            return {day: (10, 12, 0) for day in days}, {}

        with patch("tradingagents.rag_validator.outcome._load_bars", side_effect=bars):
            self.assertIsNone(_evidence(ROW, PAIR, date(2024, 12, 4), {}))
            delta, evidence = _evidence(ROW, PAIR, date(2024, 12, 5), {})
        self.assertEqual(delta, 1)
        self.assertEqual(evidence["before_signed_shares"], -.75)
        self.assertEqual(evidence["after_signed_shares"], 2.5)
        self.assertEqual(evidence["gross_difference"], 6.5)

    def test_crypto_and_unknown_markets_never_use_equity_sessions(self):
        with patch("tradingagents.rag_validator.outcome._load_bars") as load:
            for market, ticker in (("us", "BTC-USD"), ("crypto", "BTC"), ("other", "XYZ")):
                row = {**ROW, "market":market, "ticker":ticker}
                self.assertIsNone(_evidence(row, PAIR, date(2024, 12, 5), {}))
            load.assert_not_called()

    def test_chart_type_and_venue_are_verified_without_another_request(self):
        day = date(2024, 12, 2)
        with patch("tradingagents.rag_validator.outcome.yf.Ticker") as factory:
            ticker = factory.return_value
            ticker.history.return_value = pd.DataFrame(
                {"Open":[1.5], "Close":[2.0], "Stock Splits":[0]}, index=pd.to_datetime([day]))
            for kind, venue, expected in (("ETF","America/New_York",True),
                                         ("EQUITY","America/New_York",True),
                                         ("INDEX","America/New_York",False),
                                         ("MUTUALFUND","America/New_York",False),
                                         ("EQUITY","America/Toronto",False),
                                         (None,None,False)):
                ticker._price_history = SimpleNamespace(_history_metadata={
                    "instrumentType":kind, "exchangeTimezoneName":venue})
                bars, _ = _load_bars("TEST", (day,), "America/New_York")
                self.assertEqual(bool(bars), expected)
            ticker.get_history_metadata.assert_not_called()

    def test_gaps_and_splits_defer_without_shifting_window(self):
        for fault in ("missing", "split"):
            def bars(ticker, days, tz):
                result = {d: (10, 8, 0) for d in days}
                if fault == "split":
                    result[days[2]] = (10, 8, 2)
                else:
                    del result[days[2]]
                return result, {}
            with patch("tradingagents.rag_validator.outcome._load_bars", side_effect=bars):
                self.assertIsNone(_evidence(ROW, PAIR, date(2024, 12, 20), {}))

    def test_pairs_require_supplied_citation_and_finite_snapshots(self):
        docs = {"memories":[{"reflection_id":5,"matched_situation":"lesson"}],"decision_pair_v1":PAIR,
                "applied_reflection_ids":[5]}
        self.assertEqual(_decision_pair(docs), PAIR)
        self.assertIsNone(_decision_pair({**docs,"memories":[]}))
        for malformed in (None, [], "bad", {**docs, "applied_reflection_ids":[True]},
                          {**docs, "applied_reflection_ids":[]}, {**docs, "applied_reflection_ids":[5, 5]},
                          {**docs, "memories":docs["memories"] * 2}):
            self.assertIsNone(_decision_pair(malformed))
        for patch_pair in ({"cash":float("nan")},{"cash":10**400},{"holdings":-1},{"reflection_id":8}):
            self.assertIsNone(_decision_pair({**docs,"decision_pair_v1":{**PAIR,**patch_pair}}))

    def test_outcome_reranks_only_relevance_neighbours(self):
        memory = HybridMemory.__new__(HybridMemory)
        memory.reflection_repo = Mock()
        memory.reflection_repo.outcome_scores.return_value = {1:49,2:51,3:100}
        rows = [(1, 1.0), (2, .995), (3, .5)]
        self.assertEqual(memory._rank_close_matches(rows, "reflections"), [rows[1], rows[0], rows[2]])
        self.assertEqual(memory._rank_close_matches(rows, "portfolio_reflections"), rows)
