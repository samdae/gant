"""Virtual trading module for TradingAgents.

This module provides classes for managing virtual trading positions,
tracking trade history, and storing analysis reports.
"""

from .trade_manager import TradeManager
from .portfolio_agent import PortfolioAgent
from .portfolio_manager_agent import PortfolioManagerAgent
from .fee_calculator import FeeCalculator, FeeResult
from .exchange_rate import ExchangeRateService

__all__ = [
    "TradeManager",
    "PortfolioAgent",
    "PortfolioManagerAgent",
    "FeeCalculator",
    "FeeResult",
    "ExchangeRateService",
]
