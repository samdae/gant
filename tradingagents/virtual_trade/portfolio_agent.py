"""Portfolio Agent for virtual trading decisions.

Independent agent (not part of LangGraph pipeline) that reviews:
- Current trading position (trade.json)
- Analysis history (reports.json)
- Latest pipeline decision
- Past trading memories (HybridMemory) — FR-022

Makes portfolio-level decision:
- BUY: Open new position or add to existing
- SELL: Close all positions
- HOLD: Maintain current position
- MODIFY: Adjust strategy parameters

Uses deep_think_llm for comprehensive analysis.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel

from .trade_manager import TradeManager
from .report_store import ReportStore

logger = logging.getLogger(__name__)


class PortfolioAgent:
    """Portfolio-level decision agent for virtual trading."""

    def __init__(
        self,
        llm: BaseChatModel,
        trade_manager: TradeManager,
        report_store: ReportStore,
        hybrid_memory=None  # FR-022: Optional HybridMemory instance
    ):
        """Initialize the portfolio agent.

        Args:
            llm: LLM for decision making (should be deep_think_llm)
            trade_manager: TradeManager instance
            report_store: ReportStore instance
            hybrid_memory: HybridMemory instance for past trading experience (optional)
        """
        self.llm = llm
        self.trade_manager = trade_manager
        self.report_store = report_store
        self.hybrid_memory = hybrid_memory  # FR-022

    def decide(
        self,
        ticker: str,
        pipeline_decision: str,
        pipeline_state: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Make portfolio decision based on current state and pipeline recommendation.

        Args:
            ticker: Ticker symbol
            pipeline_decision: BUY | SELL | HOLD from G-ANT pipeline
            pipeline_state: Final state from propagate() (with all agent reports)
            current_price: Current stock price (for position sizing)

        Returns:
            Dict with:
                - action: BUY | SELL | HOLD | MODIFY
                - shares: int (for BUY action, LLM decides based on cash + price)
                - rationale: str
                - strategy_update: dict (stop_loss, target, next_action)
        """
        # Load current trade state
        trade_state = self.trade_manager.load(ticker)

        # Load analysis history
        reports = self.report_store.load(ticker)

        # Get position summary
        position_summary = self.trade_manager.get_position_summary(ticker)

        # Calculate current position value if holding
        current_position_value = 0.0
        unrealized_return_pct = 0.0
        if trade_state["positions"]:
            position_calc = self.trade_manager.calculate_realized_return(
                ticker, current_price
            )
            current_position_value = position_calc["total_returned"]
            unrealized_return_pct = position_calc["realized_return_pct"]

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

        except Exception as e:
            logger.error(f"Portfolio agent LLM timeout or error: {e}")
            # Fallback: Use pipeline decision directly
            return self._fallback_decision(
                pipeline_decision, trade_state, current_price
            )

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
    ) -> str:
        """Build prompt for portfolio agent LLM."""

        # Extract recent reports (last 3)
        recent_reports = reports[-3:] if len(reports) > 3 else reports

        # Format recent analysis history
        history_text = ""
        if recent_reports:
            for r in recent_reports:
                history_text += f"\n- {r['date']} (Analysis #{r['analysis_no']}): {r['decision']}"
                history_text += f"\n  Strategy: {r['strategy_summary']}"
                history_text += f"\n  Had Memory: {r['has_memory']}"
        else:
            history_text = "\n(No prior analysis)"

        # Extract pipeline state excerpts
        market_excerpt = pipeline_state.get("market_report", "")[:500]
        sentiment_excerpt = pipeline_state.get("sentiment_report", "")[:500]
        final_decision_excerpt = pipeline_state.get("final_trade_decision", "")[:500]

        # FR-022: Query HybridMemory for past trading experience
        past_experience_text = ""
        if self.hybrid_memory:
            # Build query from current situation
            situation_query = f"{market_excerpt}\n{sentiment_excerpt}"
            past_memories = self.hybrid_memory.get_memories(situation_query, n_matches=2)
            
            if past_memories:
                past_experience_text = "\n\n**Past Trading Experience:**"
                for i, mem in enumerate(past_memories, 1):
                    past_experience_text += f"\n{i}. Situation: {mem.get('matched_situation', '')[:200]}"
                    past_experience_text += f"\n   Lesson: {mem.get('recommendation', '')[:200]}"
            else:
                past_experience_text = "\n\n**Past Trading Experience:** No similar situations found."
        else:
            past_experience_text = ""

        prompt = f"""You are a Portfolio Manager for a virtual trading system. Your role is to review the current portfolio state, recent analysis history, past trading experience, and the latest AI pipeline recommendation to make a final trading decision.

**IMPORTANT: Decision-Making Framework (FR-022):**
- Weight analysis results (current market data, sentiment, fundamentals): 60%
- Weight past trading experience (lessons learned from similar situations): 40%
- Avoid position bias: Do not let current holdings influence your judgment unfairly
- Learn from past mistakes: Use past experience to avoid repeating failures

**Current Portfolio State:**
- Ticker: {ticker}
- Position: {position_summary}
- Cash Available: ${trade_state['cash']:.2f}
- Current Stock Price: ${current_price:.2f}
- Current Position Value: ${current_position_value:.2f}
- Unrealized Return: {unrealized_return_pct:.2f}%
- Portfolio Status: {trade_state['status']}

**Recent Analysis History:**{history_text}{past_experience_text}

**Latest G-ANT Pipeline Recommendation:**
- Decision: {pipeline_decision}
- Market Report Excerpt: {market_excerpt}
- Sentiment Report Excerpt: {sentiment_excerpt}
- Final Decision Excerpt: {final_decision_excerpt}

**Your Task:**
1. Review the current position and recent performance
2. Consider the analysis history and whether past decisions were successful
3. Learn from past trading experience (if available) — use failures as cautionary tales
4. Evaluate the latest pipeline recommendation in context
5. Make a portfolio-level decision: BUY, SELL, HOLD, or MODIFY

**Decision Guidelines:**
- BUY: If pipeline recommends BUY and we have cash available
  * Decide how many shares to buy based on available cash and current price
  * Suggest position sizing (e.g., 25%, 50%, 75% of available cash)
  * For partial buy strategies, specify exact shares (not 0)
- SELL: If pipeline recommends SELL or if stop-loss/target conditions are met
  * Decide whether to close all positions or partial sell
  * Specify shares: 0 or missing = close all positions (전량 매도)
  * Specify exact shares > 0 for partial sell (e.g., 50% of holdings for profit-taking)
- HOLD: If maintaining current position is prudent
  * No new trades, continue monitoring
- MODIFY: If strategy parameters need adjustment
  * Update stop-loss, target, or next action

**Output Format (STRICT):**
ACTION: [BUY|SELL|HOLD|MODIFY]
SHARES: [number of shares if BUY or partial SELL, 0 or omit for full SELL]
RATIONALE: [2-3 sentences explaining your decision, referencing both current analysis (60%) and past experience (40%) if available]
STRATEGY_UPDATE:
  stop_loss: [price or null]
  target: [price or null]
  next_action: [BUY|SELL|HOLD]

Think carefully and provide a decisive recommendation. Avoid letting your current position bias your judgment."""

        return prompt

    def _parse_decision(
        self,
        decision_text: str,
        trade_state: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Parse LLM decision output.

        Args:
            decision_text: Raw LLM output
            trade_state: Current trade state (for fallback)
            current_price: Current price (for fallback)

        Returns:
            Parsed decision dict
        """
        lines = decision_text.strip().split('\n')

        # Default values
        action = "HOLD"
        shares = 0
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

        # Validation: If BUY but shares = 0, calculate default (50% of cash)
        if action == "BUY" and shares == 0:
            if current_price > 0 and trade_state["cash"] > 0:
                shares = int((trade_state["cash"] * 0.5) / current_price)
                logger.warning(
                    f"BUY action but shares=0, defaulting to 50% of cash: {shares} shares"
                )

        # FR-020 Fallback: If SELL but shares = 0, treat as full sell
        if action == "SELL" and shares == 0:
            total_shares = sum(pos["shares"] for pos in trade_state["positions"])
            if total_shares > 0:
                shares = total_shares
                logger.info(
                    f"SELL action with shares=0, treating as full sell: {shares} shares"
                )

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
        """Fallback decision when LLM fails.

        Args:
            pipeline_decision: BUY | SELL | HOLD from pipeline
            trade_state: Current trade state
            current_price: Current price

        Returns:
            Conservative decision dict
        """
        action = pipeline_decision

        # Calculate shares for BUY (50% of cash) or SELL (all shares)
        shares = 0
        if action == "BUY" and current_price > 0:
            shares = int((trade_state["cash"] * 0.5) / current_price)
        elif action == "SELL":
            # FR-020: SELL timeout → full sell (all shares)
            shares = sum(pos["shares"] for pos in trade_state["positions"])

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
