"""Portfolio Agent for virtual trading decisions.

Independent agent (not part of LangGraph pipeline) that reviews:
- Current trading position (trade.json)
- Analysis history (reports.json)
- Latest pipeline decision

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
        report_store: ReportStore
    ):
        """Initialize the portfolio agent.

        Args:
            llm: LLM for decision making (should be deep_think_llm)
            trade_manager: TradeManager instance
            report_store: ReportStore instance
        """
        self.llm = llm
        self.trade_manager = trade_manager
        self.report_store = report_store

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

        prompt = f"""You are a Portfolio Manager for a virtual trading system. Your role is to review the current portfolio state, recent analysis history, and the latest AI pipeline recommendation to make a final trading decision.

**Current Portfolio State:**
- Ticker: {ticker}
- Position: {position_summary}
- Cash Available: ${trade_state['cash']:.2f}
- Current Stock Price: ${current_price:.2f}
- Current Position Value: ${current_position_value:.2f}
- Unrealized Return: {unrealized_return_pct:.2f}%
- Portfolio Status: {trade_state['status']}

**Recent Analysis History:**{history_text}

**Latest G-ANT Pipeline Recommendation:**
- Decision: {pipeline_decision}
- Market Report Excerpt: {market_excerpt}
- Sentiment Report Excerpt: {sentiment_excerpt}
- Final Decision Excerpt: {final_decision_excerpt}

**Your Task:**
1. Review the current position and recent performance
2. Consider the analysis history and whether past decisions were successful
3. Evaluate the latest pipeline recommendation in context
4. Make a portfolio-level decision: BUY, SELL, HOLD, or MODIFY

**Decision Guidelines:**
- BUY: If pipeline recommends BUY and we have cash available
  * Decide how many shares to buy based on available cash and current price
  * Suggest position sizing (e.g., 25%, 50%, 75% of available cash)
- SELL: If pipeline recommends SELL or if stop-loss/target conditions are met
  * Close all positions and realize gains/losses
- HOLD: If maintaining current position is prudent
  * No new trades, continue monitoring
- MODIFY: If strategy parameters need adjustment
  * Update stop-loss, target, or next action

**Output Format (STRICT):**
ACTION: [BUY|SELL|HOLD|MODIFY]
SHARES: [number of shares if BUY, 0 otherwise]
RATIONALE: [2-3 sentences explaining your decision]
STRATEGY_UPDATE:
  stop_loss: [price or null]
  target: [price or null]
  next_action: [BUY|SELL|HOLD]

Think carefully and provide a decisive recommendation."""

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

        # Calculate shares for BUY (50% of cash)
        shares = 0
        if action == "BUY" and current_price > 0:
            shares = int((trade_state["cash"] * 0.5) / current_price)

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
