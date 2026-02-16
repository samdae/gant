"""Portfolio Agent for virtual trading decisions.

FR-022: Enhanced with HybridMemory RAG search and debiasing.

Independent agent (not part of LangGraph pipeline) that reviews:
- Current trading position (from DB)
- Analysis history (from DB reports)
- Latest pipeline decision
- (Optional) Past experiences via HybridMemory RAG

Makes portfolio-level decision with 60:40 weighting (analysis:experience).
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel

from .trade_manager import TradeManager
from tradingagents.errors import DecisionParseError, AgentExecutionError

logger = logging.getLogger(__name__)

DEFAULT_INITIAL_CAPITAL = 1000.0


class PortfolioAgent:
    """Portfolio-level decision agent for virtual trading."""

    def __init__(
        self,
        llm: BaseChatModel,
        trade_manager: TradeManager,
        db,
        hybrid_memory=None
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

    def decide(
        self,
        ticker: str,
        pipeline_decision: str,
        pipeline_state: Dict[str, Any],
        current_price: float,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make portfolio decision based on current state and pipeline recommendation.

        FR-022: Enhanced with HybridMemory RAG search.

        Args:
            ticker: Ticker symbol
            pipeline_decision: BUY | SELL | HOLD from G-ANT pipeline
            pipeline_state: Final state from propagate() (with all agent reports)
            current_price: Current stock price (for position sizing)
            context: Optional context dict with position info

        Returns:
            Dict with:
                - action: BUY | SELL | HOLD | MODIFY
                - shares: int (for BUY action, LLM decides based on cash + price)
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
        if self.hybrid_memory:
            try:
                # Build query from pipeline state
                query = self._build_rag_query(pipeline_state, ticker)
                
                # Search for relevant past experiences
                memories = self.hybrid_memory.get_memories(query, n_matches=3)
                
                if memories:
                    rag_context = "\n**Past Experiences (from RAG):**\n"
                    for i, mem in enumerate(memories, 1):
                        outcome_label = mem["metadata"].get("outcome_label", "")
                        rag_context += f"\n{i}. {outcome_label}\n"
                        rag_context += f"   Lessons: {mem['matched_situation'][:200]}...\n"
                        rag_context += f"   Return: {mem['metadata'].get('return_pct', 'N/A')}%\n"
                    
                    logger.info(f"{ticker}: Found {len(memories)} relevant past experiences")
                else:
                    logger.info(f"{ticker}: No relevant past experiences found")

            except Exception as e:
                logger.warning(f"{ticker}: RAG search failed: {e}")
                rag_context = ""

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
            rag_context=rag_context  # FR-022: Add RAG context
        )

        # Invoke LLM with timeout handling
        try:
            response = self.llm.invoke(prompt, config={"timeout": 600})
            decision_text = response.content

            # Parse decision
            decision = self._parse_decision(decision_text, trade_state, current_price)

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

    def _build_rag_query(self, pipeline_state: Dict[str, Any], ticker: str) -> str:
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

        # Build query focusing on decision pattern
        query = f"{ticker} analysis: {market_excerpt} Decision: {final_decision}"
        
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
        rag_context: str = ""
    ) -> str:
        """Build prompt for portfolio agent LLM.
        
        FR-020: 매도 수량 가이드 추가
        FR-022: RAG context + 분석(60):경험(40) 가중치 + 디바이어싱
        """

        # Extract position info
        position = trade_state.get("position")
        total_shares = position["shares"] if position else 0
        cash_available = 0.0  # FR-030: No cash tracking in DB, use unlimited for now

        # Format recent analysis history
        history_text = ""
        if reports:
            for r in reports:
                # Format report summary
                history_text += f"\n- Cycle (created: {r['created_at'][:10]})"
                if r.get('final_trade_decision'):
                    history_text += f"\n  Decision: {r['final_trade_decision'][:150]}..."
                if r.get('pa_opinion'):
                    history_text += f"\n  PA: {r['pa_opinion'][:150]}..."
        else:
            history_text = "\n(No prior analysis)"

        # Extract pipeline state excerpts
        market_excerpt = pipeline_state.get("market_report", "")[:500]
        fundamentals_excerpt = pipeline_state.get("fundamentals_report", "")[:500]
        final_decision_excerpt = pipeline_state.get("final_trade_decision", "")[:500]

        # FR-022: Build weighted decision framework
        weighting_guidance = """
**Decision Weighting Framework (FR-022)**:
- Current Analysis (G-ANT pipeline): 60% weight
  - Fresh data, objective market assessment
  - Technical + fundamental + sentiment combined
- Past Experiences (RAG memories): 40% weight
  - Historical patterns and lessons learned
  - Success/failure cases in similar contexts

