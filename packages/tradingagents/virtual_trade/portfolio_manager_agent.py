"""Portfolio manager agent for cross-ticker allocation decisions."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class PortfolioManagerAgent:
    """LLM agent that generates portfolio allocation plans."""

    def __init__(
        self,
        llm: BaseChatModel,
        hybrid_memory=None,
        retry_budget: int = 1,
    ):
        self.llm = llm
        self.hybrid_memory = hybrid_memory
        self.retry_budget = max(int(retry_budget), 0)

    def _build_prompt(
        self,
        briefing: Dict[str, Any],
        holdings: List[Dict[str, Any]],
        available_cash: float,
        exchange_rate: float,
        rag_context: str = "",
        strict: bool = False,
    ) -> str:
        brief_text = str(briefing.get("summary_text") or "")
        items = briefing.get("items") or []
        holdings_lines = []
        for h in holdings[:30]:
            holdings_lines.append(
                f"- {h.get('ticker')} shares={float(h.get('shares') or 0):.4f}, "
                f"avg_cost={float(h.get('avg_cost') or 0):.2f}, "
                f"allocation={float(h.get('allocation_pct') or 0):.2f}%"
            )
        holdings_text = "\n".join(holdings_lines) if holdings_lines else "(보유 없음)"

        strict_line = (
            "중요: JSON 파싱 실패가 발생했습니다. 이번에는 반드시 JSON만 출력하세요."
            if strict
            else ""
        )

        return f"""당신은 포트폴리오 매니저입니다. 오늘의 리밸런싱 계획을 수립하세요.
{strict_line}

[오늘 브리핑]
{brief_text}

[종목별 요약 데이터]
{json.dumps(items, ensure_ascii=False)}

[현재 포트폴리오 보유]
{holdings_text}

[자금]
- 가용 현금(기준통화): {float(available_cash):.2f}
- 환율(USDKRW): {float(exchange_rate):.4f}

{rag_context}

규칙:
1) action은 BUY/SELL/HOLD 중 하나
2) allocation_pct는 0~100
3) shares는 0 이상 실수
4) 전체 BUY 비중 합계가 과도하지 않게 유지
5) rationale은 종목별 1문장
6) 결과는 아래 JSON만 출력

