from tradingagents.agents.utils.macro_mixin import get_macro_block


def create_risk_manager(llm):
    def risk_manager_node(state) -> dict:

        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state["history"]
        trader_plan = state["trader_investment_plan"]
        macro_block = get_macro_block(state)
        analyst_refs = state.get("news_analyst_cited", [])
        archive_brief = ""
        if analyst_refs:
            allowed = ", ".join(f"[{ref}]" for ref in analyst_refs)
            archive_brief = (
                "\nNews analyst report for this decision:\n" + state["news_report"]
                + f"\nEligible archive references cited by the analyst: {allowed}. "
                "If your decision relies on a material archive finding, retain its exact reference "
                "beside that finding in your rationale. Do not list unused sources or invent references.\n"
            )

        prompt = f"""As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Aggressive, Neutral, and Conservative—and determine the best course of action for the trader. Your decision must result in a clear recommendation: Buy, Sell, or Hold. Choose Hold only if strongly justified by specific arguments, not as a fallback when all sides seem valid. Strive for clarity and decisiveness.

Guidelines for Decision-Making:
1. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
2. **Provide Rationale**: Support your recommendation with direct quotes and counterarguments from the debate.
3. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.
Deliverables:
- A clear and actionable recommendation: Buy, Sell, or Hold.
- Detailed reasoning anchored in the debate and past reflections.

---

**Analysts Debate History:**
{history}
{archive_brief}

---

Focus on actionable insights and continuous improvement. Build on past lessons, critically evaluate all perspectives, and ensure each decision advances better outcomes.

**IMPORTANT: You MUST end your response with the following structured strategy block.**
This block will be consumed by downstream systems, so it must be valid JSON inside a fenced code block tagged `strategy_json`.

- action: Your final recommendation — exactly one of "BUY", "SELL", or "HOLD"
- conviction: Your confidence level — exactly one of "HIGH", "MEDIUM", or "LOW"
- allocation_pct: Suggested position size as integer 0-100 (0 for HOLD, 25=low, 50=medium, 75=high conviction)

For stocks and ETFs also include forecast_5s, independently of your action and allocation.
Estimate p_up (numeric probability from 0 to 1) that the close of the fifth trading
session exceeds the opening price of the first trading session strictly after the
report publication date in the ticker's market. Count the entry session as session
one. An unchanged price is not up. Supply this estimate for HOLD and SELL as well.
Use only evidence available for this analysis; conviction in a trade is a separate judgment.

Example shape for a stock or ETF (choose your own action, allocation and probability):
```strategy_json
{{"action": "BUY", "conviction": "MEDIUM", "allocation_pct": 50, "forecast_5s": {{"p_up": 0.51}}}}
```

You MUST include this block at the very end of your response. Do not omit it.

{macro_block}"""

        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return risk_manager_node