**Debiasing Guidelines**:
- Avoid recency bias: Don't overweight last cycle's outcome
- Avoid confirmation bias: Consider contradicting evidence
- Avoid anchoring: Current price ≠ "correct" price
"""

        prompt = f"""당신은 가상 트레이딩 시스템의 포트폴리오 매니저입니다. 현재 포지션 상태, 최근 분석 히스토리, 과거 경험, 최신 파이프라인 추천을 종합해 최종 의사결정을 내려주세요.

**현재 포트폴리오 상태:**
- 티커: {ticker}
- 포지션: {position_summary}
- 보유 주식 수: {total_shares}
- 현재가: ${current_price:.2f}
- 포지션 평가금액: ${current_position_value:.2f}
- 미실현 수익률: {unrealized_return_pct:.2f}%
- 포트폴리오 상태: {trade_state['status']}

**최근 분석 히스토리:**{history_text}

{rag_context}

**최신 G-ANT 파이프라인 추천 (가중치 60%):**
- 결정: {pipeline_decision}
- 시장 분석: {market_excerpt}
- 펀더멘털: {fundamentals_excerpt}
- 최종 결정 요약: {final_decision_excerpt}

{weighting_guidance}

**당신의 작업:**
1. 현재 포지션과 최근 성과를 검토
2. 과거 경험이 있으면 핵심 교훈 추출
3. 최신 파이프라인 추천을 60:40 비중으로 평가
4. 디바이어싱 가이드를 적용
5. 포트폴리오 레벨에서 BUY/SELL/HOLD/MODIFY 결정

**결정 가이드라인:**
- BUY: 파이프라인이 BUY 추천일 때
  * 확신도/리스크에 따라 포지션 규모 결정
  * 참고: 25%(낮음), 50%(중간), 75%(높음)
- SELL: 파이프라인이 SELL이거나 리스크 관리 필요할 때
  * **전량/부분 청산 선택:**
    - 전량 청산: shares = {total_shares}
    - 부분 청산: shares = 구체적 수량
  * 불확실하면 전량 청산 기본
- HOLD: 현 상태 유지가 합리적일 때
- MODIFY: 스탑로스/목표가/다음 행동 조정

**SELL 중요:**
- 반드시 shares 지정
- shares = 0 또는 shares >= {total_shares} → 전량 청산으로 해석
- 부분 청산: shares = {total_shares}보다 작은 구체적 수량

**응답은 반드시 아래 JSON 형식만 출력하세요. JSON 외에 다른 텍스트를 포함하지 마세요:**
```json
{{{{
  "action": "BUY 또는 SELL 또는 HOLD 또는 MODIFY",
  "shares": 정수,
  "rationale": "2~3문장, 분석과 경험 모두 언급 (한국어)",
  "strategy_update": {{{{
    "stop_loss": 가격_또는_null,
    "target": 가격_또는_null,
    "next_action": "BUY 또는 SELL 또는 HOLD"
  }}}}
}}}}
```

예시:
```json
{{{{
  "action": "BUY",
  "shares": 50,
  "rationale": "파이프라인이 강력한 매수 신호를 보내고 있으며, 펀더멘털 지표가 양호합니다.",
  "strategy_update": {{{{"stop_loss": 145.0, "target": 180.0, "next_action": "HOLD"}}}}
}}}}
```

반드시 한국어로 작성하세요."""

        return prompt

    def _parse_decision(
        self,
        decision_text: str,
        trade_state: Dict[str, Any],
        current_price: float
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

        # Parse shares (handle string/int/float)
        raw_shares = parsed.get("shares", 0)
        try:
            shares = int(float(str(raw_shares).replace("%", "").strip()))
        except (ValueError, TypeError):
            shares = 0

        # BUY/SELL must have shares > 0
        if action in ["BUY", "SELL"] and shares <= 0:
            # Auto-calculate as fallback
            position = trade_state.get("position")
            if action == "BUY" and current_price > 0:
                shares = int((DEFAULT_INITIAL_CAPITAL * 0.5) / current_price)
                shares = max(shares, 1)
            elif action == "SELL" and position:
                shares = position["shares"]
            else:
                shares = 0

        rationale = str(parsed.get("rationale", decision_text[:200]))

        strategy_update = {
            "stop_loss": None,
            "target": None,
            "next_action": action,
        }

        return {
            "action": action,
            "shares": shares,
            "rationale": rationale,
            "strategy_update": strategy_update,
        }

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
            shares = int((DEFAULT_INITIAL_CAPITAL * 0.5) / current_price)
            if shares < 1:
                shares = 1
        elif action == "SELL":
            # FR-020: SELL → 전량 매도
            position = trade_state.get("position")
            shares = position["shares"] if position else 0

        return {
            "action": action,
            "shares": shares,
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
