# TradingAgents/graph/reflection.py

from typing import Dict, Any
from langchain_core.language_models import BaseChatModel


class Reflector:
    """Handles reflection on decisions and updating memory."""

    def __init__(self, quick_thinking_llm: BaseChatModel):
        """Initialize the reflector with an LLM."""
        self.quick_thinking_llm = quick_thinking_llm
        self.reflection_system_prompt = self._get_reflection_prompt()

    def _get_reflection_prompt(self) -> str:
        """Get the system prompt for reflection."""
        return """
You are an expert financial analyst tasked with reviewing trading decisions/analysis and providing a comprehensive, step-by-step analysis. 
Your goal is to deliver detailed insights into investment decisions and highlight opportunities for improvement, adhering strictly to the following guidelines:

1. Reasoning:
   - For each trading decision, determine whether it was correct or incorrect. A correct decision results in an increase in returns, while an incorrect decision does the opposite.
   - Analyze the contributing factors to each success or mistake. Consider:
     - Market intelligence.
     - Technical indicators.
     - Technical signals.
     - Price movement analysis.
     - Overall market data analysis 
     - News analysis.
     - Social media and sentiment analysis.
     - Fundamental data analysis.
     - Weight the importance of each factor in the decision-making process.

2. Improvement:
   - For any incorrect decisions, propose revisions to maximize returns.
   - Provide a detailed list of corrective actions or improvements, including specific recommendations (e.g., changing a decision from HOLD to BUY on a particular date).

3. Summary:
   - Summarize the lessons learned from the successes and mistakes.
   - Highlight how these lessons can be adapted for future trading scenarios and draw connections between similar situations to apply the knowledge gained.

4. Query:
   - Extract key insights from the summary into a concise sentence of no more than 1000 tokens.
   - Ensure the condensed sentence captures the essence of the lessons and reasoning for easy reference.

Adhere strictly to these instructions, and ensure your output is detailed, accurate, and actionable. You will also be given objective descriptions of the market from a price movements, technical indicator, news, and sentiment perspective to provide more context for your analysis.
"""

    def _extract_current_situation(self, current_state: Dict[str, Any]) -> str:
        """Extract the current market situation from the state."""
        curr_market_report = current_state["market_report"]
        curr_sentiment_report = current_state["sentiment_report"]
        curr_news_report = current_state["news_report"]
        curr_fundamentals_report = current_state["fundamentals_report"]

        return f"{curr_market_report}\n\n{curr_sentiment_report}\n\n{curr_news_report}\n\n{curr_fundamentals_report}"

    def _reflect_on_component(
        self, component_type: str, report: str, situation: str, context: dict
    ) -> str:
        """Generate reflection for a component.

        Args:
            component_type: Type of component (BULL, BEAR, TRADER, etc.)
            report: Analysis/decision text from the component
            situation: Objective market reports for reference
            context: Structured context dict with keys:
                - return_pct (float, required)
                - ticker (str, optional)
                - holding_days (int, optional)
                - analysis_count (int, optional)
                - market_condition (str, optional)
                - has_memory (bool, optional)
        """
        # Build structured context block (FR-018)
        context_lines = [f"Returns: {context.get('return_pct', 'N/A')}%"]

        if "ticker" in context:
            context_lines.append(f"Ticker: {context['ticker']}")

        if "holding_days" in context:
            context_lines.append(f"Holding Period: {context['holding_days']} days")

        if "analysis_count" in context:
            context_lines.append(
                f"Analysis Count: {context['analysis_count']} (number of times analyzed)"
            )

        if "market_condition" in context:
            context_lines.append(f"Market Condition: {context['market_condition']}")

        if "has_memory" in context:
            memory_status = "Had prior memories" if context["has_memory"] else "No prior memories (bootstrap)"
            context_lines.append(f"Memory Status: {memory_status}")

        structured_context = "\n".join(context_lines)

        messages = [
            ("system", self.reflection_system_prompt),
            (
                "human",
                f"Structured Context:\n{structured_context}\n\nAnalysis/Decision: {report}\n\nObjective Market Reports for Reference: {situation}",
            ),
        ]

        result = self.quick_thinking_llm.invoke(messages).content
        return result

    def reflect_bull_researcher(self, current_state, context, bull_memory):
        """Reflect on bull researcher's analysis and update memory.

        Args:
            current_state: Current agent state
            context: Structured context dict (from FR-018)
            bull_memory: Memory instance to update
        """
        situation = self._extract_current_situation(current_state)
        bull_debate_history = current_state["investment_debate_state"]["bull_history"]

        result = self._reflect_on_component(
            "BULL", bull_debate_history, situation, context
        )

        # Extract metadata for JSONL storage (FR-018)
        metadata = {
            "ticker": context.get("ticker"),
            "return_pct": context.get("return_pct"),
            "has_memory": context.get("has_memory", False),
            "schema_version": context.get("schema_version", 1),
            "holding_days": context.get("holding_days"),
            "analysis_count": context.get("analysis_count"),
        }

        bull_memory.add_situations([(situation, result)], metadata=metadata)

    def reflect_bear_researcher(self, current_state, context, bear_memory):
        """Reflect on bear researcher's analysis and update memory.

        Args:
            current_state: Current agent state
            context: Structured context dict (from FR-018)
            bear_memory: Memory instance to update
        """
        situation = self._extract_current_situation(current_state)
        bear_debate_history = current_state["investment_debate_state"]["bear_history"]

        result = self._reflect_on_component(
            "BEAR", bear_debate_history, situation, context
        )

        # Extract metadata for JSONL storage (FR-018)
        metadata = {
            "ticker": context.get("ticker"),
            "return_pct": context.get("return_pct"),
            "has_memory": context.get("has_memory", False),
            "schema_version": context.get("schema_version", 1),
            "holding_days": context.get("holding_days"),
            "analysis_count": context.get("analysis_count"),
        }

        bear_memory.add_situations([(situation, result)], metadata=metadata)

    def reflect_trader(self, current_state, context, trader_memory):
        """Reflect on trader's decision and update memory.

        Args:
            current_state: Current agent state
            context: Structured context dict (from FR-018)
            trader_memory: Memory instance to update
        """
        situation = self._extract_current_situation(current_state)
        trader_decision = current_state["trader_investment_plan"]

        result = self._reflect_on_component(
            "TRADER", trader_decision, situation, context
        )

        # Extract metadata for JSONL storage (FR-018)
        metadata = {
            "ticker": context.get("ticker"),
            "return_pct": context.get("return_pct"),
            "has_memory": context.get("has_memory", False),
            "schema_version": context.get("schema_version", 1),
            "holding_days": context.get("holding_days"),
            "analysis_count": context.get("analysis_count"),
        }

        trader_memory.add_situations([(situation, result)], metadata=metadata)

    def reflect_invest_judge(self, current_state, context, invest_judge_memory):
        """Reflect on investment judge's decision and update memory.

        Args:
            current_state: Current agent state
            context: Structured context dict (from FR-018)
            invest_judge_memory: Memory instance to update
        """
        situation = self._extract_current_situation(current_state)
        judge_decision = current_state["investment_debate_state"]["judge_decision"]

        result = self._reflect_on_component(
            "INVEST JUDGE", judge_decision, situation, context
        )

        # Extract metadata for JSONL storage (FR-018)
        metadata = {
            "ticker": context.get("ticker"),
            "return_pct": context.get("return_pct"),
            "has_memory": context.get("has_memory", False),
            "schema_version": context.get("schema_version", 1),
            "holding_days": context.get("holding_days"),
            "analysis_count": context.get("analysis_count"),
        }

        invest_judge_memory.add_situations([(situation, result)], metadata=metadata)

    def reflect_risk_manager(self, current_state, context, risk_manager_memory):
        """Reflect on risk manager's decision and update memory.

        Args:
            current_state: Current agent state
            context: Structured context dict (from FR-018)
            risk_manager_memory: Memory instance to update
        """
        situation = self._extract_current_situation(current_state)
        judge_decision = current_state["risk_debate_state"]["judge_decision"]

        result = self._reflect_on_component(
            "RISK JUDGE", judge_decision, situation, context
        )

        # Extract metadata for JSONL storage (FR-018)
        metadata = {
            "ticker": context.get("ticker"),
            "return_pct": context.get("return_pct"),
            "has_memory": context.get("has_memory", False),
            "schema_version": context.get("schema_version", 1),
            "holding_days": context.get("holding_days"),
            "analysis_count": context.get("analysis_count"),
        }

        risk_manager_memory.add_situations([(situation, result)], metadata=metadata)
