# TradingAgents/graph/signal_processing.py

import re
import json
import logging
from typing import Optional, Tuple

from langchain_core.language_models import BaseChatModel

from tradingagents.errors import DecisionParseError

logger = logging.getLogger(__name__)


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: BaseChatModel):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> Tuple[str, Optional[dict]]:
        """
        Process a full trading signal to extract the core decision and strategy.

        Returns:
            Tuple of (decision, strategy_dict):
            - decision: "BUY", "SELL", or "HOLD"
            - strategy_dict: parsed strategy JSON if present, else None
        """
        # 1. Try to extract strategy_json block
        strategy = self._extract_strategy_json(full_signal)

        # 2. Extract decision from strategy JSON if available
        if strategy and strategy.get("action") in {"BUY", "SELL", "HOLD"}:
            decision = strategy["action"]
            logger.info(f"Decision extracted from strategy_json: {decision}")
            return decision, strategy

        # 3. Fallback: use LLM to extract decision
        logger.warning("strategy_json not found or invalid, falling back to LLM extraction")
        messages = [
            (
                "system",
                "You are an efficient assistant designed to analyze paragraphs or financial reports provided by a group of analysts. Your task is to extract the investment decision: SELL, BUY, or HOLD. Provide only the extracted decision (SELL, BUY, or HOLD) as your output, without adding any additional text or information.",
            ),
            ("human", full_signal),
        ]

        result = self.quick_thinking_llm.invoke(messages).content.strip().upper()
        if result not in {"BUY", "SELL", "HOLD"}:
            raise DecisionParseError(
                "Invalid final trade decision output",
                raw_text=result,
            )
        return result, strategy

    @staticmethod
    def _extract_strategy_json(text: str) -> Optional[dict]:
        """Extract strategy_json code block from text.

        Looks for:
            ```strategy_json
            {"action": "BUY", "conviction": "HIGH", "allocation_pct": 75}
            ```
        """
        pattern = r"```strategy_json\s*\n(.*?)\n\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return None

        try:
            data = json.loads(match.group(1).strip())
            # Validate required fields
            if not isinstance(data, dict):
                return None
            action = data.get("action", "").upper()
            if action not in {"BUY", "SELL", "HOLD"}:
                logger.warning(f"Invalid action in strategy_json: {action}")
                return None
            data["action"] = action
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse strategy_json: {e}")
            return None
