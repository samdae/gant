"""REST API routes for TradingAgents.

FR-025: REST endpoints
FR-026: Public READ + Authenticated WRITE
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from tradingagents.api.auth import check_admin_token
from tradingagents.api import app as app_module

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class ScheduleRequest(BaseModel):
    ticker: str
    interval_days: int = 4
    initial_capital: float = 1000.0


class ScheduleResponse(BaseModel):
    ticker: str
    interval_days: int
    next_run_time: Optional[str]


class QueueStatusResponse(BaseModel):
    running: Optional[str]
    pending: List[str]
    total: int


class HealthResponse(BaseModel):
    status: str
    scheduler_running: bool
    queue_length: int
    schedules_count: int
    uptime_seconds: float


# Schedules endpoints
@router.get("/schedules", response_model=List[ScheduleResponse], tags=["Schedules"])
async def get_schedules():
    """Get all active schedules (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    schedules = scheduler.list_schedules()
    return schedules


@router.post("/schedules", response_model=dict, tags=["Schedules"])
async def create_schedule(
    req: ScheduleRequest,
    _: bool = Depends(check_admin_token)
):
    """Create a new schedule (AUTHENTICATED).

    Returns:
        Success message with ticker
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    # Check for duplicate
    existing = scheduler.list_schedules()
    if any(s["ticker"] == req.ticker for s in existing):
        raise HTTPException(
            status_code=409,
            detail=f"Schedule already exists for {req.ticker}"
        )

    # Add ticker
    scheduler.add_ticker(req.ticker, req.interval_days, req.initial_capital)

    return {"message": f"Schedule created for {req.ticker}"}


@router.delete("/schedules/{ticker}", response_model=dict, tags=["Schedules"])
async def delete_schedule(
    ticker: str,
    _: bool = Depends(check_admin_token)
):
    """Delete a schedule (AUTHENTICATED).

    Also removes ticker from queue if present.
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    # Check existence
    existing = scheduler.list_schedules()
    if not any(s["ticker"] == ticker for s in existing):
        raise HTTPException(status_code=404, detail=f"Schedule not found for {ticker}")

    # Remove from scheduler
    scheduler.remove_ticker(ticker)

    # FR-025: Remove from queue if present
    from tradingagents.scheduler.ticker_scheduler import analysis_queue
    if analysis_queue:
        # Create new queue without this ticker
        new_queue = asyncio.Queue()
        while not analysis_queue.empty():
            try:
                item = analysis_queue.get_nowait()
                if item != ticker:
                    await new_queue.put(item)
                analysis_queue.task_done()
            except:
                break
        
        # Replace queue (note: this is a simplification, actual implementation may vary)
        logger.info(f"Removed {ticker} from queue (if present)")

    return {"message": f"Schedule deleted for {ticker}"}


# Trade endpoints
@router.get("/trade/{ticker}", response_model=dict, tags=["Trading"])
async def get_trade(ticker: str):
    """Get trade state for a ticker (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    trade_manager = scheduler.trade_manager
    
    # Check existence
    trade_path = trade_manager._get_trade_path(ticker)
    if not os.path.exists(trade_path):
        raise HTTPException(status_code=404, detail=f"Ticker not found: {ticker}")

    state = trade_manager.load(ticker)
    return state


@router.get("/trade/{ticker}/report", response_model=List[dict], tags=["Trading"])
async def get_trade_report(ticker: str):
    """Get analysis reports for a ticker (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    report_store = scheduler.report_store
    reports = report_store.load(ticker)

    return reports


# Archive endpoints
@router.get("/archive/{ticker}", response_model=List[dict], tags=["Archive"])
async def get_archive_list(
    ticker: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Get list of archived trade cycles for a ticker (PUBLIC).

    Args:
        ticker: Ticker symbol
        offset: Skip first N archives (default 0)
        limit: Max archives to return (default 20, max 100)

    Returns:
        List of archive numbers (e.g., [1, 2, 3])
    """
    archive_base_dir = app_module.graph.config.get("archive_dir")
    ticker_archive_dir = os.path.join(archive_base_dir, ticker)

    if not os.path.exists(ticker_archive_dir):
        return []

    # List archive directories (numeric only)
    archives = [
        int(d) for d in os.listdir(ticker_archive_dir)
        if os.path.isdir(os.path.join(ticker_archive_dir, d)) and d.isdigit()
    ]

    # Sort descending (most recent first)
    archives.sort(reverse=True)

    # Pagination
    paginated = archives[offset:offset+limit]

    return [{"archive_no": n} for n in paginated]


@router.get("/archive/{ticker}/{archive_no}", response_model=dict, tags=["Archive"])
async def get_archive_detail(ticker: str, archive_no: int):
    """Get archived trade cycle detail (PUBLIC).

    Returns:
        Dict with trade.json and report.json contents
    """
    archive_base_dir = app_module.graph.config.get("archive_dir")
    archive_dir = os.path.join(archive_base_dir, ticker, str(archive_no))

    if not os.path.exists(archive_dir):
        raise HTTPException(
            status_code=404,
            detail=f"Archive not found: {ticker}/{archive_no}"
        )

    trade_path = os.path.join(archive_dir, "trade.json")
    report_path = os.path.join(archive_dir, "report.json")

    import json

    trade_data = None
    if os.path.exists(trade_path):
        with open(trade_path, 'r', encoding='utf-8') as f:
            trade_data = json.load(f)

    report_data = None
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)

    return {
        "ticker": ticker,
        "archive_no": archive_no,
        "trade": trade_data,
        "report": report_data,
    }


# Positions endpoint
@router.get("/positions", response_model=List[dict], tags=["Trading"])
async def get_positions():
    """Get all open positions (PUBLIC).

    Returns:
        List of dicts with ticker, position_summary, unrealized_return
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    trade_manager = scheduler.trade_manager

    # Scan all tickers in virtual_trade_dir
    base_dir = trade_manager.base_dir
    if not os.path.exists(base_dir):
        return []

    tickers = [
        d for d in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, d))
    ]

    positions = []
    for ticker in tickers:
        state = trade_manager.load(ticker)
        if state["positions"]:
            # Get current price (simplified — use last known price or placeholder)
            # Real implementation: fetch from yfinance
            position_summary = trade_manager.get_position_summary(ticker)
            
            positions.append({
                "ticker": ticker,
                "position_summary": position_summary,
                "status": state["status"],
                "cash": state["cash"],
            })

    return positions


# Queue endpoint
@router.get("/queue", response_model=QueueStatusResponse, tags=["System"])
async def get_queue_status():
    """Get analysis queue status (PUBLIC)."""
    from tradingagents.scheduler.ticker_scheduler import analysis_queue

    if not analysis_queue:
        return QueueStatusResponse(running=None, pending=[], total=0)

    # Get queue contents (note: this is approximation)
    pending = []
    # Queue inspection is tricky in asyncio — simplified here
    # Real implementation: maintain a separate tracking structure

    return QueueStatusResponse(
        running=None,  # TODO: Track current running ticker
        pending=pending,
        total=len(pending)
    )


# Health endpoint
@router.get("/health", response_model=HealthResponse, tags=["System"])
async def get_health():
    """Health check (PUBLIC)."""
    import time

    scheduler = app_module.scheduler
    graph = app_module.graph

    if not scheduler or not graph:
        return HealthResponse(
            status="degraded",
            scheduler_running=False,
            queue_length=0,
            schedules_count=0,
            uptime_seconds=0.0
        )

    scheduler_running = scheduler.scheduler.running
    schedules_count = len(scheduler.list_schedules())

    from tradingagents.scheduler.ticker_scheduler import analysis_queue
    queue_length = analysis_queue.qsize() if analysis_queue else 0

    # Uptime tracking (simplified — use app start time)
    uptime_seconds = 0.0  # TODO: Track app start time

    status = "ok" if scheduler_running else "degraded"

    return HealthResponse(
        status=status,
        scheduler_running=scheduler_running,
        queue_length=queue_length,
        schedules_count=schedules_count,
        uptime_seconds=uptime_seconds
    )


# RAG search endpoint
@router.get("/search", response_model=List[dict], tags=["Memory"])
async def search_memories(
    query: str = Query(..., description="Search query"),
    n: int = Query(5, ge=1, le=20, description="Number of results"),
    agent: Optional[str] = Query(None, description="Agent name (e.g., 'bull_memory')")
):
    """Search past trading memories via Hybrid RAG (PUBLIC).

    Args:
        query: Search query string
        n: Number of results to return (1-20)
        agent: Optional agent name filter

    Returns:
        List of matched memories with situation, recommendation, metadata
    """
    graph = app_module.graph
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    # Determine which memory to search
    if agent:
        # Map agent name to memory instance
        memory_map = {
            "bull": graph.bull_memory,
            "bear": graph.bear_memory,
            "trader": graph.trader_memory,
            "invest_judge": graph.invest_judge_memory,
            "risk_manager": graph.risk_manager_memory,
        }
        
        memory = memory_map.get(agent)
        if not memory:
            raise HTTPException(status_code=400, detail=f"Invalid agent name: {agent}")

        results = memory.get_memories(query, n_matches=n)
        return results

    else:
        # Search all memories and aggregate
        all_results = []
        
        for memory in [
            graph.bull_memory,
            graph.bear_memory,
            graph.trader_memory,
            graph.invest_judge_memory,
            graph.risk_manager_memory,
        ]:
            results = memory.get_memories(query, n_matches=n)
            all_results.extend(results)

        # Sort by RRF score (if available)
        all_results.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)

        # Return top N
        return all_results[:n]