{{
  "rationale": "전체 배분 근거",
  "allocation_plan": [
    {{
      "ticker": "NVDA",
      "action": "BUY",
      "allocation_pct": 20,
      "shares": 3.5,
      "rationale": "근거"
    }}
  ]
}}
"""

    def _fallback_plan(
        self,
        briefing: Dict[str, Any],
        holdings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        tickers = [str(i.get("ticker") or "").upper() for i in (briefing.get("items") or [])]
        if not tickers:
            tickers = [str(h.get("ticker") or "").upper() for h in holdings]
        tickers = [t for t in tickers if t]
        plan = []
        for ticker in sorted(set(tickers)):
            plan.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "allocation_pct": 0.0,
                    "shares": 0.0,
                    "rationale": "파싱 실패로 보수적으로 유지",
                }
            )
        return {
            "rationale": "파싱 실패로 전체 포지션 유지(HOLD) 처리",
            "allocation_plan": plan,
        }

    @staticmethod
    def _parse_json_object(text: str) -> Dict[str, Any]:
        raw = str(text).strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, flags=re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        raise ValueError("allocation JSON parse failed")

    def _parse_plan(self, text: str) -> Dict[str, Any]:
        parsed = self._parse_json_object(text)
        raw_plan = parsed.get("allocation_plan")
        if not isinstance(raw_plan, list):
            if isinstance(parsed, list):
                raw_plan = parsed
            else:
                raise ValueError("allocation_plan must be a list")

        plan: List[Dict[str, Any]] = []
        for item in raw_plan:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            action = str(item.get("action") or "HOLD").upper().strip()
            if action not in {"BUY", "SELL", "HOLD"}:
                action = "HOLD"
            try:
                allocation_pct = float(item.get("allocation_pct", 0.0))
            except (TypeError, ValueError):
                allocation_pct = 0.0
            try:
                shares = float(item.get("shares", 0.0))
            except (TypeError, ValueError):
                shares = 0.0
            plan.append(
                {
                    "ticker": ticker,
                    "action": action,
                    "allocation_pct": max(min(allocation_pct, 100.0), 0.0),
                    "shares": max(shares, 0.0),
                    "rationale": str(item.get("rationale") or ""),
                }
            )

        rationale = str(parsed.get("rationale") or "")
        if not plan:
            raise ValueError("allocation_plan is empty")
        return {"rationale": rationale, "allocation_plan": plan}

    def _validate_plan(
        self,
        plan: Dict[str, Any],
        available_cash: float,
        current_prices: Optional[Dict[str, float]] = None,
        briefing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        items = plan.get("allocation_plan") or []
        current_prices = current_prices or {}
        stale_tickers: Dict[str, str] = {}
        for item in (briefing or {}).get("items", []):
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            if bool(item.get("analysis_skipped")):
                stale_tickers[ticker] = str(
                    item.get("summary") or "오늘 분석 없음 (데이터 미갱신)"
                )

        # Normalize duplicate tickers by keeping the latest entry.
        merged: Dict[str, Dict[str, Any]] = {}
        for item in items:
            merged[str(item["ticker"]).upper()] = item
        for ticker, reason in stale_tickers.items():
            if ticker in merged:
                continue
            merged[ticker] = {
                "ticker": ticker,
                "action": "HOLD",
                "allocation_pct": 0.0,
                "shares": 0.0,
                "rationale": f"{reason}; 기존 포지션 유지",
            }
        normalized = list(merged.values())

        # Enforce HOLD on stale-data tickers.
        for item in normalized:
            ticker = str(item.get("ticker") or "").upper()
            if ticker not in stale_tickers:
                continue
            reason = stale_tickers[ticker]
            item["action"] = "HOLD"
            item["allocation_pct"] = 0.0
            item["shares"] = 0.0
            prev = str(item.get("rationale") or "").strip()
            hold_reason = f"{reason}; 기존 포지션 유지"
            item["rationale"] = hold_reason if not prev else f"{prev} | {hold_reason}"

        # Cap total BUY allocation to 100%.
        buy_items = [x for x in normalized if x.get("action") == "BUY"]
        buy_alloc_sum = sum(float(x.get("allocation_pct") or 0.0) for x in buy_items)
        if buy_alloc_sum > 100.0 and buy_alloc_sum > 0:
            scale = 100.0 / buy_alloc_sum
            for item in buy_items:
                item["allocation_pct"] = round(float(item["allocation_pct"]) * scale, 2)

        # Ensure BUY shares do not exceed available cash when price is known.
        cash_left = max(float(available_cash), 0.0)
        for item in normalized:
            if item.get("action") != "BUY":
                continue
            ticker = item["ticker"]
            price = float(current_prices.get(ticker) or 0.0)
            shares = float(item.get("shares") or 0.0)
            if price <= 0:
                continue

            requested = shares * price
            if requested <= cash_left + 1e-9:
                cash_left -= requested
                continue

            # Fallback to allocation_pct-based max shares.
            alloc_budget = max(float(available_cash), 0.0) * (float(item["allocation_pct"]) / 100.0)
            budget = min(cash_left, alloc_budget) if alloc_budget > 0 else cash_left
            adjusted = max(budget / price, 0.0)
            item["shares"] = round(adjusted, 4)
            cash_left = max(cash_left - (item["shares"] * price), 0.0)

        return {
            "rationale": plan.get("rationale", ""),
            "allocation_plan": normalized,
        }

    def _inject_rag(self, briefing: Dict[str, Any]) -> str:
        if not self.hybrid_memory:
            return ""
        query = str(briefing.get("summary_text") or "").strip()
        if not query:
            return ""
        try:
            docs = self.hybrid_memory.get_memories_cross(
                query=query,
                primary_collection="portfolio_reflections",
                secondary_collection="analysis_reflections",
                primary_k=2,
                secondary_k=1,
            )
        except Exception as exc:
            logger.warning("PortfolioManagerAgent RAG injection failed: %s", exc)
            return ""

        if not docs:
            return ""

        lines = ["[과거 경험 요약]"]
        for idx, doc in enumerate(docs, 1):
            meta = doc.get("metadata") or {}
            source = meta.get("source_collection", "unknown")
            label = meta.get("outcome_label", "")
            lesson = str(doc.get("matched_situation") or "")[:180]
            lines.append(f"{idx}. ({source}) {label} {lesson}")
        return "\n".join(lines)

    def decide_allocation(
        self,
        briefing: Dict[str, Any],
        holdings: List[Dict[str, Any]],
        available_cash: float,
        exchange_rate: float,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Return validated allocation plan + rationale."""
        rag_context = self._inject_rag(briefing)
        last_error = None

        for attempt in range(self.retry_budget + 1):
            strict = attempt > 0
            prompt = self._build_prompt(
                briefing=briefing,
                holdings=holdings,
                available_cash=available_cash,
                exchange_rate=exchange_rate,
                rag_context=rag_context,
                strict=strict,
            )
            try:
                response = self.llm.invoke(prompt, config={"timeout": 180})
                content = response.content if hasattr(response, "content") else str(response)
                parsed = self._parse_plan(str(content))
                return self._validate_plan(
                    parsed,
                    available_cash,
                    current_prices=current_prices,
                    briefing=briefing,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "PortfolioManagerAgent parse failed (attempt %s/%s): %s",
                    attempt + 1,
                    self.retry_budget + 1,
                    exc,
                )

        logger.error("PortfolioManagerAgent fallback activated: %s", last_error)
        return self._fallback_plan(briefing, holdings)
