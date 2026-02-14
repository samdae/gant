"""Summary Agent for generating concise summaries from agent outputs.

This agent summarizes raw outputs from 12 agents + PA opinion into 13 separate
summary columns for storage in the reports table.

Each summary target: 200-400 tokens (concise but informative).
"""

import logging
from typing import Dict, Any
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class SummaryAgent:
    """Agent for generating structured summaries from analysis results."""

    # 13 summary columns (excluding sentiment_report and news_report due to recency)
    SUMMARY_COLUMNS = [
        "market_report",
        "fundamentals_report",
        "bull_history",
        "bear_history",
        "investment_debate_judge_decision",
        "aggressive_history",
        "conservative_history",
        "neutral_history",
        "trader_investment_judge_decision",
        "trader_investment_decision",
        "investment_plan",
        "final_trade_decision",
        "pa_opinion"
    ]

    def __init__(self, llm: BaseChatModel):
        """Initialize summary agent.

        Args:
            llm: Language model for summarization (should be quick_think_llm for cost efficiency)
        """
        self.llm = llm

    def summarize(self, final_state: Dict[str, Any], pa_opinion: str) -> Dict[str, str]:
        """Generate 13 individual summaries from agent outputs.

        Args:
            final_state: Final state dict from TradingAgentsGraph.propagate()
                        Contains raw outputs from all 12 agents
            pa_opinion: Portfolio Agent's opinion/decision text

        Returns:
            Dict with 13 summary column names as keys, summary texts as values
            Example: {"market_report": "...", "fundamentals_report": "...", ...}
        """
        summaries = {}

        # 1. Market Report (from market_report)
        summaries["market_report"] = self._summarize_component(
            component_name="Market Analysis",
            raw_content=final_state.get("market_report", ""),
            target_tokens=300,
            focus="technical indicators, price trends, volume analysis"
        )

        # 2. Fundamentals Report (from fundamentals_report)
        summaries["fundamentals_report"] = self._summarize_component(
            component_name="Fundamental Analysis",
            raw_content=final_state.get("fundamentals_report", ""),
            target_tokens=300,
            focus="financial metrics, valuation, earnings, balance sheet highlights"
        )

        # 3. Bull History (from investment_debate_state.bull_history)
        debate_state = final_state.get("investment_debate_state", {})
        summaries["bull_history"] = self._summarize_component(
            component_name="Bull Arguments",
            raw_content=debate_state.get("bull_history", ""),
            target_tokens=250,
            focus="key bullish arguments, supporting evidence, conviction level"
        )

        # 4. Bear History (from investment_debate_state.bear_history)
        summaries["bear_history"] = self._summarize_component(
            component_name="Bear Arguments",
            raw_content=debate_state.get("bear_history", ""),
            target_tokens=250,
            focus="key bearish arguments, risk factors, concerns"
        )

        # 5. Investment Debate Judge Decision (from investment_debate_state.judge_decision)
        summaries["investment_debate_judge_decision"] = self._summarize_component(
            component_name="Investment Judge Decision",
            raw_content=debate_state.get("judge_decision", ""),
            target_tokens=200,
            focus="final verdict, reasoning, confidence level"
        )

        # 6. Aggressive History (from risk_debate_state.aggressive_history)
        risk_state = final_state.get("risk_debate_state", {})
        summaries["aggressive_history"] = self._summarize_component(
            component_name="Aggressive Risk View",
            raw_content=risk_state.get("aggressive_history", ""),
            target_tokens=200,
            focus="aggressive perspective, high-conviction plays, upside targets"
        )

        # 7. Conservative History (from risk_debate_state.conservative_history)
        summaries["conservative_history"] = self._summarize_component(
            component_name="Conservative Risk View",
            raw_content=risk_state.get("conservative_history", ""),
            target_tokens=200,
            focus="conservative perspective, downside protection, risk management"
        )

        # 8. Neutral History (from risk_debate_state.neutral_history)
        summaries["neutral_history"] = self._summarize_component(
            component_name="Neutral Risk View",
            raw_content=risk_state.get("neutral_history", ""),
            target_tokens=200,
            focus="balanced perspective, hedging strategies, middle ground"
        )

        # 9. Trader Investment Judge Decision (from risk_debate_state.judge_decision)
        summaries["trader_investment_judge_decision"] = self._summarize_component(
            component_name="Risk Judge Decision",
            raw_content=risk_state.get("judge_decision", ""),
            target_tokens=200,
            focus="final risk assessment, chosen approach"
        )

        # 10. Trader Investment Decision (from trader_investment_plan)
        summaries["trader_investment_decision"] = self._summarize_component(
            component_name="Trader Decision",
            raw_content=final_state.get("trader_investment_plan", ""),
            target_tokens=250,
            focus="trading decision, rationale, conviction"
        )

        # 11. Investment Plan (from investment_plan)
        summaries["investment_plan"] = self._summarize_component(
            component_name="Investment Plan",
            raw_content=final_state.get("investment_plan", ""),
            target_tokens=300,
            focus="entry strategy, exit criteria, position sizing, stop loss, targets"
        )

        # 12. Final Trade Decision (from final_trade_decision)
        summaries["final_trade_decision"] = self._summarize_component(
            component_name="Final Trade Decision",
            raw_content=final_state.get("final_trade_decision", ""),
            target_tokens=250,
            focus="BUY/SELL/HOLD decision, key reasoning, execution plan"
        )

        # 13. PA Opinion (already concise, minimal processing)
        summaries["pa_opinion"] = pa_opinion[:1000] if pa_opinion else ""

        logger.info("Generated 13 summaries from agent outputs")
        return summaries

    def _summarize_component(
        self,
        component_name: str,
        raw_content: str,
        target_tokens: int,
        focus: str
    ) -> str:
        """Summarize a single component's output.

        Args:
            component_name: Name of the component (for context)
            raw_content: Raw output text from the component
            target_tokens: Target token count for summary (200-400)
            focus: What to focus on in the summary

        Returns:
            Concise summary text
        """
        # Handle empty content
        if not raw_content or len(raw_content.strip()) == 0:
            return f"(No {component_name} data)"

        # If already short, return as-is
        if len(raw_content) < target_tokens * 2:  # Rough token estimation
            return raw_content

        # Build summarization prompt
        prompt = f"""Summarize the following {component_name} analysis into approximately {target_tokens} tokens.

Focus on: {focus}

Original Analysis:
{raw_content[:3000]}

Provide a concise summary that captures the key points and actionable insights.
Target length: {target_tokens} tokens (approximately {target_tokens // 4} words).
"""

        try:
            # Invoke LLM for summarization
            response = self.llm.invoke(prompt)
            summary = response.content.strip()

            # Truncate if too long (safety measure)
            max_chars = target_tokens * 5  # Rough upper bound
            if len(summary) > max_chars:
                summary = summary[:max_chars] + "..."

            return summary

        except Exception as e:
            logger.error(f"Failed to summarize {component_name}: {e}")
            # Fallback: Return truncated raw content
            return raw_content[:target_tokens * 4] + "..."


