import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from tradingagents.memory.hybrid_memory import HybridMemory
from tradingagents.rag_validator.service import RAGValidatorService
from tradingagents.retrospective.prompt import build_retrospective_prompt, report_memories
from tradingagents.storage.trade_repo import closed_position_return


def fill(action, qty, price, currency="USD"):
    return dict(action=action, shares=qty, price=price, currency=currency)


class LearningFeedbackTests(unittest.TestCase):
    def test_final_sale_alone_has_opposite_sign(self):
        trades = [fill("BUY", 10, 100), fill("SELL", 9, 130), fill("SELL", 1, 50)]
        self.assertEqual(closed_position_return(trades, "USD"), 22)
        position = dict(ticker="X", currency="USD", return_pct=-50, opened_at="date")
        text = build_retrospective_prompt(position, [], trades, False)
        self.assertIn("+22.00%", text)

    def test_incomplete_history_has_no_outcome(self):
        for trades in ([fill("BUY", 1, 1)], [fill("SELL", 1, 1), fill("BUY", 1, 1)],
                       [fill("BUY", 1, 1), fill("SELL", 1, 1, "KRW")]):
            self.assertIsNone(closed_position_return(trades, "USD"))

    def test_missing_evidence_is_ignored(self):
        for record in (None, 'unexpected', '{"memories":[null, {"reflection_id":"not a number"}]}'):
            self.assertEqual(report_memories(dict(rag_used=True, rag_docs=record)), [])

    def test_invalid_response_remains_retryable(self):
        service = RAGValidatorService(Mock(), {})
        service._llm = Mock()
        service.retro_repo = Mock()
        service.retro_repo.get_by_id.return_value = dict(status="completed", analysis_content="retro", position_id=5)
        service.report_repo = Mock()
        service.report_repo.get_by_position.return_value = [
            dict(rag_used=True, scheduled_cycle=17, pa_opinion="original rationale",
                 rag_docs={"memories":[{"reflection_id":3, "matched_situation":"lesson"}]})]
        service.validation_repo = Mock()
        service.validation_repo.exists.return_value = False
        service._llm.invoke.return_value = SimpleNamespace(content="broken")
        with self.assertRaises(ValueError):
            service.validate(1)
        service.validation_repo.create.assert_not_called()
        self.assertIn("original rationale", service._llm.invoke.call_args.args[0])

    def test_portfolio_cross_search_survives_missing_chroma(self):
        memory = HybridMemory.__new__(HybridMemory)
        memory._vector_retrieve_from_collection = Mock(return_value=[])
        memory._fts_retrieve = Mock(return_value=[(4, .5)])
        memory._get_document_by_id = Mock(return_value={"id":4, "key_lessons":"lesson"})
        results = memory.get_memories_cross("q", "portfolio_reflections", "analysis_reflections", 2, 0)
        self.assertEqual(results[0]["metadata"]["source_collection"], "portfolio_reflections")
        memory._fts_retrieve.assert_called_once_with("q", 3, source_table="portfolio_reflections")

    def test_verified_result_fills_quota_after_stale_top_hit(self):
        memory = HybridMemory.__new__(HybridMemory)
        memory.source_table = "reflections"
        memory.collection_name = "analysis_reflections"
        memory.chroma_available = False
        memory.chroma_client = Mock()
        memory.reflection_repo = Mock()
        memory._fts_retrieve = Mock(return_value=[(1, .9), (2, .8), (3, .7)])
        memory._get_document_by_id = Mock(side_effect=lambda rid, **kwargs: {"id":rid} if rid > 1 else None)
        hits = memory.get_memories("query", n_matches=1)
        self.assertEqual([hit["metadata"]["reflection_id"] for hit in hits], [2])
        memory._vector_retrieve_from_collection = Mock(return_value=[(1, .9)])
        hits = memory.get_memories_cross("query", "analysis_reflections", "portfolio_reflections", 1, 0)
        self.assertEqual([hit["metadata"]["reflection_id"] for hit in hits], [2])

    def test_usage_verdict_requires_source_evidence(self):
        import json

        service = RAGValidatorService(Mock(), {})
        service._llm = Mock()
        doc = {"reflection_id": 7, "decisions": [{"opinion": "회고 #7의 거래량 조건을 적용"}]}
        answer = {"reflection_id": 7, "evidence_quote": "거래량 조건을 적용", "justification": "조건 일치"}
        for verdict in ("reflected", "not_reflected", "ambiguous"):
            service._llm.invoke.return_value.content = json.dumps(dict(answer, verdict=verdict))
            self.assertEqual(service._evaluate_document("retro", doc)["score_delta"], 0)
        for changes in ({"reflection_id": 9}, {"evidence_quote": "없는 기록"}):
            service._llm.invoke.return_value.content = json.dumps(dict(answer, verdict="reflected", **changes))
            with self.assertRaises(ValueError):
                service._evaluate_document("retro", doc)

    def test_retrospective_scores_require_unique_valid_fields(self):
        from tradingagents.retrospective.service import _parse_scores, _build_prompt_with_scores
        self.assertIn("90~100", _build_prompt_with_scores("회고"))
        self.assertEqual(_parse_scores("analysis_accuracy: 72\nrag_contribution: null"), (72, None))
        for bad in ("101", "-3", "78.5", "90~100", "70점"):
            self.assertEqual(_parse_scores("analysis_accuracy: " + bad), (None, None))
        self.assertEqual(_parse_scores("analysis_accuracy: 10\nanalysis_accuracy: 80"), (None, None))
