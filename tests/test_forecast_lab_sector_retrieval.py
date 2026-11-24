"""Counterfactual sector evidence uses frozen inputs, never labels or outcomes."""

from copy import deepcopy
import unittest

from tradingagents.forecast_lab.sector_retrieval import sector_candidates


def group(sector="industrials", industry="electrical", asset="equity", exposure=None):
    return {
        "version": "taxonomy-v1",
        "asset_class": asset,
        "sector": sector,
        "industry": industry,
        "exposure": exposure,
    }


def features(trend=0.06, vol=0.021, benchmark=True):
    values = {"trend_20d": trend, "volatility_20d": vol}
    if benchmark:
        values.update(
            benchmark_trend_20d=0.018,
            benchmark_volatility_20d=0.013,
            relative_trend_20d=trend - 0.018,
        )
    return values


class SectorGateTests(unittest.TestCase):
    def setUp(self):
        self.target = {
            "ticker": "267260.KS",
            "snapshot": {"features": features(), "classification": group()},
        }
        self.source = {
            "id": 4,
            "case_id": 50,
            "entry_at": "2026-03-03",
            "exit_at": "2026-03-09",
            "entry_open": 100.0,
            "exit_close": 103.0,
            "ticker": "010120.KS",
            "data_session": "2026-03-02",
            "features": features(0.062),
            "classification": group(),
        }
        self.peer = {
            **self.source,
            "id": 15,
            "ticker": "267260.KS",
            "features": features(0.059),
        }

    def select(self, peers):
        return sector_candidates(self.target, [deepcopy(self.source)], peers)

    def test_distinct_session_sector_peer_and_novel_price_regime(self):
        self.assertEqual(
            self.select([self.peer])[0]["sector_selection_v1"]["basis"], "equity_peer"
        )
        for variants in (
            {"ticker": "010120.KS"},
            {"exit_close": None},
            {"exit_close": 80.0},
            {"exit_close": 100.0},
            {"exit_close": 122.0},
            {"entry_at": "2026-03-04"},
            {"exit_at": "2026-03-10"},
            {"data_session": "2026-03-03"},
            {"classification": group("financials")},
            {"features": features(-0.06)},
            {"features": features(0.14)},
            {"features": features(0.02)},
        ):
            with self.subTest(variants=variants):
                self.assertEqual(self.select([{**self.peer, **variants}]), [])
        self.target["snapshot"]["classification"] = group(industry="machinery")
        self.assertEqual(self.select([{**self.peer, "features": features(0.075)}]), [])
        self.target["snapshot"]["features"] = features(0.20)
        self.assertEqual(self.select([self.peer]), [])

    def test_etf_exposure_unknown_and_missing_core_features(self):
        self.target["snapshot"]["classification"] = group(
            None, None, "etf", "us-large-cap"
        )
        self.source["classification"] = group(None, None, "etf", "us-large-cap")
        self.assertEqual(
            self.select([])[0]["sector_selection_v1"]["basis"], "etf_exposure"
        )
        self.source["classification"]["exposure"] = "gold"
        self.assertEqual(self.select([]), [])
        self.target["snapshot"]["classification"] = self.source["classification"] = (
            group(None, None, "unknown")
        )
        self.assertEqual(self.select([]), [])
        self.source["ticker"] = self.target["ticker"]
        self.assertEqual(
            self.select([])[0]["sector_selection_v1"]["basis"], "same_ticker"
        )
        self.target["snapshot"]["features"] = {}
        self.assertEqual(self.select([]), [])

    def test_watchlist_reference_uses_three_distinct_independent_out_of_sector_equities(
        self,
    ):
        self.target["snapshot"]["features"] = features(benchmark=False)
        self.source["features"] = features(0.062, benchmark=False)
        peer = {**self.peer, "features": features(0.059, benchmark=False)}
        others = [
            {
                **peer,
                "id": i,
                "ticker": ticker,
                "classification": group(sector),
                "features": features(trend, benchmark=False),
            }
            for i, (ticker, sector, trend) in enumerate(
                [
                    ("005930.KS", "technology", 0.01),
                    ("000660.KS", "technology", 0.012),
                    ("316140.KS", "financials", 0.02),
                ],
                start=30,
            )
        ]
        diag = self.select([peer, *others])[0]["sector_selection_v1"]
        self.assertEqual(
            (diag["peer_reference"], diag["reference_count"]), ("watchlist_median", 3)
        )
        self.assertAlmostEqual(diag["source_relative_trend_20d"], 0.05)
        for invalid in (
            others[:2],
            [*others[:2], others[1]],
            [dict(r, classification=group("technology")) for r in others],
            [*others[:2], dict(others[2], classification=None)],
        ):
            self.assertEqual(self.select([peer, *invalid]), [])
