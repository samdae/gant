"""Decision evidence and quantity boundaries in the normal analysis pipeline."""
import json
import unittest
from unittest.mock import Mock, patch

from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.errors import DecisionParseError
from tradingagents.graph.signal_processing import SignalProcessor
from tradingagents.virtual_trade.portfolio_agent import PortfolioAgent


class DecisionEvidenceTests(unittest.TestCase):
    def test_judge_reads_traders_actual_plan(self):
        llm = Mock()
        debate = dict.fromkeys(("history", "aggressive_history", "conservative_history",
                                "neutral_history", "current_aggressive_response",
                                "current_conservative_response", "current_neutral_response"), "")
        debate["count"] = 3
        create_risk_manager(llm)({"investment_plan": "Research-only marker",
                                  "trader_investment_plan": "Trader-only marker",
                                  "risk_debate_state": debate})
        prompt = llm.invoke.call_args.args[0]
        self.assertIn("Trader-only marker", prompt)
        self.assertNotIn("Research-only marker", prompt)

    def test_invalid_forecast_does_not_replace_the_action(self):
        for value in (True, "0.5", -0.1, 1.1, None):
            strategy = {"action": "SELL", "forecast_5s": {"p_up": value}}
            signal = "```strategy_json\n" + json.dumps(strategy) + "\n```"
            self.assertEqual(SignalProcessor(Mock()).process_signal(signal), ("SELL", {"action": "SELL"}))

    def test_zero_allocation_and_microshares(self):
        agent = object.__new__(PortfolioAgent)
        state = {"position": {"shares": 5}}
        for action in ("BUY", "SELL"):
            result = agent._parse_decision(json.dumps({"action": action, "allocation_pct": 0}),
                                           state, 100, 100)
            self.assertEqual(result["shares"], 0)
        buy = agent._parse_decision('{"action":"BUY","allocation_pct":100}', state, 60000, 10)
        self.assertLessEqual(buy["shares"] * 60000, 10)
        self.assertEqual(buy["shares"], 0.000166)

    @patch("tradingagents.storage.TradeRepository")
    @patch("tradingagents.storage.ReportRepository")
    def test_recent_reports_and_no_memory_constraint(self, report_repo, trade_repo):
        llm, manager, db = Mock(), Mock(), Mock()
        manager.load.return_value = {"position": {"id": 1, "shares": 0}, "status": "open"}
        report_repo.return_value.get_by_position.return_value = [
            {"final_trade_decision": f"signal-{i}"} for i in (5, 4, 3, 2, 1)]
        trade_repo.return_value.get_cash_balance.return_value = 500
        llm.invoke.return_value.content = '{"action":"BUY","allocation_pct":10}'
        agent = PortfolioAgent(llm, manager, db)
        with self.assertRaises(DecisionParseError):
            agent.decide("A", "SELL", {}, 100, context={"currency": "KRW"})
        prompt = llm.invoke.call_args.args[0]
        self.assertIn("KRW 100.00", prompt)
        self.assertLess(prompt.index("signal-3"), prompt.index("signal-5"))
        self.assertNotIn("signal-1", prompt)


    def test_portfolio_briefing_keeps_evidence_sources_distinct(self):
        from tradingagents.agents.briefing_agent import BriefingAgent
        items = BriefingAgent(Mock())._build_items([
            dict(ticker="A", decision_position="BUY", portfolio_action="SELL",
                 final_trade_decision="High risk", pipeline_strategy='{"conviction":"LOW"}'),
            dict(ticker="B", decision_position="SELL", portfolio_rationale="Automatic liquidation: target"),
        ])
        self.assertEqual((items[0]["action"], items[0]["ticker_pa_action"], items[0]["confidence"]),
                         ("BUY", "SELL", "low"))
        self.assertTrue(items[1]["analysis_skipped"])
        self.assertEqual(items[1]["action"], "HOLD")
