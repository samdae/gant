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
from tradingagents.retrospective.prompt import build_retrospective_prompt, report_memories
from tradingagents.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


def _build_prompt_with_scores(base_prompt: str) -> str:
    """Append FR-055 score output instructions to retrospective prompt."""
    return (
        f"{base_prompt}\n\n"
        "분석 당시의 전망·근거와 그 이후에 관측한 가격·날짜를 사이클별로 대조하고 근거를 인용하세요. "
        "PA의 매매 실행이나 손익만으로 파이프라인 전망을 채점하지 마세요. "
        "기간이 지나지 않았거나 당시 전망·기간·후속 관측을 대응시킬 수 없으면 그 사이클은 제외하세요. "
        "평가 가능한 사이클 번호와 제외 이유를 먼저 적고, 평가 가능한 사례가 없으면 analysis_accuracy는 null입니다.\n"
        "analysis_accuracy는 회고자의 정성 점수입니다. 90~100은 방향·타이밍·근거 일치, "
        "70~89는 방향 일치와 타이밍 또는 근거 일부 오류, 50~69는 방향 일치와 근거 부실, "
        "30~49는 방향 불일치와 일부 분석 유효, 0~29는 전반적 불일치입니다.\n"
        "rag_contribution은 당시 PA 근거에서 확인되는 경험 반영 정도입니다. 자료 부족 시 null입니다. "
        "90~100은 결정의 핵심 근거, 70~89는 확신도나 비중에 명시적 영향, "
        "50~69는 보조 근거로 언급, 30~49는 제한적 반영, 0~29는 무관하거나 잘못 적용한 경우입니다.\n"
        "마지막에 analysis_accuracy와 rag_contribution을 한 줄씩 키: 값 형식으로 작성하세요. "
        "값은 0~100 정수 또는 null입니다."
    )


def _parse_scores(text: str) -> tuple[int | None, int | None]:
    def read_score(key: str) -> int | None:
        values = re.findall(rf"^[ \t]*{key}[ \t]*[:=][ \t]*([^\r\n]*)", text, re.I | re.M)
        if len(values) != 1:
            return None
        value = values[0].strip()
        if not re.fullmatch(r"[0-9]{1,3}", value):
            return None
        score = int(value)
        return score if score <= 100 else None

    return read_score("analysis_accuracy"), read_score("rag_contribution")


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

        if position["status"] not in {"active", "closed"}:
            raise ValueError(f"Position {position_id} has no trading outcome for retrospective analysis")
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
        if not any(report_memories(report) for report in reports):
            rag_contribution = None

        def store_result(conn):
            retro_repo.update_status(
                retro_id, "completed", analysis_content=analysis_content, commit=False, conn=conn
            )
            retro_repo.update_scores(
                retro_id, analysis_accuracy=analysis_accuracy, rag_contribution=rag_contribution,
                commit=False, conn=conn,
            )

        db.execute_in_transaction(store_result)
        logger.info(f"Retrospective analysis completed for {ticker} (retro_id={retro_id})")

    except Exception as e:
        logger.error(f"Retrospective analysis failed for {ticker}: {e}", exc_info=True)
        retro_repo.update_status(
            retro_id, "failed", error_message=str(e)[:1000]
        )
        raise


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
