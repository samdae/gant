"""Virtual trading module for TradingAgents.

This module provides classes for managing virtual trading positions,
tracking trade history, and storing analysis reports.
"""

from .trade_manager import TradeManager
from .report_store import ReportStore

__all__ = ["TradeManager", "ReportStore"]
