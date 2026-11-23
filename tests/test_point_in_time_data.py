import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pandas as pd

from tradingagents.dataflows import alpha_vantage_fundamentals as av
from tradingagents.dataflows import alpha_vantage_news, macro_collector as macro, stockstats_utils
from tradingagents.dataflows import y_finance, yfinance_news


class PointInTimeTests(unittest.TestCase):
    def test_news_filters_before_limiting_using_utc_dates(self):
        items = [
            {"title": "unknown"},
            {"content": {"title": "next", "pubDate": "2024-04-02T00:00:00Z"}},
            {"content": {"title": "utc next", "pubDate": "2024-04-01T23:30:00-04:00"}},
            {"title": "in range", "providerPublishTime": datetime(2024, 4, 1, tzinfo=timezone.utc).timestamp()},
        ]
        with patch.object(yfinance_news.yf, "Search", return_value=Mock(news=items)):
            output = yfinance_news.get_global_news_yfinance("2024-04-01", limit=1)
        with patch.object(yfinance_news.yf, "Ticker") as ticker:
            ticker.return_value.get_news.return_value = items
            single = yfinance_news.get_news_yfinance("T", "2024-04-01", "2024-04-01")
        for result in [output, single]:
            self.assertIn("in range", result)
            self.assertNotIn("next", result)
            self.assertNotIn("unknown", result)

    def test_daily_history_bounds_match_header(self):
        bars = pd.DataFrame({"Close": [1, 2]}, index=pd.to_datetime(["2024-04-01", "2024-04-02"]))
        with patch.object(y_finance.yf, "Ticker") as ticker:
            ticker.return_value.history.return_value = bars
            result = y_finance.get_YFin_data_online("T", "2024-04-01", "2024-04-01")
            ticker.return_value.history.assert_called_once_with(start="2024-04-01", end="2024-04-02")
        self.assertIn("2024-04-01,1", result)
        self.assertNotIn("2024-04-02,2", result)

    def test_indicator_download_and_cache_share_cutoff(self):
        dates = pd.date_range("2024-04-01", periods=4, name="Date")
        frame = pd.DataFrame({col: [1, 2, 3, 4] for col in ("Close", "Open", "Low", "High", "Volume")}, index=dates)
        with tempfile.TemporaryDirectory() as directory, patch.object(stockstats_utils.yf, "download", return_value=frame) as fetch:
            for _ in range(2):
                data = stockstats_utils.load_price_window("T", dates[2], 1, {"data_cache_dir": directory})
                self.assertEqual(list(data["Date"]), list(dates[1:3]))
            fetch.assert_called_once()

    def test_historical_macro_excludes_same_day_us_close_and_live_info(self):
        bars = pd.DataFrame({"Close": [4.5, 98.0]}, index=pd.to_datetime(["2024-04-01", "2024-04-02"]))
        with patch.object(macro.yf, "Ticker") as ticker, patch.dict(macro._macro_cache, clear=True):
            ticker.return_value.history.return_value = bars
            result = macro.collect_macro_context("T", "kr", "2024-04-02")
            self.assertIn("4.50", result)
            self.assertNotIn("98.00", result)
            self.assertNotIn("T", [call.args[0] for call in ticker.call_args_list])
            self.assertEqual(ticker.return_value.history.call_args.kwargs["end"], "2024-04-02")
            us = macro.collect_macro_context("T", "us", "2024-04-02")
            self.assertIn("4.50%", us)

    def test_historical_fundamentals_do_not_fetch_current_snapshots(self):
        with patch.object(av, "_make_api_request") as fetch, patch.object(y_finance.yf, "Ticker") as ticker:
            for vendor in [av, y_finance]:
                for name in ["get_fundamentals", "get_balance_sheet", "get_cashflow", "get_income_statement"]:
                    self.assertIn("unavailable", getattr(vendor, name)("T", curr_date="2020-01-01"))
            fetch.assert_not_called()
            ticker.assert_not_called()

    def test_explicit_news_time_preserved_and_date_only_includes_end_day(self):
        with patch.object(alpha_vantage_news, "_make_api_request") as fetch:
            for end, expected in [("2024-04-01", "20240401T2359"), ("2024-04-01 15:30", "20240401T1530")]:
                alpha_vantage_news.get_news("T", "2024-03-01", end)
                self.assertEqual(fetch.call_args.args[1]["time_to"], expected)

    def test_toolnode_enforces_context_for_omitted_and_future_dates(self):
        from langchain_core.messages import AIMessage
        from langgraph.graph import MessagesState, START, StateGraph
        from langgraph.prebuilt import ToolNode
        from tradingagents.agents.utils import fundamental_data_tools as fundamentals, news_data_tools as news
        from tradingagents.runtime_context import analysis_date_scope, bounded_analysis_date

        graph = StateGraph(MessagesState)
        graph.add_node("tools", ToolNode([fundamentals.get_balance_sheet, news.get_global_news, news.get_insider_transactions]))
        graph.add_edge(START, "tools")
        app = graph.compile()
        message = AIMessage(content="", tool_calls=[
            {"id": "1", "name": "get_balance_sheet", "args": {"ticker": "T"}},
            {"id": "2", "name": "get_global_news", "args": {"curr_date": "2025-01-01"}},
            {"id": "3", "name": "get_insider_transactions", "args": {"ticker": "T"}},
        ])
        with analysis_date_scope("2024-04-01"), patch.object(fundamentals, "route_to_vendor", return_value="ok") as fin, patch.object(news, "route_to_vendor", return_value="ok") as fetch:
            result = app.invoke({"messages": [message]})
            fin.assert_called_once_with("get_balance_sheet", "T", "quarterly", "2024-04-01")
            fetch.assert_called_once_with("get_global_news", "2024-04-01", 7, 5)
            self.assertIn("unavailable", result["messages"][-1].content)
        self.assertIsNone(bounded_analysis_date())

    def test_us_snapshot_available_after_korean_midnight(self):
        from tradingagents.dataflows import fundamental_dates
        instant = datetime(2024, 4, 1, 21, tzinfo=timezone.utc)
        with patch.object(fundamental_dates, "datetime") as clock:
            clock.now.side_effect = lambda tz: instant.astimezone(tz)
            self.assertIsNone(fundamental_dates.unavailable_snapshot("AAPL", "2024-04-01"))
            self.assertIn("unavailable", fundamental_dates.unavailable_snapshot("005930.KS", "2024-04-01"))
            self.assertIsNone(fundamental_dates.unavailable_snapshot("005930.KS", "2024-04-02"))
