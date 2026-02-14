# TradingAgents/graph/reflection.py

from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
import logging

logger = logging.getLogger(__name__)


class Reflector:
    """Handles reflection on closed positions and updating memory.
    
    FR-031: Centralized reflection - reflects on entire position lifecycle
    instead of per-agent reflections.
    """

    def __init__(self, deep_thinking_llm: BaseChatModel):
        """Initialize the reflector with an LLM.
        
        FR-031: Changed from quick_thinking_llm to deep_thinking_llm
        for comprehensive reflection on position lifecycle.
        """
        self.deep_thinking_llm = deep_thinking_llm
        self.reflection_system_prompt = self._get_reflection_prompt()

    def _get_reflection_prompt(self) -> str:
        """Get the system prompt for position-level reflection."""
        return """
You are an expert financial analyst tasked with reflecting on a complete trading position lifecycle.
You will be provided with:
1. All analysis summaries (from each cycle during the position)
2. Complete trade history (all BUY/SELL actions)
3. Final position outcome (return %, holding period, etc.)

Your goal is to provide a comprehensive reflection that:

1. **Cycle-by-Cycle Analysis**:
   - Review each analysis cycle's key points (market, fundamentals, debates, decisions)
   - Identify which analyses were accurate vs. inaccurate
   - Note how market conditions evolved over the holding period

2. **Trading Execution Review**:
   - Evaluate entry timing and sizing
   - Assess exit timing and execution
   - Identify if partial trades were optimal

3. **Key Lessons** (Most Important):
   - What worked well and why
   - What went wrong and why
   - Specific patterns to recognize in future (e.g., "Entering on RSI >70 led to immediate drawdown")
   - Sector/market context that was critical
   - Risk management insights

4. **Actionable Insights**:
   - Concrete recommendations for similar future scenarios
   - Warning signals to watch for
   - Optimal entry/exit criteria for this pattern

**Output Format**:
- Reflection: Comprehensive analysis (800-1200 tokens)
- Key Lessons: Concise summary for RAG queries (200-400 tokens, focus on actionable patterns)

Be specific, data-driven, and brutally honest. Focus on learnings that will improve future decisions.
"""

    def reflect_on_position(
        self,
        position_id: int,
        db,
        ticker: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reflect on a closed position's complete lifecycle.

        FR-031: Single reflection method replacing 5 per-agent reflections.

        Args:
            position_id: Position ID to reflect on
            db: Database instance (for accessing repositories)
            ticker: Optional ticker symbol (for logging)

        Returns:
            Dict with keys:
                - reflection: str (full reflection text)
                - key_lessons: str (concise lessons for RAG)
                - outcome: str ('win' or 'loss')
                - return_pct: float

        Raises:
            ValueError: If position not found or not closed
        """
        from tradingagents.storage import (
            PositionRepository,
            ReportRepository,
            TradeRepository
        )

        # Initialize repositories
        position_repo = PositionRepository(db)
        report_repo = ReportRepository(db)
        trade_repo = TradeRepository(db)

        # 1. Get position metadata
        position = position_repo.get_by_id(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        if position["status"] != "closed":
            raise ValueError(f"Position {position_id} is not closed (status={position['status']})")

        ticker = ticker or position["ticker"]
        return_pct = position.get("return_pct", 0.0)
        outcome = "win" if return_pct >= 0 else "loss"

        # 2. Get all reports for this position (전 사이클 요약)
        reports = report_repo.get_by_position(position_id)
        if not reports:
            raise ValueError(f"No reports found for position {position_id}")

        # 3. Get all trades for this position (매매 이력)
        trades = trade_repo.get_by_position(position_id)
        if not trades:
            raise ValueError(f"No trades found for position {position_id}")

        # 4. Build comprehensive context for LLM
        context = self._build_reflection_context(
            position=position,
            reports=reports,
            trades=trades,
            ticker=ticker
        )

        # 5. Invoke LLM for reflection
        messages = [
            ("system", self.reflection_system_prompt),
            ("human", context)
        ]

        try:
            response = self.deep_thinking_llm.invoke(messages)
            reflection_text = response.content

            # Parse reflection and key_lessons from response
            reflection, key_lessons = self._parse_reflection_output(reflection_text)

            logger.info(f"Generated reflection for position {position_id} ({ticker}): {outcome}")

            return {
                "reflection": reflection,
                "key_lessons": key_lessons,
                "outcome": outcome,
                "return_pct": return_pct
            }

        except Exception as e:
            logger.error(f"Reflection failed for position {position_id}: {e}")
            
            # Fallback: Generate basic reflection from data
            return {
                "reflection": f"Position {ticker} closed with {return_pct:.2f}% return. {len(reports)} analysis cycles, {len(trades)} trades.",
                "key_lessons": f"Position outcome: {outcome} ({return_pct:.2f}%)",
                "outcome": outcome,
                "return_pct": return_pct
            }

    def _build_reflection_context(
        self,
        position: Dict[str, Any],
        reports: list,
        trades: list,
        ticker: str
    ) -> str:
        """Build comprehensive context string for reflection LLM."""
        context = f"""
=== Position Reflection: {ticker} ===

**Position Metadata**:
- Position ID: {position['id']}
- Ticker: {ticker}
- Opened: {position['opened_at']}
- Closed: {position['closed_at']}
- Total Shares: {position['shares']}
- Avg Cost: ${position.get('avg_cost', 0):.2f}
- Return: {position.get('return_pct', 0):.2f}%
- Outcome: {"WIN ✅" if position.get('return_pct', 0) >= 0 else "LOSS ⚠️"}

"""

        # Trade history
        context += "\n**Trade History** (chronological):\n"
        for i, trade in enumerate(trades, 1):
            context += f"{i}. {trade['action']} {trade['shares']} shares @ ${trade['price']:.2f} on {trade['executed_at']}\n"

        # Analysis cycles (reports) - include key summaries only
        context += f"\n**Analysis Cycles** ({len(reports)} total):\n\n"
        for i, report in enumerate(reports, 1):
            context += f"--- Cycle {i} ({report['created_at']}) ---\n\n"

            if report.get('market_report'):
                context += f"Market: {report['market_report'][:300]}...\n\n"
            
            if report.get('final_trade_decision'):
                context += f"Final Decision: {report['final_trade_decision'][:300]}...\n\n"

            if report.get('pa_opinion'):
                context += f"PA Opinion: {report['pa_opinion'][:300]}...\n\n"

            context += "\n"

        context += """
**Your Task**:
Reflect on this complete position lifecycle. Analyze what worked, what didn't, and extract actionable lessons.

Provide output in this format:

**Reflection**:
[Comprehensive analysis here - 800-1200 tokens]

**Key Lessons**:
[Concise, actionable insights - 200-400 tokens]
"""

        return context

    def _parse_reflection_output(self, reflection_text: str) -> tuple[str, str]:
        """Parse LLM reflection output into reflection and key_lessons."""
        # Try to split by "Key Lessons:" marker
        parts = reflection_text.split("**Key Lessons**:")
        
        if len(parts) == 2:
            # Successfully split
            reflection = parts[0].replace("**Reflection**:", "").strip()
            key_lessons = parts[1].strip()
        else:
            # Fallback: Use entire text as reflection, extract last paragraph as lessons
            lines = reflection_text.strip().split('\n')
            if len(lines) > 10:
                # Last 5 lines as key_lessons
                reflection = '\n'.join(lines[:-5]).strip()
                key_lessons = '\n'.join(lines[-5:]).strip()
            else:
                # Too short, use entire text for both
                reflection = reflection_text.strip()
                key_lessons = reflection_text.strip()[:500]

        return reflection, key_lessons


    # ===== Legacy methods (DEPRECATED in FR-031) =====
    # Kept for backward compatibility only

    def _extract_current_situation(self, current_state: Dict[str, Any]) -> str:
        """DEPRECATED: Legacy method for backward compatibility."""
        curr_market_report = current_state.get("market_report", "")
        curr_sentiment_report = current_state.get("sentiment_report", "")
        curr_news_report = current_state.get("news_report", "")
        curr_fundamentals_report = current_state.get("fundamentals_report", "")
        return f"{curr_market_report}\n\n{curr_sentiment_report}\n\n{curr_news_report}\n\n{curr_fundamentals_report}"

    def _reflect_on_component(self, component_type: str, report: str, situation: str, context: dict) -> str:
        """DEPRECATED: Legacy method - no longer used (FR-031)."""
        logger.warning(f"_reflect_on_component called for {component_type} - deprecated (FR-031)")
        return ""

    def reflect_bull_researcher(self, current_state, context, bull_memory):
        """DEPRECATED: Legacy method - no longer used (FR-031)."""
        logger.warning("reflect_bull_researcher deprecated (FR-031) - use reflect_on_position")

    def reflect_bear_researcher(self, current_state, context, bear_memory):
        """DEPRECATED: Legacy method - no longer used (FR-031)."""
        logger.warning("reflect_bear_researcher deprecated (FR-031) - use reflect_on_position")

    def reflect_trader(self, current_state, context, trader_memory):
        """DEPRECATED: Legacy method - no longer used (FR-031)."""
        logger.warning("reflect_trader deprecated (FR-031) - use reflect_on_position")

    def reflect_invest_judge(self, current_state, context, invest_judge_memory):
        """DEPRECATED: Legacy method - no longer used (FR-031)."""
        logger.warning("reflect_invest_judge deprecated (FR-031) - use reflect_on_position")

    def reflect_risk_manager(self, current_state, context, risk_manager_memory):
        """DEPRECATED: Legacy method - no longer used (FR-031)."""
        logger.warning("reflect_risk_manager deprecated (FR-031) - use reflect_on_position")
