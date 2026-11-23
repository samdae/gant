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
        "evidence_quote": "당시 PA 의견 또는 판단 근거에서 그대로 인용한 문장 (ambiguous이면 빈 문자열)",
    }

    return f"""당신은 RAG 품질 검증기입니다.

회고분석 문서와 RAG 문서를 비교해, 포트폴리오 에이전트가 해당 경험을 실제 의사결정에 반영했는지 판정하세요.

[해당 경험을 제공한 사이클의 실제 PA 기록]
{json.dumps(rag_doc.get("decisions", []), ensure_ascii=False)}

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
- reflected: 당시 PA 기록에서 해당 경험의 교훈을 판단 근거로 사용한 증거가 있음
- not_reflected: PA가 해당 교훈을 명시적으로 배제한 증거가 있음
- ambiguous: 근거가 부족하거나 단순히 매매 방향만 일치함. 회고자의 해석 또는 수익만으로 반영 여부를 추론하지 마세요.
"""
