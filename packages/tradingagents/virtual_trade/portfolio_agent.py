"""Portfolio Agent for virtual trading decisions.

FR-022: Enhanced with HybridMemory RAG search and debiasing.

Independent agent (not part of LangGraph pipeline) that reviews:
- Current trading position (from DB)
- Analysis history (from DB reports)
- Latest pipeline decision + strategy JSON
- (Optional) Past experiences via HybridMemory RAG

Makes portfolio-level decision:
- No experience: MUST follow pipeline action, may adjust allocation_pct only
- With experience: strategy JSON serves as comparison basis for independent judgment
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel

from .trade_manager import TradeManager
from tradingagents.errors import DecisionParseError, AgentExecutionError

logger = logging.getLogger(__name__)

DEFAULT_INITIAL_CAPITAL = 5000.0


class PortfolioAgent:
    """Portfolio-level decision agent for virtual trading."""

    def __init__(
        self,
        llm: BaseChatModel,
        trade_manager: TradeManager,
        db,
        hybrid_memory=None,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ):
        """Initialize the portfolio agent.

        FR-030: Changed from report_store to db.
        FR-022: Added hybrid_memory for RAG search.

        Args:
            llm: LLM for decision making (should be deep_think_llm)
            trade_manager: TradeManager instance
            db: Database instance (for accessing repositories)
            hybrid_memory: Optional HybridMemory instance for RAG search
        """
        self.llm = llm
        self.trade_manager = trade_manager
        self.db = db
        self.hybrid_memory = hybrid_memory
        self.initial_capital = (
            float(initial_capital)
            if initial_capital is not None and float(initial_capital) > 0
            else DEFAULT_INITIAL_CAPITAL
        )
        self.rag_top_k = max(int(os.getenv("RAG_TOP_K", "1")), 1)

    def decide(
        self,
        ticker: str,
        pipeline_decision: str,
        pipeline_state: Dict[str, Any],
        current_price: float,
        context: Optional[Dict[str, Any]] = None,
        pipeline_strategy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make portfolio decision based on current state and pipeline recommendation.

        Args:
            ticker: Ticker symbol
            pipeline_decision: BUY | SELL | HOLD from G-ANT pipeline
            pipeline_state: Final state from propagate() (with all agent reports)
            current_price: Current stock price (for position sizing)
            context: Optional context dict with position info
            pipeline_strategy: Optional strategy JSON from Risk Judge

        Returns:
            Dict with:
                - action: BUY | SELL | HOLD
                - shares: float (for BUY action, LLM decides based on cash + price)
                - rationale: str
                - strategy_update: dict (stop_loss, target, next_action)
        """
        # FR-030: Load from DB instead of files
        from tradingagents.storage import (
            PositionRepository,
            TradeRepository,
            ReportRepository
        )

        position_repo = PositionRepository(self.db)
        trade_repo = TradeRepository(self.db)
        report_repo = ReportRepository(self.db)

        # Load current trade state
        trade_state = self.trade_manager.load(ticker)
        position = trade_state.get("position")

        # Load analysis history (recent reports)
        reports = []
        if position:
            reports = report_repo.get_by_position(position["id"])
            # Get recent 3 reports
            reports = reports[-3:] if len(reports) > 3 else reports

        # Get position summary
        position_summary = self.trade_manager.get_position_summary(ticker)

        # Calculate current position value if holding
        current_position_value = 0.0
        unrealized_return_pct = 0.0
        if position and position["shares"] > 0:
            position_calc = self.trade_manager.calculate_realized_return(
                ticker, current_price
            )
            current_position_value = position_calc["total_returned"]
            unrealized_return_pct = position_calc["realized_return_pct"]

        # FR-022: RAG search for past experiences (if hybrid_memory available)
        rag_context = ""
        has_experience = False
        rag_docs = None
        if self.hybrid_memory:
            try:
                query = self._build_rag_query(pipeline_state, ticker, context=context)
                memories = self.hybrid_memory.get_memories(query, n_matches=self.rag_top_k)

                if memories:
                    has_experience = True
                    rag_context = "\n**Past Experiences (from RAG):**\n"
                    rag_memories = []
                    for i, mem in enumerate(memories, 1):
                        outcome_label = mem["metadata"].get("outcome_label", "")
                        matched_situation = mem["matched_situation"][:200]
                        return_pct = mem["metadata"].get("return_pct")
                        rag_context += f"\n{i}. {outcome_label}\n"
                        rag_context += f"   Lessons: {matched_situation}...\n"
                        rag_context += f"   Return: {return_pct if return_pct is not None else 'N/A'}%\n"
                        rag_memories.append({
                            "reflection_id": mem["metadata"].get("reflection_id"),
                            "outcome_label": outcome_label,
                            "matched_situation": matched_situation,
                            "return_pct": return_pct,
                        })

                    import json
                    rag_docs = json.dumps({
                        "memories": rag_memories,
                        "raw_context": rag_context,
                    }, ensure_ascii=False)
                    logger.info(f"{ticker}: Found {len(memories)} relevant past experiences")
                else:
                    logger.info(f"{ticker}: No relevant past experiences found")

            except Exception as e:
                logger.warning(f"{ticker}: RAG search failed: {e}")
                rag_context = ""
                rag_docs = None

        ctx_capital = context.get("initial_capital") if context else None
        cash_available = self._get_cash_available(ticker, trade_repo, ctx_capital)

        # Build prompt
        prompt = self._build_prompt(
            ticker=ticker,
            position_summary=position_summary,
            trade_state=trade_state,
            current_price=current_price,
            current_position_value=current_position_value,
            unrealized_return_pct=unrealized_return_pct,
            reports=reports,
            pipeline_decision=pipeline_decision,
            pipeline_state=pipeline_state,
            cash_available=cash_available,
            rag_context=rag_context,
            pipeline_strategy=pipeline_strategy,
            has_experience=has_experience,
        )

        # Invoke LLM with timeout handling
        try:
            response = self.llm.invoke(prompt, config={"timeout": 600})
            decision_text = response.content

            # Parse decision
            decision = self._parse_decision(
                decision_text,
                trade_state,
                current_price,
                cash_available,
            )

            decision["rag_used"] = has_experience
            decision["rag_docs"] = rag_docs

            logger.info(
                f"Portfolio decision for {ticker}: {decision['action']} "
                f"(pipeline: {pipeline_decision})"
            )

            return decision

        except DecisionParseError:
            raise
        except Exception as e:
            logger.error(f"Portfolio agent LLM timeout or error: {e}")
            raise AgentExecutionError("Portfolio agent failed") from e

    def _build_rag_query(
        self,
        pipeline_state: Dict[str, Any],
        ticker: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build RAG query from pipeline state.

        FR-022: Extract key concepts from analysis for RAG search.

        Args:
            pipeline_state: Final state from propagate()
            ticker: Ticker symbol

        Returns:
            Query string for RAG search
        """
        # Extract key decision factors
        market_excerpt = pipeline_state.get("market_report", "")[:300]
        final_decision = pipeline_state.get("final_trade_decision", "")[:300]

        market = (context or {}).get("market")
        sector = (context or {}).get("sector")

        if not sector:
            try:
                import yfinance as yf

                info = yf.Ticker(ticker).info or {}
                sector = info.get("sector")
            except Exception as exc:
                logger.debug(f"{ticker}: Failed to enrich sector for RAG query: {exc}")

        context_parts = []
        if market:
            context_parts.append(f"Market: {market}")
        if sector:
            context_parts.append(f"Sector: {sector}")
        context_text = " ".join(context_parts).strip()

        query = f"{ticker} analysis: {market_excerpt} Decision: {final_decision}"
        if context_text:
            query = f"{query} {context_text}"

        return query

    def _build_prompt(
        self,
        ticker: str,
        position_summary: str,
        trade_state: Dict[str, Any],
        current_price: float,
        current_position_value: float,
        unrealized_return_pct: float,
        reports: list,
        pipeline_decision: str,
        pipeline_state: Dict[str, Any],
        cash_available: float,
        rag_context: str = "",
        pipeline_strategy: Optional[Dict[str, Any]] = None,
        has_experience: bool = False,
    ) -> str:
        """Build prompt for portfolio agent LLM.
        
        FR-020: 매도 수량 가이드 추가
        FR-022: RAG context + 분석(60):경험(40) 가중치 + 디바이어싱
        """

        # Extract position info
        position = trade_state.get("position")
        total_shares = position["shares"] if position else 0
        cash_available = max(cash_available, 0.0)

        # Format recent analysis history
        history_text = ""
        if reports:
            for r in reports:
                created_at = r.get("created_at")
                if isinstance(created_at, datetime):
                    created_str = created_at.date().isoformat()
                elif created_at:
                    created_str = str(created_at)[:10]
                else:
                    created_str = "-"
                # Format report summary
                history_text += f"\n- Cycle (created: {created_str})"
                if r.get('final_trade_decision'):
                    history_text += f"\n  Decision: {r['final_trade_decision'][:800]}..."
                if r.get('pa_opinion'):
                    history_text += f"\n  PA: {r['pa_opinion'][:800]}..."
        else:
            history_text = "\n(No prior analysis)"

        # Extract only final_trade_decision (NOT raw market/fundamentals)
        final_decision_excerpt = pipeline_state.get("final_trade_decision", "")[:500]

        # Format pipeline strategy JSON if available
        strategy_block = ""
        if pipeline_strategy:
            strategy_block = f"""
**파이프라인 전략 (구조화):**
```json
{json.dumps(pipeline_strategy, ensure_ascii=False, indent=2)}
```
"""
        else:
            strategy_block = "(전략 JSON 없음 — 최종결정 텍스트만 참고)"

        # Experience-based guidance
        if has_experience:
            experience_guidance = """
**의사결정 가중치:**
- 파이프라인 분석: 60% — 최신 시장 데이터 기반 객관적 평가
- 과거 경험 (RAG): 40% — 유사 상황의 성공/실패 교훈

**경험이 있으므로**, 파이프라인 전략과 과거 교훈을 비교하여 독립적으로 판단 가능합니다.
단, action을 변경하려면 반드시 명확한 과거 교훈에 근거해야 합니다.

**디바이어싱 가이드:**
- 최근 편향 방지: 직전 사이클 결과에 과도한 가중치 부여 금지
- 확증 편향 방지: 반대 근거도 반드시 고려
- 앵커링 방지: 현재 가격 ≠ 적정 가격
"""
        else:
            experience_guidance = """
**⚠️ 과거 경험이 없습니다.**
경험 데이터 없이 파이프라인 결정을 임의로 변경하는 것은 금지됩니다.

**필수 규칙:**
1. 파이프라인의 action(BUY/SELL/HOLD)을 **반드시 그대로 따라야** 합니다
2. allocation_pct(비중)만 조절할 수 있습니다
3. 파이프라인이 HOLD이면 반드시 HOLD를 출력하세요
4. 파이프라인이 BUY이면 반드시 BUY를 출력하세요
5. 파이프라인이 SELL이면 반드시 SELL를 출력하세요

전략 JSON의 allocation_pct가 있으면 그 값을 참고하되, 본인의 판단으로 조절 가능합니다.
"""

        prompt = f"""당신은 가상 트레이딩 시스템의 포트폴리오 매니저입니다. 파이프라인의 최종결정과 전략을 기반으로 실행 가능한 매매 결정을 내려주세요.

**현재 포트폴리오 상태:**
- 티커: {ticker}
- 포지션: {position_summary}
- 보유 주식 수: {total_shares}
- 현재가: ${current_price:.2f}
- 포지션 평가금액: ${current_position_value:.2f}
- 미실현 수익률: {unrealized_return_pct:.2f}%
- 포트폴리오 상태: {trade_state['status']}
- 가용 현금: ${cash_available:.2f}

**최근 분석 히스토리:**{history_text}

{rag_context}

**최신 G-ANT 파이프라인 최종결정:**
- 결정 (action): {pipeline_decision}
- 최종 결정 원문: {final_decision_excerpt}

{strategy_block}

{experience_guidance}

**결정 가이드라인:**
- BUY: allocation_pct로 비중 표현 (가용 현금 cash_available 대비 비중)
  * 25%(낮음), 50%(중간), 75%(높음)
- SELL: allocation_pct로 청산 비중 표현 (보유 주식 대비 비중)
  * 전량 청산: allocation_pct = 100
  * 부분 청산: allocation_pct = 25/50/75 등
  * 불확실하면 전량 청산 기본
- HOLD: 현 상태 유지 (strategy_update로 스탑로스/목표가 조정 가능)

**응답은 반드시 아래 JSON 형식만 출력하세요. JSON 외에 다른 텍스트를 포함하지 마세요:**
```json
{{{{
  "action": "BUY 또는 SELL 또는 HOLD",
  "allocation_pct": 0~100 정수,
  "shares": 0,
  "rationale": "2~3문장 (한국어)",
  "strategy_update": {{{{
    "stop_loss": 가격_또는_null,
    "target": 가격_또는_null,
    "next_action": "BUY 또는 SELL 또는 HOLD"
  }}}}
}}}}
```

반드시 한국어로 작성하세요."""

        return prompt

    def _parse_decision(
        self,
        decision_text: str,
        trade_state: Dict[str, Any],
        current_price: float,
        cash_available: float
    ) -> Dict[str, Any]:
        """Parse LLM JSON decision output.

        Expects JSON with: action, shares, rationale.
        Falls back to keyword detection if JSON parsing fails.

        Args:
            decision_text: Raw LLM output (should be JSON)
            trade_state: Current trade state
            current_price: Current price

        Returns:
            Parsed decision dict
        """
        import json
        import re

        text = decision_text.strip()

        # Try to extract JSON from the response
        parsed = None

        # 1. Try direct json.loads
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Try extracting JSON from markdown code block
        if not parsed:
            json_match = re.search(r'```(?:json)?\s*(.+?)\s*```', text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

        # 3. Try finding { ... } in the text
        if not parsed:
            brace_match = re.search(r'\{.+\}', text, re.DOTALL)
            if brace_match:
                try:
                    parsed = json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

        if not parsed or not isinstance(parsed, dict):
            raise DecisionParseError(
                "Failed to parse JSON from portfolio decision",
                raw_text=decision_text,
            )

        # Validate required fields
        action = str(parsed.get("action", "")).upper().strip()
        if action not in ["BUY", "SELL", "HOLD"]:
            raise DecisionParseError(
                f"Invalid action '{action}' in portfolio decision",
                raw_text=decision_text,
            )

        # Parse allocation_pct (preferred) and shares (fallback)
        raw_shares = parsed.get("shares", 0)
        allocation_pct = self._parse_allocation_pct(parsed.get("allocation_pct"))

        if allocation_pct is None and isinstance(raw_shares, str) and "%" in raw_shares:
            allocation_pct = self._parse_allocation_pct(raw_shares)

        shares = 0.0
        try:
            shares = float(str(raw_shares).replace("%", "").strip())
        except (ValueError, TypeError):
            shares = 0.0

        if allocation_pct is not None:
            shares = self._shares_from_allocation(
                action,
                allocation_pct,
                trade_state,
                current_price,
                cash_available,
            )
        elif action == "BUY" and shares > 0 and current_price > 0:
            max_shares = cash_available / current_price if cash_available > 0 else 0.0
            if shares > max_shares and shares <= 100:
                shares = self._shares_from_allocation(
                    action,
                    float(shares),
                    trade_state,
                    current_price,
                    cash_available,
                )
            elif shares > max_shares:
                shares = max_shares
        elif action == "SELL" and shares > 0:
            position = trade_state.get("position")
            total_shares = float(position.get("shares", 0)) if position else 0.0
            if total_shares > 0 and shares > total_shares and shares <= 100:
                shares = self._shares_from_allocation(
                    action,
                    float(shares),
                    trade_state,
                    current_price,
                    cash_available,
                )

        # BUY/SELL must have shares > 0
        if action in ["BUY", "SELL"] and shares <= 0:
            # Auto-calculate as fallback
            position = trade_state.get("position")
            if action == "BUY" and current_price > 0:
                shares = (cash_available * 0.5) / current_price if cash_available > 0 else 0.0
            elif action == "SELL" and position:
                shares = position["shares"]
            else:
                shares = 0.0

        rationale = str(parsed.get("rationale", decision_text[:200]))

        raw_strategy = parsed.get("strategy_update") or {}
        if isinstance(raw_strategy, str):
            try:
                raw_strategy = json.loads(raw_strategy)
            except Exception:
                raw_strategy = {}

        def _parse_price(val):
            if val is None:
                return None
            try:
                v = float(str(val).replace("$", "").replace(",", "").strip())
                return v if v > 0 else None
            except (ValueError, TypeError):
                return None

        strategy_update = {
            "stop_loss": _parse_price(raw_strategy.get("stop_loss")),
            "target": _parse_price(raw_strategy.get("target")),
            "next_action": action,
        }

        return {
            "action": action,
            "shares": self._round_shares(shares),
            "rationale": rationale,
            "strategy_update": strategy_update,
        }

    def _parse_allocation_pct(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text:
            return None
        text = text.replace("%", "").replace("pct", "").replace("percent", "")
        try:
            pct = float(text)
        except (ValueError, TypeError):
            return None
        if pct < 0:
            return None
        return pct

    def _shares_from_allocation(
        self,
        action: str,
        allocation_pct: float,
        trade_state: Dict[str, Any],
        current_price: float,
        cash_available: float,
    ) -> float:
        pct = max(min(float(allocation_pct), 100.0), 0.0)

        if action == "BUY":
            if current_price <= 0:
                return 0.0
            cash = max(cash_available, 0.0) * (pct / 100.0)
            shares = cash / current_price
            return self._round_shares(shares)

        if action == "SELL":
            position = trade_state.get("position")
            total_shares = float(position.get("shares", 0)) if position else 0.0
            if total_shares <= 0:
                return 0.0
            if pct >= 100.0:
                return self._round_shares(total_shares)
            shares = total_shares * (pct / 100.0)
            return self._round_shares(shares)

        return 0.0

    def _get_cash_available(
        self, ticker: str, trade_repo, initial_capital: float = None
    ) -> float:
        capital = float(initial_capital) if initial_capital else float(self.initial_capital)
        try:
            cash = trade_repo.get_cash_balance(ticker, capital)
            return max(float(cash), 0.0)
        except Exception as e:
            logger.warning(f"{ticker}: Failed to compute cash balance: {e}")
            return capital

    @staticmethod
    def _round_shares(value: float) -> float:
        return round(float(value), 2)

    def _fallback_decision(
        self,
        pipeline_decision: str,
        trade_state: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Fallback decision when LLM fails (FR-020: SELL → 전량 매도).

        Args:
            pipeline_decision: BUY | SELL | HOLD from pipeline
            trade_state: Current trade state
            current_price: Current price

        Returns:
            Conservative decision dict
        """
        action = pipeline_decision

        # Calculate shares based on action
        shares = 0
        if action == "BUY" and current_price > 0:
            # BUY: 50% of fixed capital
            shares = (self.initial_capital * 0.5) / current_price
        elif action == "SELL":
            # FR-020: SELL → 전량 매도
            position = trade_state.get("position")
            shares = position["shares"] if position else 0

        return {
            "action": action,
            "shares": self._round_shares(float(shares)) if shares else 0.0,
            "rationale": (
                f"Portfolio agent timeout, using pipeline decision directly: {action}"
            ),
            "strategy_update": {
                "stop_loss": None,
                "target": None,
                "next_action": action,
            },
        }


if __name__ == "__main__":
    # Example usage (requires LLM setup)
    print("PortfolioAgent requires LLM integration for testing.")
    print("See scheduler integration for full usage example.")
