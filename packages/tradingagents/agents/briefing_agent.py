"""Briefing agent for portfolio daily pipeline."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


def _extract_decision(text: Optional[str]) -> str:
    if not text:
        return "HOLD"
    cleaned = str(text).replace("**", "")
    m = re.search(r"(BUY|SELL|HOLD|매수|매도|보유)", cleaned, flags=re.IGNORECASE)
    if not m:
        return "HOLD"
    token = m.group(1).upper()
    if token in {"BUY", "SELL", "HOLD"}:
        return token
    if "매수" in m.group(1):
        return "BUY"
    if "매도" in m.group(1):
        return "SELL"
    return "HOLD"


class BriefingAgent:
    """Compress per-ticker analysis reports into a portfolio briefing."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def _build_items(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for report in reports:
            ticker = str(report.get("ticker") or "").upper()
            if bool(report.get("analysis_skipped")):
                skip_reason = str(
                    report.get("skip_reason") or "오늘 분석 없음 (데이터 미갱신)"
                )
                items.append(
                    {
                        "ticker": ticker,
                        "action": "HOLD",
                        "confidence": "low",
                        "summary": skip_reason,
                        "analysis_skipped": True,
                    }
                )
                continue

            decision = (
                report.get("portfolio_action")
                or report.get("decision_position")
                or _extract_decision(report.get("final_trade_decision"))
            )
            final_reason = str(report.get("final_trade_decision") or "")
            key_summary = str(report.get("market_report") or "")[:400]
            confidence = "medium"
            if "high" in final_reason.lower() or "강한" in final_reason:
                confidence = "high"
            elif "low" in final_reason.lower() or "약한" in final_reason:
                confidence = "low"

            items.append(
                {
                    "ticker": ticker,
                    "action": str(decision).upper(),
                    "confidence": confidence,
                    "summary": key_summary,
                    "analysis_skipped": False,
                }
            )
        items.sort(key=lambda x: x["ticker"])
        return items

    def _fallback_summary(
        self,
        items: List[Dict[str, Any]],
        holdings: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        if not items:
            return "오늘 반영할 분석 리포트가 없어 포트폴리오 리밸런싱을 보류합니다."
        buy_cnt = len([i for i in items if i["action"] == "BUY"])
        sell_cnt = len([i for i in items if i["action"] == "SELL"])
        hold_cnt = len([i for i in items if i["action"] == "HOLD"])
        top = ", ".join([f"{i['ticker']}:{i['action']}" for i in items[:6]])
        holdings_cnt = len(holdings or [])
        return (
            f"오늘 분석 요약: BUY {buy_cnt}건, SELL {sell_cnt}건, HOLD {hold_cnt}건. "
            f"주요 티커 판단은 {top} 입니다. "
            f"현재 보유 종목 수는 {holdings_cnt}개로 집계되었습니다."
        )

    def generate_briefing(
        self,
        reports: List[Dict[str, Any]],
        holdings: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate briefing summary payload."""
        items = self._build_items(reports)
        fallback = self._fallback_summary(items, holdings)
        if not items:
            return {
                "summary_text": fallback,
                "items": items,
                "generated_at": datetime.now().isoformat(),
            }

        holdings_text = ""
        if holdings:
            sample = []
            for h in holdings[:8]:
                sample.append(
                    f"{h.get('ticker')} {float(h.get('allocation_pct') or 0):.1f}%"
                )
            holdings_text = ", ".join(sample)

        prompt = f"""당신은 투자 비서입니다.
다음 종목별 분석 요약을 바탕으로 오늘의 포트폴리오 브리핑을 간결하게 작성하세요.

[분석 요약]
{items}

[현재 보유(상위)]
{holdings_text if holdings_text else "(없음)"}

요구사항:
1) 전체 시장 흐름 2~3문장
2) 종목별 핵심 변화(매수/매도 후보) 3~6개
3) 리스크/주의 포인트 1~2개
4) 반드시 한국어, 500자 내외
"""
        try:
            response = self.llm.invoke(prompt, config={"timeout": 180})
            content = response.content if hasattr(response, "content") else str(response)
            summary_text = str(content).strip()
            if not summary_text:
                summary_text = fallback
        except Exception as exc:
            logger.warning("BriefingAgent fallback due to LLM error: %s", exc)
            summary_text = fallback

        return {
            "summary_text": summary_text,
            "items": items,
            "generated_at": datetime.now().isoformat(),
        }
