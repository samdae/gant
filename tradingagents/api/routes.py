"""REST API routes for TradingAgents.

FR-025: REST endpoints (DB-based)
FR-026: Public READ + Authenticated WRITE
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
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
    interval_days: int = 1


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


class MarketPositionResponse(BaseModel):
    position_id: int
    ticker: str
    shares: int
    avg_cost: Optional[float]
    current_price: Optional[float]
    pnl: float
    return_pct: float
    as_of: str


class MetricsResponse(BaseModel):
    as_of: str
    active_positions: int
    closed_positions: int
    wins: int
    losses: int
    total_unrealized_pnl: float
    total_unrealized_return_pct: float


class ActivityEvent(BaseModel):
    event_type: str
    ticker: str
    created_at: datetime
    schedule_id: Optional[int] = None
    scheduled_cycle: Optional[int] = None
    action: Optional[str] = None
    decision: Optional[str] = None
    shares: Optional[int] = None
    price: Optional[float] = None
    report_id: Optional[int] = None
    trade_id: Optional[int] = None


class ScheduleSummary(BaseModel):
    total: int
    done: int
    failed: int
    skipped: int
    running: int
    pending: int
    as_of: datetime


def _fetch_latest_prices(tickers: List[str]) -> Dict[str, Optional[float]]:
    prices: Dict[str, Optional[float]] = {}
    for ticker in tickers:
        prices[ticker] = None
    if not tickers:
        return prices

    try:
        import yfinance as yf

        data: Any = yf.download(
            tickers=list(set(tickers)),
            period="1d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.warning(f"Price fetch failed: {e}")
        return prices

    if data is None or data.empty:
        return prices

    if len(tickers) == 1:
        try:
            close_series = data["Close"]
            values = list(close_series)
            if values:
                prices[tickers[0]] = float(values[-1])
        except Exception:
            pass
        return prices

    for ticker in tickers:
        try:
            close_series = data[ticker]["Close"]
            values = list(close_series)
            if values:
                prices[ticker] = float(values[-1])
        except Exception:
            continue

    return prices


def _extract_decision(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    upper = text.upper()
    for key in ["BUY", "SELL", "HOLD"]:
        if key in upper:
            return key
    return None


# Schedules endpoints
@router.get("/schedules", response_model=List[ScheduleResponse], tags=["Schedules"])
async def get_schedules(
    cursor: Optional[int] = Query(None, ge=0, description="Offset cursor"),
    limit: int = Query(10, ge=1, le=100),
):
    """Get all active schedules (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import ScheduleConfigRepository
    schedule_config_repo = ScheduleConfigRepository(scheduler.db)

    configs = schedule_config_repo.get_all()
    start = cursor or 0
    end = start + limit

    jobs = {job.id: job for job in scheduler.scheduler.get_jobs()} if scheduler else {}
    results = []
    for cfg in configs[start:end]:
        ticker = cfg["ticker"]
        job = jobs.get(f"ticker_{ticker}")
        next_run_time = None
        if job:
            next_run_time = getattr(job, "next_run_time", None) or getattr(
                job, "next_fire_time", None
            )
            if isinstance(next_run_time, datetime):
                next_run_time = next_run_time.isoformat()

        results.append(
            {
                "ticker": ticker,
                "interval_days": cfg["interval_days"],
                "next_run_time": next_run_time,
            }
        )

    return results


@router.post("/schedules", response_model=dict, tags=["Schedules"])
async def create_schedule(req: ScheduleRequest, _: bool = Depends(check_admin_token)):
    """Create a new schedule (AUTHENTICATED).

    Returns:
        Success message with ticker
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    # Check for duplicate
    from tradingagents.storage import ScheduleConfigRepository
    schedule_config_repo = ScheduleConfigRepository(scheduler.db)

    existing = schedule_config_repo.get_by_ticker(req.ticker)
    if existing:
        raise HTTPException(status_code=409, detail=f"Schedule already exists for {req.ticker}")

    # Persist schedule config and add ticker
    schedule_config_repo.create(req.ticker, req.interval_days)
    scheduler.add_ticker(req.ticker, req.interval_days)
    scheduler.enqueue_schedule(req.ticker)

    return {"message": f"Schedule created for {req.ticker}"}


@router.delete("/schedules/{ticker}", response_model=dict, tags=["Schedules"])
async def delete_schedule(ticker: str, _: bool = Depends(check_admin_token)):
    """Delete a schedule (AUTHENTICATED).

    Also removes ticker from queue if present.
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    # Check existence
    from tradingagents.storage import ScheduleConfigRepository
    schedule_config_repo = ScheduleConfigRepository(scheduler.db)

    existing = schedule_config_repo.get_by_ticker(ticker)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Schedule not found for {ticker}")

    # Remove from scheduler
    scheduler.remove_ticker(ticker)
    schedule_config_repo.delete(ticker)

    # FR-025: Remove from queue if present
    from tradingagents.scheduler.ticker_scheduler import analysis_queue

    if analysis_queue and not analysis_queue.empty():
        # Drain and re-enqueue without the deleted ticker
        remaining = []
        while not analysis_queue.empty():
            try:
                item = analysis_queue.get_nowait()
                if isinstance(item, dict):
                    item_ticker = item.get("ticker")
                else:
                    item_ticker = item

                if item_ticker != ticker:
                    remaining.append(item)
                analysis_queue.task_done()
            except Exception:
                break
        for item in remaining:
            analysis_queue.put_nowait(item)
        logger.info(f"Cleaned queue after deleting {ticker} schedule")

    return {"message": f"Schedule deleted for {ticker}"}


# FR-025: Positions endpoints (DB-based)
@router.get("/positions", response_model=List[dict], tags=["Positions"])
async def get_positions(
    status: Optional[str] = Query(None, description="Filter by status: active|closed"),
    cursor: Optional[int] = Query(None, ge=1, description="Last position id"),
    limit: int = Query(10, ge=1, le=100),
):
    """Get all positions with optional status filter (PUBLIC).
    
    Query params:
        status: "active" or "closed" (optional)
    
    Returns:
        List of positions with basic info
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    from tradingagents.storage import PositionRepository
    position_repo = PositionRepository(scheduler.db)
    
    # Build query with cursor pagination
    query = "SELECT * FROM positions"
    params: List[Any] = []
    where_clauses: List[str] = []

    if status:
        if status not in ["active", "closed"]:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        where_clauses.append("status = %s")
        params.append(status)

    if cursor:
        where_clauses.append("id < %s")
        params.append(cursor)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY id DESC LIMIT %s"
    params.append(limit)

    cursor_obj = scheduler.db.get_connection().execute(query, tuple(params))
    positions = [dict(row) for row in cursor_obj.fetchall()]

    return positions


@router.get("/positions/market", response_model=List[MarketPositionResponse], tags=["Positions"])
async def get_positions_market():
    """Get active positions with current price and PnL (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    cursor_obj = scheduler.db.get_connection().execute(
        """
        SELECT id, ticker, shares, avg_cost
        FROM positions
        WHERE status = 'active'
        ORDER BY id DESC
        """
    )
    rows = [dict(row) for row in cursor_obj.fetchall()]

    tickers = [row["ticker"] for row in rows]
    prices = _fetch_latest_prices(tickers)
    as_of = datetime.now().isoformat()

    results: List[MarketPositionResponse] = []
    for row in rows:
        ticker = row["ticker"]
        shares = int(row.get("shares", 0) or 0)
        avg_cost = row.get("avg_cost")
        current_price = prices.get(ticker)

        pnl = 0.0
        return_pct = 0.0
        if shares > 0 and avg_cost is not None and current_price is not None:
            pnl = (current_price - avg_cost) * shares
            if avg_cost > 0:
                return_pct = ((current_price - avg_cost) / avg_cost) * 100

        results.append(MarketPositionResponse(
            position_id=row["id"],
            ticker=ticker,
            shares=shares,
            avg_cost=avg_cost,
            current_price=current_price,
            pnl=pnl,
            return_pct=return_pct,
            as_of=as_of,
        ))

    return results


@router.get("/metrics", response_model=MetricsResponse, tags=["System"])
async def get_metrics():
    """Get dashboard metrics with current price PnL (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    as_of = datetime.now().isoformat()

    conn = scheduler.db.get_connection()
    active_positions = conn.execute(
        "SELECT COUNT(*) AS count FROM positions WHERE status = 'active'"
    ).fetchone()["count"]
    closed_positions = conn.execute(
        "SELECT COUNT(*) AS count FROM positions WHERE status = 'closed'"
    ).fetchone()["count"]
    wins = conn.execute(
        "SELECT COUNT(*) AS count FROM positions WHERE status = 'closed' AND return_pct > 0"
    ).fetchone()["count"]
    losses = conn.execute(
        "SELECT COUNT(*) AS count FROM positions WHERE status = 'closed' AND return_pct <= 0"
    ).fetchone()["count"]

    cursor_obj = scheduler.db.get_connection().execute(
        "SELECT ticker, shares, avg_cost FROM positions WHERE status = 'active'"
    )
    rows = [dict(row) for row in cursor_obj.fetchall()]

    tickers = [row["ticker"] for row in rows]
    prices = _fetch_latest_prices(tickers)

    total_unrealized_pnl = 0.0
    total_cost_basis = 0.0
    for row in rows:
        shares = int(row.get("shares", 0) or 0)
        avg_cost = row.get("avg_cost")
        current_price = prices.get(row["ticker"])

        if shares <= 0 or avg_cost is None or current_price is None:
            continue

        total_unrealized_pnl += (current_price - avg_cost) * shares
        total_cost_basis += avg_cost * shares

    total_unrealized_return_pct = 0.0
    if total_cost_basis > 0:
        total_unrealized_return_pct = (total_unrealized_pnl / total_cost_basis) * 100

    return MetricsResponse(
        as_of=as_of,
        active_positions=active_positions,
        closed_positions=closed_positions,
        wins=wins,
        losses=losses,
        total_unrealized_pnl=total_unrealized_pnl,
        total_unrealized_return_pct=total_unrealized_return_pct,
    )


@router.get("/activity", response_model=List[ActivityEvent], tags=["System"])
async def get_activity(
    limit: int = Query(20, ge=1, le=100),
    since_hours: int = Query(24, ge=1, le=168),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
):
    """Get recent activity feed (trades + analysis reports)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    since_ts = (datetime.now() - timedelta(hours=since_hours)).isoformat()

    # Trade events
    trade_query = """
        SELECT t.id AS trade_id, t.action, t.shares, t.price,
               t.executed_at AS created_at,
               p.ticker AS ticker,
               r.id AS report_id,
               r.schedule_id AS schedule_id,
               s.scheduled_cycle AS scheduled_cycle
        FROM trades t
        JOIN positions p ON t.position_id = p.id
        JOIN reports r ON t.report_id = r.id
        JOIN schedules s ON r.schedule_id = s.id
        WHERE t.executed_at >= %s
    """
    trade_params: List[Any] = [since_ts]
    if ticker:
        trade_query += " AND p.ticker = %s"
        trade_params.append(ticker)
    trade_query += " ORDER BY t.executed_at DESC LIMIT %s"
    trade_params.append(limit)

    trade_rows = scheduler.db.get_connection().execute(
        trade_query, tuple(trade_params)
    ).fetchall()

    trade_events = [
        ActivityEvent(
            event_type="trade",
            ticker=row["ticker"],
            created_at=row["created_at"],
            schedule_id=row["schedule_id"],
            scheduled_cycle=row["scheduled_cycle"],
            action=row["action"],
            shares=row["shares"],
            price=row["price"],
            report_id=row["report_id"],
            trade_id=row["trade_id"],
        )
        for row in trade_rows
    ]

    # Analysis events (reports without trades)
    report_query = """
        SELECT r.id AS report_id, r.created_at AS created_at,
               r.final_trade_decision AS final_trade_decision,
               r.schedule_id AS schedule_id,
               s.scheduled_cycle AS scheduled_cycle,
               s.ticker AS ticker
        FROM reports r
        JOIN schedules s ON r.schedule_id = s.id
        LEFT JOIN trades t ON t.report_id = r.id
        WHERE t.id IS NULL AND r.created_at >= %s
    """
    report_params: List[Any] = [since_ts]
    if ticker:
        report_query += " AND s.ticker = %s"
        report_params.append(ticker)
    report_query += " ORDER BY r.created_at DESC LIMIT %s"
    report_params.append(limit)

    report_rows = scheduler.db.get_connection().execute(
        report_query, tuple(report_params)
    ).fetchall()

    report_events = []
    for row in report_rows:
        decision = _extract_decision(row["final_trade_decision"])
        report_events.append(
            ActivityEvent(
                event_type="analysis",
                ticker=row["ticker"],
                created_at=row["created_at"],
                schedule_id=row["schedule_id"],
                scheduled_cycle=row["scheduled_cycle"],
                decision=decision,
                report_id=row["report_id"],
            )
        )

    # Merge and sort
    combined = trade_events + report_events
    combined.sort(key=lambda e: e.created_at, reverse=True)
    return combined[:limit]


@router.get("/positions/{position_id}", response_model=dict, tags=["Positions"])
async def get_position_detail(position_id: int):
    """Get position detail with trades and reports (PUBLIC).
    
    Returns:
        {
            "position": {...},
            "trades": [...],
            "reports": [...]
        }
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    from tradingagents.storage import (
        PositionRepository,
        TradeRepository,
        ReportRepository
    )
    
    position_repo = PositionRepository(scheduler.db)
    trade_repo = TradeRepository(scheduler.db)
    report_repo = ReportRepository(scheduler.db)
    
    # Get position
    position = position_repo.get_by_id(position_id)
    if not position:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
    
    # Get trades
    trades = trade_repo.get_by_position(position_id)
    
    # Get reports
    reports = report_repo.get_by_position(position_id)
    
    return {
        "position": position,
        "trades": trades,
        "reports": reports
    }


@router.get("/reports", response_model=List[dict], tags=["Reports"])
async def get_reports(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    position_id: Optional[int] = Query(None, description="Filter by position id"),
    cursor: Optional[int] = Query(None, ge=1, description="Last report id"),
    limit: int = Query(10, ge=1, le=100),
):
    """Get reports with optional ticker/position filter (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    query = """
        SELECT r.*, s.ticker AS ticker, s.scheduled_cycle AS scheduled_cycle
        FROM reports r
        JOIN schedules s ON r.schedule_id = s.id
    """
    params: List[Any] = []
    where_clauses: List[str] = []

    if ticker:
        where_clauses.append("s.ticker = %s")
        params.append(ticker)

    if position_id:
        where_clauses.append("r.position_id = %s")
        params.append(position_id)

    if cursor:
        where_clauses.append("r.id < %s")
        params.append(cursor)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY r.id DESC LIMIT %s"
    params.append(limit)

    cursor_obj = scheduler.db.get_connection().execute(query, tuple(params))
    reports = [dict(row) for row in cursor_obj.fetchall()]
    return reports




@router.get("/reports/tickers", response_model=List[dict], tags=["Reports"])
async def get_report_tickers():
    """Get ticker summaries for reports page (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    cursor_obj = scheduler.db.get_connection().execute(
        """
        SELECT s.ticker,
               COUNT(*) AS report_count,
               MAX(r.created_at) AS latest_at
        FROM reports r
        JOIN schedules s ON r.schedule_id = s.id
        GROUP BY s.ticker
        ORDER BY MAX(r.created_at) DESC
        """
    )
    summaries = [dict(row) for row in cursor_obj.fetchall()]

    # Attach latest decision snippet per ticker
    for item in summaries:
        dec_cur = scheduler.db.get_connection().execute(
            """
            SELECT r.final_trade_decision
            FROM reports r
            JOIN schedules s ON r.schedule_id = s.id
            WHERE s.ticker = %s
            ORDER BY r.id DESC LIMIT 1
            """,
            (item["ticker"],),
        )
        dec_row = dec_cur.fetchone()
        raw = (dec_row["final_trade_decision"] or "") if dec_row else ""
        item["last_decision"] = raw[:120].strip() if raw else ""

    return summaries


# FR-025: Schedules/Cycles endpoints
@router.get("/schedules/{ticker}/cycles", response_model=List[dict], tags=["Schedules"])
async def get_ticker_cycles(
    ticker: str,
    cursor: Optional[int] = Query(None, ge=1, description="Last schedule id"),
    limit: int = Query(10, ge=1, le=100),
):
    """Get analysis cycle history for a ticker (PUBLIC).
    
    Returns:
        List of schedules with their status
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    from tradingagents.storage import ScheduleRepository
    schedule_repo = ScheduleRepository(scheduler.db)
    
    # Get schedules for ticker with cursor pagination
    query = """
        SELECT id, ticker, interval_days, scheduled_cycle, created_at
        FROM schedules
        WHERE ticker = %s
    """
    params: List[Any] = [ticker]

    if cursor:
        query += " AND id < %s"
        params.append(cursor)

    query += " ORDER BY id DESC LIMIT %s"
    params.append(limit)

    cursor_obj = scheduler.db.get_connection().execute(query, tuple(params))
    cycles = [dict(row) for row in cursor_obj.fetchall()]
    
    if not cycles:
        return []
    
    return cycles


@router.get(
    "/schedules/{ticker}/cycles/{schedule_id}/events",
    response_model=List[dict],
    tags=["Schedules"],
)
async def get_cycle_events(
    ticker: str,
    schedule_id: int,
    limit: int = Query(200, ge=1, le=500),
):
    """Get schedule events for a specific cycle (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import ScheduleEventRepository

    repo = ScheduleEventRepository(scheduler.db)
    return repo.list_by_schedule_id(schedule_id, limit=limit, ticker=ticker)


# FR-025: Reflections endpoint
@router.get("/reflections", response_model=List[dict], tags=["Reflections"])
async def get_reflections(
    limit: int = Query(10, ge=1, le=100),
    outcome: Optional[str] = Query(None, description="Filter by outcome: win|loss"),
    cursor: Optional[int] = Query(None, ge=1, description="Last reflection id"),
):
    """Get reflections with optional outcome filter (PUBLIC).
    
    Query params:
        limit: Max results (default 10, max 100)
        outcome: "win" or "loss" (optional)
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    # Build query
    query = "SELECT * FROM reflections"
    params: List[Any] = []
    where_clauses: List[str] = []
    
    if outcome:
        if outcome not in ["win", "loss"]:
            raise HTTPException(status_code=400, detail="Invalid outcome filter")
        where_clauses.append("outcome = %s")
        params.append(outcome)

    if cursor:
        where_clauses.append("id < %s")
        params.append(cursor)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    
    query += " ORDER BY id DESC LIMIT %s"
    params.append(limit)
    
    cursor_obj = scheduler.db.get_connection().execute(query, tuple(params))
    reflections = [dict(row) for row in cursor_obj.fetchall()]
    
    return reflections


# FR-025: Hybrid RAG search endpoint
@router.get("/search", response_model=List[dict], tags=["Search"])
async def search_memories(
    query: str = Query(..., description="Search query"),
    limit: int = Query(5, ge=1, le=20)
):
    """Hybrid RAG search (ChromaDB + FTS) (PUBLIC).
    
    Query params:
        query: Search text
        limit: Max results (default 5, max 20)
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    graph = app_module.graph
    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")
    
    # Use HybridMemory for search
    try:
        results = graph.memory.get_memories(query, n_matches=limit)
        return results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/live/{ticker}/events", response_model=List[dict], tags=["Live"])
async def get_live_events(
    ticker: str,
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent live events for a ticker (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import ScheduleEventRepository

    repo = ScheduleEventRepository(scheduler.db)
    return repo.list_latest_by_ticker(ticker, limit=limit)


# FR-025: Retry failed schedule
@router.post("/schedules/{ticker}/retry", response_model=dict, tags=["Schedules"])
async def retry_failed_schedule(ticker: str, _: bool = Depends(check_admin_token)):
    """Retry a failed schedule by re-enqueuing (AUTHENTICATED)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    
    from tradingagents.storage import ScheduleRepository, ScheduleJobRepository
    schedule_repo = ScheduleRepository(scheduler.db)
    schedule_job_repo = ScheduleJobRepository(scheduler.db)
    
    schedules = schedule_repo.get_by_ticker(ticker)
    if not schedules:
        raise HTTPException(status_code=404, detail=f"No schedule found for {ticker}")

    latest_schedule = schedules[0]
    latest_job = schedule_job_repo.get_latest_by_schedule(latest_schedule["id"])
    if not latest_job:
        raise HTTPException(status_code=404, detail=f"No schedule job found for {ticker}")

    latest_status = latest_job.get("status")

    if latest_status in ["pending", "running"]:
        raise HTTPException(
            status_code=409,
            detail=f"Latest schedule for {ticker} is already pending or running"
        )

    if latest_status != "failed":
        raise HTTPException(
            status_code=404,
            detail=f"No failed schedule found for {ticker}"
        )
    
    # Re-enqueue
    from tradingagents.scheduler.ticker_scheduler import analysis_queue
    
    try:
        if not analysis_queue:
            raise HTTPException(status_code=503, detail="Analysis queue not initialized")

        scheduler.enqueue_schedule(
            ticker,
            schedule_id=latest_schedule["id"],
            error_type="requeue",
            error_message="Re-enqueued by retry",
        )
        logger.info(f"Re-enqueued failed schedule: {ticker}")
        return {"message": f"Re-enqueued {ticker} for retry"}
    except asyncio.QueueFull:
        raise HTTPException(status_code=503, detail="Analysis queue is full")


# Queue status endpoint
@router.get("/queue", response_model=QueueStatusResponse, tags=["System"])
async def get_queue_status():
    """Get current analysis queue status (PUBLIC)."""
    from tradingagents.scheduler.ticker_scheduler import analysis_queue

    running = app_module.current_running_ticker
    pending = []

    if analysis_queue and not analysis_queue.empty():
        # Peek without removing (approximation)
        queue_any: Any = analysis_queue
        raw_pending = list(getattr(queue_any, "_queue", []))
        for item in raw_pending:
            if isinstance(item, dict):
                ticker = item.get("ticker")
            else:
                ticker = item
            if ticker:
                pending.append(ticker)

    return QueueStatusResponse(
        running=running,
        pending=pending,
        total=len(pending) + (1 if running else 0)
    )


@router.get("/schedules/summary", response_model=ScheduleSummary, tags=["Schedules"])
async def get_schedule_summary():
    """Get today's schedule summary counts (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    conn = scheduler.db.get_connection()
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM schedule_jobs
        WHERE created_at >= %s
        GROUP BY status
        """,
        (start_of_day,),
    ).fetchall()

    counts = {"done": 0, "failed": 0, "skipped": 0, "running": 0, "pending": 0}
    for row in rows:
        status = (row["status"] or "").lower()
        if status in counts:
            counts[status] = int(row["count"]) if row["count"] is not None else 0

    total = sum(counts.values())
    return ScheduleSummary(total=total, as_of=now, **counts)


# Health check endpoint
@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint (PUBLIC)."""
    import time
    from tradingagents.scheduler.ticker_scheduler import analysis_queue

    scheduler = app_module.scheduler
    
    scheduler_running = scheduler is not None and scheduler.is_running()
    queue_length = analysis_queue.qsize() if analysis_queue else 0
    schedules_count = 0
    if scheduler:
        from tradingagents.storage import ScheduleConfigRepository
        schedules_count = len(ScheduleConfigRepository(scheduler.db).get_all())
    uptime = time.time() - app_module._app_start_time

    return HealthResponse(
        status="ok",
        scheduler_running=scheduler_running,
        queue_length=queue_length,
        schedules_count=schedules_count,
        uptime_seconds=uptime
    )
