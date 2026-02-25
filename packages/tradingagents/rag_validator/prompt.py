"""Prompt builder for RAG validation."""

import json
from typing import Any, Dict


def build_validation_prompt(
    retrospective_content: str,
    rag_doc: Dict[str, Any],
) -> str:
    """Build prompt to decide if a RAG memory was reflected in PA decision."""
    reflection_id = rag_doc.get("reflection_id")
    matched = rag_doc.get("matched_situation", "")
    return_pct = rag_doc.get("return_pct")
    outcome_label = rag_doc.get("outcome_label", "")

    schema = {
        "reflection_id": reflection_id,
        "verdict": "reflected | not_reflected | ambiguous",
        "justification": "short reason",
    }

    return f"""당신은 RAG 품질 검증기입니다.

회고분석 문서와 RAG 문서를 비교해, 포트폴리오 에이전트가 해당 경험을 실제 의사결정에 반영했는지 판정하세요.

[회고분석]
{retrospective_content}

[RAG 문서]
- reflection_id: {reflection_id}
- outcome_label: {outcome_label}
- return_pct: {return_pct}
- matched_situation: {matched}

반드시 아래 JSON 스키마로만 출력하세요:
```json
{json.dumps(schema, ensure_ascii=False, indent=2)}
```

판정 규칙:
- reflected: 회고분석에 해당 경험의 핵심 교훈/근거가 명확히 사용됨
- not_reflected: 해당 경험과 무관하거나 반대로 행동함
- ambiguous: 판단 근거가 부족함
"""
