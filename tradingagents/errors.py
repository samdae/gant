"""Shared exception types for TradingAgents."""

from typing import Any, Optional


class TradingAgentsError(Exception):
    """Base exception type."""


class DataVendorError(TradingAgentsError):
    """Raised when all data vendors fail after retries."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.details = details


class DecisionParseError(TradingAgentsError):
    """Raised when parsing a decision fails."""

    def __init__(self, message: str, raw_text: Optional[str] = None):
        super().__init__(message)
        self.raw_text = raw_text


class AgentExecutionError(TradingAgentsError):
    """Raised when an agent execution fails."""