if __name__ == "__main__":
    # Test summary agent
    print("Testing SummaryAgent...")

    # Mock LLM for testing (returns truncated input)
    class MockLLM:
        class Response:
            def __init__(self, content):
                self.content = content

        def invoke(self, prompt):
            # Extract original analysis from prompt
            lines = prompt.split('\n')
            for i, line in enumerate(lines):
                if line.startswith("Original Analysis:"):
                    content = '\n'.join(lines[i+1:])
                    # Return first 200 chars as mock summary
                    return self.Response(content[:200] + "...")
            return self.Response("Mock summary")

    mock_llm = MockLLM()
    agent = SummaryAgent(mock_llm)

    # Mock final_state
    final_state = {
        "market_report": "Market analysis shows strong uptrend with RSI at 65. " * 20,
        "fundamentals_report": "Company shows solid revenue growth of 25% YoY. " * 20,
        "investment_debate_state": {
            "bull_history": "Bulls argue for continued momentum based on sector strength. " * 15,
            "bear_history": "Bears warn of overvaluation and potential correction. " * 15,
            "judge_decision": "Judge favors bullish case with 70% confidence."
        },
        "risk_debate_state": {
            "aggressive_history": "Aggressive approach suggests full position entry. " * 10,
            "conservative_history": "Conservative approach recommends 25% position sizing. " * 10,
            "neutral_history": "Neutral approach suggests 50% entry with trailing stop. " * 10,
            "judge_decision": "Risk judge recommends moderate aggression with 60% position."
        },
        "trader_investment_plan": "Trader recommends BUY with entry at $250. " * 15,
        "investment_plan": "Enter 50% at current price, add 25% on pullback. " * 15,
        "final_trade_decision": "Final decision: BUY 10 shares at market open."
    }

    pa_opinion = "PA agrees with BUY decision based on strong technicals and fundamentals."

    # Generate summaries
    summaries = agent.summarize(final_state, pa_opinion)

    print(f"\nGenerated {len(summaries)} summaries:")
    for col in SummaryAgent.SUMMARY_COLUMNS:
        summary = summaries.get(col, "")
        print(f"\n{col}: {len(summary)} chars")
        print(f"  {summary[:100]}...")

    print("\n✅ SummaryAgent test completed!")
