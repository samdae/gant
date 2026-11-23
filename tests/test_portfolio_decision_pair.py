import json
import unittest
from unittest.mock import Mock, patch

from tradingagents.errors import AgentExecutionError
from tradingagents.virtual_trade.portfolio_agent import PortfolioAgent


def response(action, allocation, applied=None):
    return Mock(content=json.dumps(dict(action=action, allocation_pct=allocation,
                                        applied_reflection_ids=applied, rationale="Reviewed #7")))


def memory(reflection_id):
    return {"metadata": {"reflection_id": reflection_id}, "matched_situation": "unique lesson text"}


class PairedDecisionTests(unittest.TestCase):
    def setUp(self):
        self.llm = Mock()
        self.rag = Mock()
        self.manager = Mock()
        self.manager.load.return_value = {"position": {"id": 1, "shares": 8}, "status": "open"}
        self.manager.get_position_summary.return_value = "holding eight"
        self.manager.calculate_realized_return.return_value = {"total_returned": 400, "realized_return_pct": 0}
        self.agent = PortfolioAgent(self.llm, self.manager, Mock(), hybrid_memory=self.rag)
        self.rag.get_memories.return_value = [memory(7)]
        trade = self.enterContext(patch("tradingagents.storage.TradeRepository"))
        trade.return_value.get_cash_balance.return_value = 1000
        reports = self.enterContext(patch("tradingagents.storage.ReportRepository"))
        reports.return_value.get_by_position.return_value = [
            {"final_trade_decision": "prior market judgment", "pa_opinion": "previous private lesson rationale"}]

    def decide(self, outputs):
        self.llm.invoke.side_effect = outputs
        return self.agent.decide("A", "BUY", {"final_trade_decision": "market snapshot"}, 50,
                                 context={"sector": "example"})

    def test_only_lesson_text_differs_and_only_live_arm_is_returned(self):
        result = self.decide([response("SELL", 50), response("BUY", 25, [7])])
        docs = json.loads(result["rag_docs"])
        self.assertEqual((result["action"], result["shares"]), ("BUY", 5))
        self.assertEqual(docs["decision_pair_v1"], dict(reflection_id=7, before=dict(action="SELL", shares=4),
                         after=dict(action="BUY", shares=5), cash=1000, holdings=8))
        first, second = (call.args[0] for call in self.llm.invoke.call_args_list)
        self.assertNotIn("unique lesson text", first)
        self.assertNotIn("previous private lesson", second)
        self.assertIn("prior market judgment", first)
        self.assertEqual(second.replace(docs["raw_context"], ""), first)

    def test_unchanged_but_explicitly_applied_is_a_measurable_pair(self):
        docs = json.loads(self.decide([response("BUY", 50), response("BUY", 50, [7])])["rag_docs"])
        self.assertEqual(docs["decision_pair_v1"]["before"], docs["decision_pair_v1"]["after"])

    def test_unknown_duplicate_rejected_missing_or_multiple_supply_yields_no_pair(self):
        for ids, lessons in [([], [7]), (None, [7]), ([7, 777], [7]), ([7, 7], [7]), ([True], [1]), ([7], [7, 8])]:
            with self.subTest(ids=ids, lessons=lessons):
                self.rag.get_memories.return_value = [memory(i) for i in lessons]
                docs = json.loads(self.decide([response("BUY", 25), response("BUY", 50, ids)])["rag_docs"])
                self.assertNotIn("decision_pair_v1", docs)

    def test_failed_control_or_infeasible_order_cannot_be_compared(self):
        for first in [RuntimeError("control unavailable"), response("BUY", 0)]:
            docs = json.loads(self.decide([first, response("SELL", 100, [7])])["rag_docs"])
            self.assertNotIn("decision_pair_v1", docs)
        with self.assertRaises(AgentExecutionError):
            self.decide([response("BUY", 50), RuntimeError("live arm failed")])

    def test_no_eligible_memory_has_one_call_and_preserves_prior_history(self):
        self.rag.get_memories.return_value = [memory(None)]
        result = self.decide([response("BUY", 50)])
        self.llm.invoke.assert_called_once()
        self.assertIn("previous private lesson", self.llm.invoke.call_args.args[0])
        self.assertFalse(result["rag_used"])
        self.assertIsNone(result["rag_docs"])
