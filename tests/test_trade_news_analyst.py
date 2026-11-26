"""Trade archive receipt, attribution and the price-session time boundary."""
import json
import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from langchain_core.messages import HumanMessage, ToolMessage

from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.llm_clients.codex_client import ChatCodex
from tradingagents.scheduler.news_evidence import trade_news_for_close


class TradeNewsAnalystTests(unittest.TestCase):
    def test_codex_tool_turns_receive_the_same_archive_and_only_explicit_refs_survive(self):
        packet = {"version": 1, "ticker": "WMT", "status": "available", "as_of": "2026-11-25T21:00:00+00:00",
                  "items": [{"ref": "N1", "title": "Revenue outlook {revised}", "url": "https://example.org/1"},
                            {"ref": "N2", "title": "Store incident", "url": "https://example.org/2"}]}
        state = {"trade_date": "2026-11-25", "company_of_interest": "WMT", "news_evidence": packet,
                 "messages": [HumanMessage("WMT")]}
        with patch("tradingagents.llm_clients.codex_client.Codex") as sdk:
            client = sdk.return_value.__enter__.return_value
            client.account.return_value.account.root.type = "chatgpt"
            thread = client.thread_start.return_value
            tool_call = {"name": "get_news", "arguments": json.dumps({
                "query": "WMT", "start_date": "2026-11-19", "end_date": "2026-11-25"})}
            replies = [{"content": "", "calls": [tool_call]},
                       {"content": "Outlook merits review [N1]. Invalid [N99].", "calls": []}]
            thread.run.side_effect = [Mock(final_response=json.dumps(a), status=Mock(value="completed")) for a in replies]
            node = create_news_analyst(ChatCodex())
            first = node(state)
            self.assertNotIn("news_analyst_cited", first)
            ai = first["messages"][0]
            state["messages"].extend([ai, ToolMessage(content="Separate news", tool_call_id=ai.tool_calls[0]["id"])])
            result = node(state)
            self.assertEqual(result["news_analyst_cited"], ["N1"])
            for start, turn in zip(client.thread_start.call_args_list, thread.run.call_args_list):
                self.assertNotIn("Revenue outlook", start.kwargs["base_instructions"])
                messages = json.loads(turn.args[0])
                self.assertEqual(messages[0]["type"], "human")
                self.assertEqual(json.loads(messages[0]["data"]["content"].split("\n", 1)[1]), packet)
        manager = Mock()
        debate = dict.fromkeys(("history", "aggressive_history", "conservative_history", "neutral_history",
                                "current_aggressive_response", "current_conservative_response", "current_neutral_response"), "")
        create_risk_manager(manager)({**result, "risk_debate_state": {**debate, "count": 3}, "trader_investment_plan": ""})
        self.assertIn("Eligible archive references cited by the analyst: [N1].", manager.invoke.call_args.args[0])

    @patch("tradingagents.scheduler.news_evidence.read_trade_news")
    def test_cutoff_follows_the_price_exchange_including_short_sessions(self, read_news):
        def cutoff(symbol, market, day, venue, now="2026-12-01T12:00:00+00:00"):
            trade_news_for_close(symbol, market, day, {**venue, "symbol": symbol}, datetime.fromisoformat(now))
            return read_news.call_args.args[2].astimezone(UTC).isoformat()
        us = {"instrumentType": "EQUITY", "currency": "USD", "exchangeName": "NMS", "exchangeTimezoneName": "America/New_York"}
        kr = {"instrumentType": "EQUITY", "currency": "KRW", "exchangeName": "KSC", "exchangeTimezoneName": "Asia/Seoul"}
        btc = {"instrumentType": "CRYPTOCURRENCY", "currency": "USD", "exchangeName": "CCC", "exchangeTimezoneName": "UTC"}
        self.assertEqual(cutoff("WMT", "us", "2026-11-27", us), "2026-11-27T18:00:00+00:00")
        self.assertEqual(cutoff("NVDA", "us", "2026-07-07", us), "2026-07-07T20:00:00+00:00")
        self.assertEqual(cutoff("000660.KS", "kr", "2026-11-25", kr), "2026-11-25T06:30:00+00:00")
        self.assertEqual(cutoff("BTC-USD", "us", "2026-11-25", btc), "2026-11-26T00:00:00+00:00")
        self.assertEqual(cutoff("BTC-USD", "us", "2026-11-25", btc, "2026-11-25T10:05:00+00:00"),
                         "2026-11-25T10:05:00+00:00")
        read_news.reset_mock()
        now = datetime(2026, 11, 28, tzinfo=UTC)
        for bad in ({**us, "symbol": "WMT", "exchangeName": "LSE"}, {**us, "symbol": "WMT"}, {}):
            # Thanksgiving is closed; lack of verified market metadata also disables archive delivery.
            result = trade_news_for_close("WMT", "us", "2026-11-26", bad, now)
            self.assertEqual((result["status"], result["items"]), ("unavailable", []))
        read_news.assert_not_called()
