"""RAG validation service."""

import json
import logging
from typing import Any, Dict, List

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.retrospective.prompt import report_memories
from tradingagents.rag_validator.prompt import build_validation_prompt
from tradingagents.storage import (
    RAGValidationRepository,
    ReportRepository,
    RetrospectiveRepository,
)
from tradingagents.storage.database import Database

logger = logging.getLogger(__name__)


class RAGValidatorService:
    """Evaluate whether RAG docs were reflected in retrospective analysis."""

    def __init__(self, db: Database, config: Dict[str, Any]):
        self.db = db
        self.config = config
        self.retro_repo = RetrospectiveRepository(db)
        self.report_repo = ReportRepository(db)
        self.validation_repo = RAGValidationRepository(db)
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            client = create_llm_client(
                provider=self.config.get("llm_provider", "gemini-cli"),
                model=self.config.get("quick_think_llm", "gemini-3-flash"),
                base_url=self.config.get("backend_url"),
            )
            self._llm = client.get_llm()
        return self._llm

    def _is_already_evaluated(self, retrospective_id: int, reflection_id: int) -> bool:
        return self.validation_repo.exists(retrospective_id, reflection_id)

    def _evaluate_document(
        self,
        retro_content: str,
        rag_doc: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = build_validation_prompt(retro_content, rag_doc)
        response = self._get_llm().invoke(prompt, config={"timeout": 600})
        content = response.content if hasattr(response, "content") else str(response)
        parsed = self._parse_json(content)

        if not isinstance(parsed, dict):
            raise ValueError("Expected a RAG verdict object")
        verdict = str(parsed.get("verdict", "")).strip().lower()
        if verdict not in {"reflected", "not_reflected", "ambiguous"}:
            raise ValueError("Invalid or missing RAG verdict")
        justification = parsed.get("justification")
        if not isinstance(justification, str) or not justification.strip():
            raise ValueError("Missing RAG verdict justification")
        reflection_id = int(rag_doc.get("reflection_id"))

        if parsed.get("reflection_id") != reflection_id:
            raise ValueError("RAG verdict references the wrong memory")
        if verdict != "ambiguous":
            quote = parsed.get("evidence_quote")
            if not isinstance(quote, str) or not quote.strip():
                raise ValueError("RAG verdict has no supporting PA quotation")
            quote = quote.strip()
            if not any(quote in (decision.get(field) or "") for decision in rag_doc["decisions"]
                       for field in ("opinion", "rationale")):
                raise ValueError("Quoted evidence is absent from the recorded PA decision")
            justification = f"{justification} (당시 PA 기록: {quote})"

        return {
            "reflection_id": reflection_id,
            "verdict": verdict,
            "justification": justification,
            "score_delta": 0,
        }

    def _generate_report(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        summary = {
            "evaluated_count": len(results),
            "reflected_count": 0,
            "not_reflected_count": 0,
            "ambiguous_count": 0,
        }
        for result in results:
            key = f"{result['verdict']}_count"
            if key in summary:
                summary[key] += 1
        return summary

    def validate(self, retrospective_id: int) -> Dict[str, Any]:
        retro = self.retro_repo.get_by_id(retrospective_id)
        if not retro:
            raise ValueError(f"Retrospective {retrospective_id} not found")

        if retro.get("status") != "completed":
            raise ValueError(f"Retrospective {retrospective_id} is not completed")
        retro_content = retro.get("analysis_content") or ""
        if not retro_content.strip():
            raise ValueError(f"Retrospective {retrospective_id} has empty analysis_content")

        reports = self.report_repo.get_by_position(retro["position_id"])
        deduped: Dict[int, Dict[str, Any]] = {}
        for report in reports:
            for memory in report_memories(report):
                reflection_id = int(memory["reflection_id"])
                doc = deduped.setdefault(reflection_id, {**memory, "decisions": []})
                doc["decisions"].append({
                    "cycle": report.get("scheduled_cycle"),
                    "action": report.get("portfolio_action"),
                    "opinion": report.get("pa_opinion"),
                    "rationale": report.get("portfolio_rationale"),
                })

        results: List[Dict[str, Any]] = []
        for reflection_id, doc in deduped.items():
            if self._is_already_evaluated(retrospective_id, reflection_id):
                continue
            result = self._evaluate_document(retro_content, doc)
            inserted = self.validation_repo.create(
                retrospective_id=retrospective_id,
                reflection_id=result["reflection_id"],
                verdict=result["verdict"],
                justification=result["justification"],
            )
            if inserted:
                results.append(result)
        return {
            "retrospective_id": retrospective_id,
            "summary": self._generate_report(results),
            "results": results,
        }

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        text = str(content).strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return {}
