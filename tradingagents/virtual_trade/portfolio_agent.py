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

        prompt = f"""You are a Portfolio Manager for a virtual trading system. Your role is to review the current portfolio state, recent analysis history, past trading experiences, and the latest AI pipeline recommendation to make a final trading decision.

**Current Portfolio State:**
- Ticker: {ticker}
- Position: {position_summary}
- Total Shares Held: {total_shares}
- Current Stock Price: ${current_price:.2f}
- Current Position Value: ${current_position_value:.2f}
- Unrealized Return: {unrealized_return_pct:.2f}%
- Portfolio Status: {trade_state['status']}

**Recent Analysis History:**{history_text}

{rag_context}

**Latest G-ANT Pipeline Recommendation (60% weight):**
- Decision: {pipeline_decision}
- Market Analysis: {market_excerpt}
- Fundamentals: {fundamentals_excerpt}
- Final Decision: {final_decision_excerpt}

{weighting_guidance}

**Your Task:**
1. Review the current position and recent performance
2. Consider past experiences (if any) and extract relevant lessons
3. Evaluate the latest pipeline recommendation with 60:40 weighting
4. Apply debiasing guidelines to avoid common cognitive errors
5. Make a portfolio-level decision: BUY, SELL, HOLD, or MODIFY

**Decision Guidelines:**
- BUY: If pipeline recommends BUY
  * Decide position sizing based on conviction and risk
  * Consider: 25% (low conviction), 50% (medium), 75% (high conviction)
- SELL: If pipeline recommends SELL or if risk management criteria met
  * **Choose FULL or PARTIAL liquidation:**
    - Full liquidation: SHARES = {total_shares} (close entire position)
    - Partial liquidation: SHARES = <number> (e.g., 50% for profit-taking, 25% for risk reduction)
  * Consider market conditions and profit levels
  * If unsure, default to FULL liquidation
- HOLD: If maintaining current position is prudent
  * No new trades, continue monitoring
- MODIFY: If strategy parameters need adjustment
  * Update stop-loss, target, or next action

**Output Format (STRICT):**
ACTION: [BUY|SELL|HOLD|MODIFY]
SHARES: [number of shares - REQUIRED for BUY and SELL, 0 for HOLD/MODIFY]
RATIONALE: [2-3 sentences explaining your decision, reference both analysis and experience]
STRATEGY_UPDATE:
  stop_loss: [price or null]
  target: [price or null]
  next_action: [BUY|SELL|HOLD]

**IMPORTANT for SELL:**
- You MUST specify SHARES (number of shares to sell)
- SHARES = 0 or SHARES >= {total_shares} will be interpreted as FULL liquidation
- For partial sell: SHARES = <specific number less than {total_shares}>

Think carefully, apply the 60:40 weighting, and provide a decisive recommendation."""

        return prompt

    def _parse_decision(
        self,
        decision_text: str,
        trade_state: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Parse LLM decision output (FR-020: SELL shares=0 → 전량 매도 fallback).

        Args:
            decision_text: Raw LLM output
            trade_state: Current trade state (for fallback)
            current_price: Current price (for fallback)

        Returns:
            Parsed decision dict
        """
        lines = decision_text.strip().split('\n')

        # Default values
        action = None
        shares = None
        rationale = decision_text[:200]  # Fallback
        strategy_update = {
            "stop_loss": None,
            "target": None,
            "next_action": "HOLD"
        }

        # Parse line by line
        for line in lines:
            line = line.strip()

            if line.startswith("ACTION:"):
                action_str = line.split(":", 1)[1].strip().upper()
                if action_str in ["BUY", "SELL", "HOLD", "MODIFY"]:
                    action = action_str

            elif line.startswith("SHARES:"):
                try:
                    shares = int(line.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    shares = 0

            elif line.startswith("RATIONALE:"):
                rationale = line.split(":", 1)[1].strip()

            elif line.startswith("stop_loss:"):
                try:
                    value = line.split(":", 1)[1].strip()
                    if value.lower() not in ["null", "none"]:
                        strategy_update["stop_loss"] = float(value)
                except (ValueError, IndexError):
                    pass

            elif line.startswith("target:"):
                try:
                    value = line.split(":", 1)[1].strip()
                    if value.lower() not in ["null", "none"]:
                        strategy_update["target"] = float(value)
                except (ValueError, IndexError):
                    pass

            elif line.startswith("next_action:"):
                next_action = line.split(":", 1)[1].strip().upper()
                if next_action in ["BUY", "SELL", "HOLD"]:
                    strategy_update["next_action"] = next_action

        if action not in ["BUY", "SELL", "HOLD", "MODIFY"]:
            raise DecisionParseError(
                "Missing or invalid ACTION in portfolio decision",
                raw_text=decision_text,
            )

        if action in ["BUY", "SELL"]:
            if shares is None or shares <= 0:
                raise DecisionParseError(
                    f"Invalid SHARES for {action} decision",
                    raw_text=decision_text,
                )
        else:
            # HOLD/MODIFY do not require shares
            shares = shares or 0

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
