import unittest

from tradingagents.api.performance import calculate_performance


def fills(events, *, position=1, currency="USD", status="closed", shares=0, avg_cost=None):
    return [
        dict(id=position, ticker="TEST", status=status, shares=shares, avg_cost=avg_cost,
             currency=currency, return_pct=None, action=action, fill_shares=qty, price=price,
             fill_currency=currency)
        for action, qty, price in events
    ]


class PerformanceTests(unittest.TestCase):
    def test_sale_uses_average_cost_at_that_sale(self):
        rows = fills([("BUY", 10, 100), ("SELL", 5, 120), ("BUY", 5, 200), ("SELL", 10, 180)])
        stats = calculate_performance(rows, {})["USD"]
        self.assertEqual(stats.total_realized_pnl, 400)
        self.assertEqual(stats.realized_cost, 2000)
        self.assertEqual(stats.total_return_pct, 20)
        self.assertEqual(stats.incomplete_positions, 0)

    def test_partial_legacy_close_and_currency_separation(self):
        rows = fills([("BUY", 10, 100), ("SELL", 4, 110)])
        rows += fills([("BUY", 1, 100000), ("SELL", 1, 90000)], position=2, currency="KRW")
        results = calculate_performance(rows, {})
        self.assertEqual(results["USD"].total_realized_pnl, 40)
        self.assertEqual(results["USD"].total_return_pct, 10)
        self.assertEqual(results["USD"].incomplete_positions, 1)
        self.assertEqual(results["KRW"].total_return_pct, -10)

    def test_reset_generates_no_sale(self):
        rows = fills([("BUY", 10, 100), ("SELL", 1, 110)], status="reset")
        stats = calculate_performance(rows, {})["USD"]
        self.assertEqual(stats.realized_cost, 100)
        self.assertEqual(stats.total_pnl, 10)
        self.assertEqual(stats.active_positions + stats.closed_positions, 0)

    def test_excess_sales_only_count_matched_quantity(self):
        rows = fills([("BUY", 1, 100), ("SELL", 5, 120)])
        stats = calculate_performance(rows, {})["USD"]
        self.assertEqual(stats.total_pnl, 20)
        self.assertEqual(stats.incomplete_positions, 1)

    def test_open_position_realized_and_unpriced(self):
        rows = fills([("BUY", 10, 100), ("SELL", 4, 120)], status="active", shares=6, avg_cost=100)
        stats = calculate_performance(rows, {"TEST": 110})["USD"]
        self.assertEqual(stats.total_pnl, 140)
        self.assertEqual(stats.total_return_pct, 14)
        stats = calculate_performance(rows, {})["USD"]
        self.assertIsNone(stats.total_return_pct)
        self.assertEqual(stats.total_realized_pnl, 80)
        self.assertEqual(stats.unpriced_positions, 1)

    def test_empty_account(self):
        self.assertEqual(calculate_performance([], {}), {})


if __name__ == "__main__":
    unittest.main()
