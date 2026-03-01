"""Retrospective analysis service.

Collects position data, builds LLM prompt, invokes analysis, and stores results.
Called from the queue worker when item type is 'retrospective'.
"""

import logging
import re
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


def _build_prompt_with_scores(base_prompt: str) -> str:
    """Append FR-055 score output instructions to retrospective prompt."""
    return (
        f"{base_prompt}\n\n"
        "반드시 아래 점수 항목을 함께 포함하세요.\n"
        "- analysis_accuracy: 0~100 정수\n"
        "- rag_contribution: 0~100 정수 또는 null (RAG 미사용 시)\n\n"
        "출력 형식 예시:\n"
        "analysis_accuracy: 72\n"
        "rag_contribution: 58\n"
    )


def _clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))


def _parse_scores(text: str) -> tuple[int | None, int | None]:
    """Parse FR-055 scoring fields from analysis content."""
    accuracy: int | None = None
    contribution: int | None = None

    m = re.search(r"analysis_accuracy\s*[:=]\s*(\d+)", text, flags=re.IGNORECASE)
    if m:
        accuracy = _clamp_score(int(m.group(1)))

    m = re.search(
        r"rag_contribution\s*[:=]\s*(\d+|null)",
        text,
        flags=re.IGNORECASE,
    )
    if m and m.group(1).lower() != "null":
        contribution = _clamp_score(int(m.group(1)))

    return accuracy, contribution


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
        prompt = _build_prompt_with_scores(prompt)

        llm = _get_llm(config)
        response = llm.invoke(prompt, config={"timeout": 600})
        analysis_content = (
            response.content
            if hasattr(response, "content")
            else str(response)
        )
        analysis_content = str(analysis_content)

        analysis_accuracy, rag_contribution = _parse_scores(analysis_content)

        retro_repo.update_status(
            retro_id, "completed", analysis_content=analysis_content
        )
        retro_repo.update_scores(
            retro_id,
            analysis_accuracy=analysis_accuracy,
            rag_contribution=rag_contribution,
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
