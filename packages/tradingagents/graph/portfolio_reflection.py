"""Portfolio weekly reflection generator."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel

from tradingagents.storage import PortfolioReflectionRepository

logger = logging.getLogger(__name__)


class PortfolioReflector:
    """Generate and persist weekly portfolio reflection."""

    def __init__(
        self,
        llm: BaseChatModel,
        db,
        hybrid_memory=None,
    ):
        self.llm = llm
        self.db = db
        self.hybrid_memory = hybrid_memory
        self.repo = PortfolioReflectionRepository(db)

    @staticmethod
    def _clamp_score(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            score = int(float(value))
        except (TypeError, ValueError):
            return None
        return max(0, min(100, score))

    def _build_prompt(
        self,
        week_start: str,
        week_end: str,
        decisions: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        holdings: List[Dict[str, Any]],
        total_return_pct: Optional[float],
    ) -> str:
        decisions_text = json.dumps(decisions[:20], ensure_ascii=False)
        trades_text = json.dumps(trades[:200], ensure_ascii=False)
        holdings_text = json.dumps(holdings[:200], ensure_ascii=False)
        return f"""당신은 포트폴리오 회고 분석가입니다.
주간 기간({week_start} ~ {week_end})의 의사결정 품질을 평가하세요.

[이번 주 의사결정]
{decisions_text}

[이번 주 매매]
{trades_text}

[보유 스냅샷]
{holdings_text}

[주간 총 수익률]
{total_return_pct if total_return_pct is not None else "N/A"}%

요구사항:
1) 회고문(핵심 요약 포함) 작성
2) allocation_accuracy 0~100 점수 부여
3) key_lessons를 짧게 정리

반드시 아래 JSON 형식으로만 출력:
{{
  "reflection_content": "주간 회고 본문",
  "allocation_accuracy": 0,
  "key_lessons": "핵심 교훈",
  "total_return_pct": {total_return_pct if total_return_pct is not None else "null"}
}}
"""

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        text = str(content).strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    def _parse_output(
        self,
        content: str,
        fallback_total_return_pct: Optional[float],
    ) -> Dict[str, Any]:
        parsed = self._parse_json(content)
        reflection_content = str(parsed.get("reflection_content") or "").strip()
        key_lessons = str(parsed.get("key_lessons") or "").strip()
        accuracy = self._clamp_score(parsed.get("allocation_accuracy"))
        total_return_pct = parsed.get("total_return_pct")

        if accuracy is None:
            m = re.search(r"allocation_accuracy\s*[:=]\s*(\d+)", str(content), flags=re.IGNORECASE)
            if m:
                accuracy = self._clamp_score(m.group(1))
        if not key_lessons:
            m = re.search(r"key_lessons\s*[:=]\s*(.+)", str(content), flags=re.IGNORECASE)
            if m:
                key_lessons = m.group(1).strip()[:400]
        if not reflection_content:
            reflection_content = str(content).strip()
        if not key_lessons:
            key_lessons = reflection_content[:400]

        try:
            total_return_pct_val = (
                float(total_return_pct)
                if total_return_pct is not None
                else fallback_total_return_pct
            )
        except (TypeError, ValueError):
            total_return_pct_val = fallback_total_return_pct

        return {
            "reflection_content": reflection_content,
            "allocation_accuracy": accuracy,
            "key_lessons": key_lessons,
            "total_return_pct": total_return_pct_val,
        }

    def reflect_weekly(
        self,
        config_id: int,
        week_start_date: str,
        week_end_date: str,
        decisions: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        holdings: List[Dict[str, Any]],
        total_return_pct: Optional[float],
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(
            week_start=week_start_date,
            week_end=week_end_date,
            decisions=decisions,
            trades=trades,
            holdings=holdings,
            total_return_pct=total_return_pct,
        )

        try:
            response = self.llm.invoke(prompt, config={"timeout": 180})
            content = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_output(str(content), total_return_pct)
        except Exception as exc:
            logger.warning("PortfolioReflector fallback due to LLM error: %s", exc)
            parsed = {
                "reflection_content": (
                    f"{week_start_date}~{week_end_date} 포트폴리오 주간 회고를 생성하지 못했습니다. "
                    "데이터를 기반으로 다음 주 위험 노출을 축소하세요."
                ),
                "allocation_accuracy": None,
                "key_lessons": "LLM 실패로 기본 회고를 저장했습니다.",
                "total_return_pct": total_return_pct,
            }

        reflection_id = self.repo.create(
            config_id=config_id,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            reflection_content=parsed["reflection_content"],
            allocation_accuracy=parsed["allocation_accuracy"],
            total_return_pct=parsed["total_return_pct"],
            key_lessons=parsed["key_lessons"],
        )

        if self.hybrid_memory and hasattr(self.hybrid_memory, "add_external_document"):
            try:
                outcome = None
                if parsed["total_return_pct"] is not None:
                    outcome = "win" if float(parsed["total_return_pct"]) >= 0 else "loss"
                self.hybrid_memory.add_external_document(
                    document_id=reflection_id,
                    matched_situation=parsed["key_lessons"],
                    recommendation=parsed["reflection_content"],
                    collection_name="portfolio_reflections",
                    source_table="portfolio_reflections",
                    metadata={
                        "outcome": outcome,
                        "return_pct": parsed["total_return_pct"],
                        "source_collection": "portfolio_reflections",
                    },
                )
            except Exception as exc:
                logger.warning("Failed to store portfolio reflection vector: %s", exc)

        saved = self.repo.get_by_id(reflection_id) or {"id": reflection_id}
        return saved
