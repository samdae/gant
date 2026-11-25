import unittest

from tradingagents.forecast_lab.public_research import prices


class PublicChartVolumeTests(unittest.TestCase):
    def test_frozen_trade_volume_parity_and_rejections(self):
        day = "2026-11-24"
        for value, expected in [(122309000.0, 122309000), (7, 7), (0.0, 0),
                                (float(2**53 - 1), 2**53 - 1), (None, None),
                                (True, None), ("10", None), (0.5, None),
                                (-1.0, None), (float(2**53), None),
                                (float("nan"), None), (float("inf"), None)]:
            with self.subTest(value=value):
                private = {"date": day, "close": 213.05, "volume": value}
                public, = prices([private], day)
                self.assertEqual(public["volume"], expected)
                if expected is not None:
                    self.assertIs(type(public["volume"]), int)
                    self.assertEqual(public["volume"], private["volume"])
        self.assertIsNone(prices([{"date": day, "close": 10}], day)[0]["volume"])
