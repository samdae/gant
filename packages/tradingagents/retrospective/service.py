"""Retrospective analysis service.

Collects position data, builds LLM prompt, invokes analysis, and stores results.
Called from the queue worker when item type is 'retrospective'.
"""

import logging
from typing import Dict, Any

from tradingagents.storage import (
    RetrospectiveRepository,
    PositionRepository,
    ReportRepository,
    TradeRepository,
)
from tradingagents.storage.database import Database
from tradingagents.retrospective.prompt import build_retrospective_prompt
from tradingagents.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


def run_retrospective_analysis(
    db: Database,
    item: Dict[str, Any],
    config: Dict[str, Any],
) -> None:
    """Execute a single retrospective analysis for one position.

    Args:
        db: Database instance
        item: Queue item with keys: position_id, retro_id, ticker, type
        config: Application config (for LLM settings)
    """
    retro_id = item["retro_id"]
    position_id = item["position_id"]
    ticker = item["ticker"]

    retro_repo = RetrospectiveRepository(db)
    position_repo = PositionRepository(db)
    report_repo = ReportRepository(db)
    trade_repo = TradeRepository(db)

    retro_repo.update_status(retro_id, "running")

    try:
        position = position_repo.get_by_id(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        reports = report_repo.get_by_position(position_id)
        trades = trade_repo.get_by_position(position_id)

        is_open = position["status"] == "active"

        current_price = None
        unrealized_pnl_pct = None
        if is_open and position.get("shares", 0) > 0 and position.get("avg_cost"):
            current_price = _fetch_current_price(ticker)
            if current_price and position["avg_cost"] > 0:
                unrealized_pnl_pct = (
                    (current_price - position["avg_cost"]) / position["avg_cost"]
                ) * 100

        prompt = build_retrospective_prompt(
            position=position,
            reports=reports,
            trades=trades,
            is_open=is_open,
            current_price=current_price,
            unrealized_pnl_pct=unrealized_pnl_pct,
        )

        llm = _get_llm(config)
        response = llm.invoke(prompt, config={"timeout": 600})
        analysis_content = response.content

        retro_repo.update_status(
            retro_id, "completed", analysis_content=analysis_content
        )
        logger.info(f"Retrospective analysis completed for {ticker} (retro_id={retro_id})")

    except Exception as e:
        logger.error(f"Retrospective analysis failed for {ticker}: {e}", exc_info=True)
        retro_repo.update_status(
            retro_id, "failed", error_message=str(e)[:1000]
        )


def _fetch_current_price(ticker: str) -> float | None:
    """Fetch latest close price via yfinance."""
    try:
        import yfinance as yf
        data = yf.download(ticker, period="5d", progress=False)
        if data is not None and not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"Failed to fetch current price for {ticker}: {e}")
    return None


def _get_llm(config: Dict[str, Any]):
    """Get LLM instance using existing factory pattern."""
    client = create_llm_client(
        provider=config.get("llm_provider", "gemini-cli"),
        model=config.get("deep_think_llm", "gemini-2.5-pro"),
        base_url=config.get("backend_url"),
    )
    return client.get_llm()
