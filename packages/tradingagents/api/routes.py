"""REST API routes for TradingAgents.

FR-025: REST endpoints (DB-based)
FR-026: Public READ + Authenticated WRITE
"""

import os
import re
import math
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

_GRAPH_CACHE: Dict[str, Dict[str, Any]] = {}


def _graph_cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _GRAPH_CACHE.get(key)
    if not entry:
        return None
    if entry["expires_at"] <= datetime.now(timezone.utc):
        _GRAPH_CACHE.pop(key, None)
        return None
    return entry["data"]


def _graph_cache_set(key: str, data: Dict[str, Any], ttl_seconds: int) -> None:
    _GRAPH_CACHE[key] = {
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        "data": data,
    }


# Request/Response models
class ScheduleRequest(BaseModel):
    ticker: str
    interval_days: int = 1
    display_name: str = None


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
    shares: float
    avg_cost: Optional[float]
    current_price: Optional[float]
    pnl: float
    return_pct: float
    as_of: str


class ClosedPositionResponse(BaseModel):
    position_id: int
    ticker: str
    shares: float
    avg_cost: Optional[float]
    return_pct: float
    currency: str
    outcome: str
    opened_at: Optional[str]
    closed_at: Optional[str]


class MetricsResponse(BaseModel):
    as_of: str
    active_positions: int
    closed_positions: int
    wins: int
    losses: int
    total_unrealized_pnl: float
    total_unrealized_return_pct: float
    total_realized_pnl: float
    total_realized_return_pct: float
    total_pnl: float
    total_return_pct: float


class ActivityEvent(BaseModel):
    event_type: str
    ticker: str
    created_at: datetime
    schedule_job_id: Optional[int] = None
    scheduled_cycle: Optional[int] = None
    action: Optional[str] = None
    decision: Optional[str] = None
    shares: Optional[float] = None
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
    prices: Dict[str, Optional[float]] = {ticker: None for ticker in tickers}
    if not tickers:
        return prices

    def is_krx_numeric(symbol: str) -> bool:
        base = symbol.split(".")[0]
        return base.isdigit() and len(base) == 6

    def alt_symbols(symbol: str) -> List[str]:
        if not is_krx_numeric(symbol):
            return []
        base = symbol.split(".")[0]
        if symbol.endswith(".KS"):
            return [f"{base}.KQ"]
        if symbol.endswith(".KQ"):
            return [f"{base}.KS"]
        if "." not in symbol:
            return [f"{base}.KS", f"{base}.KQ"]
        return []

    def extract_close_info(data: Any, symbol: str, multi: bool) -> tuple[Optional[float], Optional[Any], bool]:
        try:
            close_series = data[symbol]["Close"] if multi else data["Close"]
        except Exception:
            return None, None, False
        try:
            values = list(close_series)
        except Exception:
            return None, None, False
        if not values:
            return None, None, False
        for value in reversed(values):
            try:
                val = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(val):
                return val, values[-1], True
        return None, values[-1], True

    def fetch_data(symbols: List[str]) -> Optional[Any]:
        if not symbols:
            return None
        try:
            import yfinance as yf

            return yf.download(
                tickers=symbols,
                period="1d",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
        except Exception as e:
            logger.warning(f"Price fetch failed: {e}")
            return None

    primary_symbols = sorted(set(tickers))
    primary_data = fetch_data(primary_symbols)
    if primary_data is None or primary_data.empty:
        return prices

    primary_multi = len(primary_symbols) > 1
    missing: List[str] = []
    diagnostics: Dict[str, List[str]] = {ticker: [] for ticker in tickers}
    for ticker in tickers:
        price, last_value, has_values = extract_close_info(primary_data, ticker, primary_multi)
        if price is not None:
            prices[ticker] = price
            continue
        missing.append(ticker)
        if has_values:
            diagnostics[ticker].append(f"{ticker} last={last_value}")
        else:
            diagnostics[ticker].append(f"{ticker} empty")

    if missing:
        alt_map: Dict[str, List[str]] = {ticker: alt_symbols(ticker) for ticker in missing}
        alt_symbols_all = sorted({symbol for symbols in alt_map.values() for symbol in symbols})
        alt_data = fetch_data(alt_symbols_all)
        if alt_data is not None and not alt_data.empty:
            alt_multi = len(alt_symbols_all) > 1
            for ticker in missing:
                for symbol in alt_map.get(ticker, []):
                    price, last_value, has_values = extract_close_info(alt_data, symbol, alt_multi)
                    if price is not None:
                        logger.warning(f"Price fallback: {ticker} -> {symbol}")
                        prices[ticker] = price
                        break
                    if has_values:
                        diagnostics[ticker].append(f"{symbol} last={last_value}")
                    else:
                        diagnostics[ticker].append(f"{symbol} empty")

    for ticker, price in prices.items():
        if price is None:
            logger.warning(f"Price missing for {ticker}; tried: {', '.join(diagnostics.get(ticker, []))}")

    return prices


def _extract_decision(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = text.replace("**", "")
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    for line in lines:
        if "결정" in line or "decision" in line.lower():
            match = re.search(r"(?:결정|decision)\s*[:：]\s*(BUY|SELL|HOLD|매수|매도|보유)", line, re.IGNORECASE)
            if match:
                token = match.group(1).upper()
                if token in {"BUY", "SELL", "HOLD"}:
                    return token
                if "매수" in match.group(1):
                    return "BUY"
                if "매도" in match.group(1):
                    return "SELL"
                if "보유" in match.group(1):
                    return "HOLD"

    scrubbed = re.sub(r"BUY/SELL/HOLD", "", cleaned, flags=re.IGNORECASE)
    if "보유" in scrubbed:
        return "HOLD"
    if "매도" in scrubbed:
        return "SELL"
    if "매수" in scrubbed:
        return "BUY"

    lower = scrubbed.lower()
    if re.search(r"(^|\b)hold(\b|$)", lower):
        return "HOLD"
    if re.search(r"(^|\b)sell(\b|$)", lower) or re.search(r"(^|\b)short(\b|$)", lower):
        return "SELL"
    if re.search(r"(^|\b)buy(\b|$)", lower) or re.search(r"(^|\b)long(\b|$)", lower):
        return "BUY"

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

    schedule_config_repo.create(req.ticker, req.interval_days, display_name=req.display_name)
    cfg = schedule_config_repo.get_by_ticker(req.ticker) or {}
    scheduler.add_ticker(req.ticker, req.interval_days, market=cfg.get("market", "us"))
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
                entry = analysis_queue.get_nowait()
                payload = entry
                if isinstance(entry, tuple) and len(entry) == 3:
                    _, _, payload = entry
                if isinstance(payload, dict):
                    item_ticker = payload.get("ticker")
                else:
                    item_ticker = payload
                if item_ticker != ticker:
                    remaining.append(entry)
                analysis_queue.task_done()
            except Exception:
                break
        for entry in remaining:
            analysis_queue.put_nowait(entry)
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
        shares = float(row.get("shares", 0) or 0.0)
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


@router.get("/positions/closed", response_model=List[ClosedPositionResponse], tags=["Positions"])
async def get_positions_closed():
    """Get closed positions with outcome and return."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    conn = scheduler.db.get_connection()
    cursor_obj = conn.execute(
        """
        SELECT id, ticker, shares, avg_cost, return_pct, currency,
               opened_at, closed_at
        FROM positions
        WHERE status = 'closed'
        ORDER BY closed_at DESC
        """
    )
    rows = [dict(row) for row in cursor_obj.fetchall()]

    results: List[ClosedPositionResponse] = []
    for row in rows:
        rp = float(row.get("return_pct") or 0)
        results.append(ClosedPositionResponse(
            position_id=row["id"],
            ticker=row["ticker"],
            shares=float(row.get("shares") or 0),
            avg_cost=row.get("avg_cost"),
            return_pct=rp,
            currency=row.get("currency") or "USD",
            outcome="win" if rp >= 0 else "loss",
            opened_at=row.get("opened_at"),
            closed_at=row.get("closed_at"),
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
        "SELECT COUNT(*) AS count FROM positions WHERE status = 'closed' AND return_pct >= 0"
    ).fetchone()["count"]
    losses = conn.execute(
        "SELECT COUNT(*) AS count FROM positions WHERE status = 'closed' AND return_pct < 0"
    ).fetchone()["count"]

    # Realized PnL from closed positions
    realized_rows = conn.execute(
        """
        SELECT p.id, p.avg_cost, p.shares AS orig_shares, p.return_pct, p.currency,
               COALESCE(SUM(CASE WHEN t.action='SELL' THEN t.shares * t.price ELSE 0 END), 0) AS sell_total,
               COALESCE(SUM(CASE WHEN t.action='BUY' THEN t.shares * t.price ELSE 0 END), 0) AS buy_total
        FROM positions p
        LEFT JOIN trades t ON t.position_id = p.id
        WHERE p.status = 'closed'
        GROUP BY p.id, p.avg_cost, p.shares, p.return_pct, p.currency
        """
    ).fetchall()

    total_realized_pnl = 0.0
    total_realized_cost = 0.0
    for r in realized_rows:
        sell_total = float(r["sell_total"] or 0)
        buy_total = float(r["buy_total"] or 0)
        pnl = sell_total - buy_total
        total_realized_pnl += pnl
        total_realized_cost += buy_total

    total_realized_return_pct = 0.0
    if total_realized_cost > 0:
        total_realized_return_pct = (total_realized_pnl / total_realized_cost) * 100

    # Unrealized PnL from active positions
    cursor_obj = scheduler.db.get_connection().execute(
        "SELECT ticker, shares, avg_cost FROM positions WHERE status = 'active'"
    )
    rows = [dict(row) for row in cursor_obj.fetchall()]

    tickers = [row["ticker"] for row in rows]
    prices = _fetch_latest_prices(tickers)

    total_unrealized_pnl = 0.0
    total_cost_basis = 0.0
    for row in rows:
        shares = float(row.get("shares", 0) or 0.0)
        avg_cost = row.get("avg_cost")
        current_price = prices.get(row["ticker"])

        if shares <= 0 or avg_cost is None or current_price is None:
            continue

        total_unrealized_pnl += (current_price - avg_cost) * shares
        total_cost_basis += avg_cost * shares

    total_unrealized_return_pct = 0.0
    if total_cost_basis > 0:
        total_unrealized_return_pct = (total_unrealized_pnl / total_cost_basis) * 100

    total_pnl = total_realized_pnl + total_unrealized_pnl
    total_invested = total_realized_cost + total_cost_basis
    total_return_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    return MetricsResponse(
        as_of=as_of,
        active_positions=active_positions,
        closed_positions=closed_positions,
        wins=wins,
        losses=losses,
        total_unrealized_pnl=total_unrealized_pnl,
        total_unrealized_return_pct=total_unrealized_return_pct,
        total_realized_pnl=total_realized_pnl,
        total_realized_return_pct=total_realized_return_pct,
        total_pnl=total_pnl,
        total_return_pct=total_return_pct,
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

    events_query = """
        SELECT r.id AS report_id,
               r.schedule_job_id AS schedule_job_id,
               sj.scheduled_cycle AS scheduled_cycle,
               sc.ticker AS ticker,
               COALESCE(t.executed_at, r.created_at) AS created_at,
               t.id AS trade_id,
               t.action AS trade_action,
               t.shares AS trade_shares,
               t.price AS trade_price,
               r.final_trade_decision AS final_trade_decision,
               r.decision_position AS decision_position,
               r.portfolio_action AS portfolio_action,
               r.portfolio_shares AS portfolio_shares
        FROM reports r
        JOIN schedule_jobs sj ON r.schedule_job_id = sj.id
        JOIN schedule_configs sc ON sj.schedule_config_id = sc.id
        LEFT JOIN trades t ON t.report_id = r.id
        WHERE r.created_at >= %s
    """
    event_params: List[Any] = [since_ts]
    if ticker:
        events_query += " AND sc.ticker = %s"
        event_params.append(ticker)
    events_query += " ORDER BY created_at DESC LIMIT %s"
    event_params.append(limit)

    rows = scheduler.db.get_connection().execute(
        events_query, tuple(event_params)
    ).fetchall()

    events: List[ActivityEvent] = []
    for row in rows:
        if row.get("trade_id"):
            events.append(
                ActivityEvent(
                    event_type="trade",
                    ticker=row["ticker"],
                    created_at=row["created_at"],
                    schedule_job_id=row["schedule_job_id"],
                    scheduled_cycle=row["scheduled_cycle"],
                    action=row["trade_action"],
                    shares=row["trade_shares"],
                    price=row["trade_price"],
                    report_id=row["report_id"],
                    trade_id=row["trade_id"],
                )
            )
        else:
            decision = (
                row.get("portfolio_action")
                or row.get("decision_position")
                or _extract_decision(row.get("final_trade_decision"))
            )
            events.append(
                ActivityEvent(
                    event_type="analysis",
                    ticker=row["ticker"],
                    created_at=row["created_at"],
                    schedule_job_id=row["schedule_job_id"],
                    scheduled_cycle=row["scheduled_cycle"],
                    decision=decision,
                    shares=row.get("portfolio_shares") if row.get("portfolio_action") else None,
                    report_id=row["report_id"],
                )
            )

    return events


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


@router.get("/position/{position_id}/graph", response_model=dict, tags=["Positions"])
async def get_position_graph(
    position_id: int,
    days: int = Query(7, ge=1, le=60),
):
    """Get OHLC daily graph data for a position ticker (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import PositionRepository

    position_repo = PositionRepository(scheduler.db)
    position = position_repo.get_by_id(position_id)
    if not position:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    ticker = position["ticker"]
    opened_at = position.get("opened_at")
    now = datetime.now(timezone.utc)

    start_dt = now - timedelta(days=days)
    if opened_at:
        try:
            parsed = datetime.fromisoformat(str(opened_at))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            start_dt = parsed - timedelta(days=days)
        except Exception:
            pass

    start_date = start_dt.date().isoformat()
    end_date = (now + timedelta(days=1)).date().isoformat()
    cache_key = f"{ticker}:{start_date}:{end_date}"

    cached = _graph_cache_get(cache_key)
    if cached:
        return cached

    try:
        import yfinance as yf

        data: Any = yf.download(
            tickers=ticker,
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
    except Exception as exc:
        logger.warning(f"Graph fetch failed for {ticker}: {exc}")
        return {"ticker": ticker, "start": start_date, "end": now.date().isoformat(), "points": []}

    if data is None or data.empty:
        return {"ticker": ticker, "start": start_date, "end": now.date().isoformat(), "points": []}

    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if hasattr(value, "iloc"):
            try:
                value = value.iloc[0]
            except Exception:
                pass
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    points: List[Dict[str, Any]] = []
    data = data.reset_index()
    for _, row in data.iterrows():
        date_value = row.get("Date")
        if hasattr(date_value, "to_pydatetime"):
            date_value = date_value.to_pydatetime()
        if isinstance(date_value, datetime):
            date_str = date_value.date().isoformat()
        else:
            date_str = str(date_value)

        points.append(
            {
                "date": date_str,
                "open": _to_float(row.get("Open")),
                "high": _to_float(row.get("High")),
                "low": _to_float(row.get("Low")),
                "close": _to_float(row.get("Close")),
                "volume": _to_float(row.get("Volume")),
            }
        )

    payload = {
        "ticker": ticker,
        "start": start_date,
        "end": now.date().isoformat(),
        "points": points,
    }

    is_today = bool(points) and now.date().isoformat() == points[-1]["date"]
    ttl_seconds = 86400 if is_today else 86400 * 7
    _graph_cache_set(cache_key, payload, ttl_seconds)
    return payload


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
        SELECT r.*, sc.ticker AS ticker, sj.scheduled_cycle AS scheduled_cycle
        FROM reports r
        JOIN schedule_jobs sj ON r.schedule_job_id = sj.id
        JOIN schedule_configs sc ON sj.schedule_config_id = sc.id
    """
    params: List[Any] = []
    where_clauses: List[str] = []

    if ticker:
        where_clauses.append("sc.ticker = %s")
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
    for item in reports:
        if not item.get("decision_position"):
            item["decision_position"] = _extract_decision(item.get("final_trade_decision"))
    return reports




@router.get("/reports/tickers", response_model=List[dict], tags=["Reports"])
async def get_report_tickers():
    """Get ticker summaries for reports page (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    cursor_obj = scheduler.db.get_connection().execute(
        """
        SELECT sc.ticker,
               COUNT(*) AS report_count,
               MAX(r.created_at) AS latest_at,
               MAX(sj.scheduled_cycle) AS latest_cycle
        FROM reports r
        JOIN schedule_jobs sj ON r.schedule_job_id = sj.id
        JOIN schedule_configs sc ON sj.schedule_config_id = sc.id
        GROUP BY sc.ticker
        ORDER BY MAX(r.created_at) DESC
        """
    )
    summaries = [dict(row) for row in cursor_obj.fetchall()]

    for item in summaries:
        dec_cur = scheduler.db.get_connection().execute(
            """
            SELECT r.final_trade_decision, r.decision_position,
                   r.portfolio_action, r.portfolio_shares,
                   t.action AS trade_action, t.shares AS trade_shares
            FROM reports r
            JOIN schedule_jobs sj ON r.schedule_job_id = sj.id
            JOIN schedule_configs sc ON sj.schedule_config_id = sc.id
            LEFT JOIN trades t ON t.report_id = r.id
            WHERE sc.ticker = %s
            ORDER BY r.id DESC LIMIT 1
            """,
            (item["ticker"],),
        )
        dec_row = dec_cur.fetchone()
        raw = (dec_row["final_trade_decision"] or "") if dec_row else ""
        item["last_decision"] = raw[:120].strip() if raw else ""
        if dec_row and dec_row.get("trade_action"):
            item["trade_action"] = dec_row["trade_action"]
            item["trade_shares"] = dec_row.get("trade_shares")
        if dec_row and dec_row.get("portfolio_action"):
            item["portfolio_action"] = dec_row["portfolio_action"]
            item["portfolio_shares"] = dec_row.get("portfolio_shares")
        if dec_row and dec_row.get("decision_position"):
            item["decision_position"] = dec_row["decision_position"]
        else:
            item["decision_position"] = _extract_decision(raw)

    return summaries






@router.get("/tickers/names", response_model=dict, tags=["Tickers"])
async def get_ticker_names():
    """Return {ticker: display_name} map for all tickers with display names."""
    from tradingagents.storage import ScheduleConfigRepository

    scheduler = app_module.scheduler
    if not scheduler or not scheduler.db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    repo = ScheduleConfigRepository(scheduler.db)
    return repo.get_all_display_names()



@router.get("/search/tickers", response_model=List[dict], tags=["Search"])
async def search_tickers(q: str = Query(..., min_length=1, max_length=20)):
    """Search Yahoo Finance for ticker symbols (PUBLIC)."""
    import urllib.request
    import urllib.parse
    import json

    url = (
        "https://query2.finance.yahoo.com/v1/finance/search?"
        + urllib.parse.urlencode({"q": q, "quotesCount": 8, "newsCount": 0})
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    results = []
    for quote in data.get("quotes", []):
        symbol = quote.get("symbol", "")
        name = quote.get("shortname") or quote.get("longname") or ""
        exchange = quote.get("exchange", "")
        qtype = quote.get("quoteType", "")
        if symbol and qtype in ("EQUITY", "ETF", "CRYPTOCURRENCY", "MUTUALFUND", "INDEX"):
            results.append({
                "symbol": symbol,
                "name": name,
                "exchange": exchange,
                "type": qtype,
            })
    return results


# FR-025: Schedules/Cycles endpoints
@router.get("/schedules/{ticker}/cycles", response_model=List[dict], tags=["Schedules"])
async def get_ticker_cycles(
    ticker: str,
    cursor: Optional[int] = Query(None, ge=1, description="Last schedule id"),
    limit: int = Query(10, ge=1, le=100),
):
    """Get analysis cycle history for a ticker (PUBLIC).

    Returns:
        List of schedule_jobs with their status
    """
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    query = """
        SELECT sj.id, sc.ticker, sj.scheduled_cycle, sj.status,
               sj.error_type, sj.error_message, sj.created_at
        FROM schedule_jobs sj
        JOIN schedule_configs sc ON sj.schedule_config_id = sc.id
        WHERE sc.ticker = %s
    """
    params: List[Any] = [ticker]

    if cursor:
        query += " AND sj.id < %s"
        params.append(cursor)

    query += " ORDER BY sj.id DESC LIMIT %s"
    params.append(limit)

    cursor_obj = scheduler.db.get_connection().execute(query, tuple(params))
    cycles = [dict(row) for row in cursor_obj.fetchall()]

    return cycles


@router.get(
    "/schedules/{ticker}/cycles/{job_id}/events",
    response_model=List[dict],
    tags=["Schedules"],
)
async def get_cycle_events(
    ticker: str,
    job_id: int,
    limit: int = Query(200, ge=1, le=500),
):
    """Get schedule events for a specific cycle (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import ScheduleEventRepository

    repo = ScheduleEventRepository(scheduler.db)
    return repo.list_by_job_id(job_id, limit=limit, ticker=ticker)


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
    
    query = """
        SELECT r.id, r.position_id, r.reflection, r.key_lessons,
               r.outcome, r.return_pct, r.market, r.sector, r.industry,
               r.created_at, p.ticker
        FROM reflections r
        LEFT JOIN positions p ON p.id = r.position_id
    """
    params: List[Any] = []
    where_clauses: List[str] = []

    if outcome:
        if outcome not in ["win", "loss"]:
            raise HTTPException(status_code=400, detail="Invalid outcome filter")
        where_clauses.append("r.outcome = %s")
        params.append(outcome)

    if cursor:
        where_clauses.append("r.id < %s")
        params.append(cursor)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY r.id DESC LIMIT %s"
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
    
    from tradingagents.storage import ScheduleJobRepository
    job_repo = ScheduleJobRepository(scheduler.db)

    latest_job = job_repo.get_latest_by_ticker(ticker)
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

    from tradingagents.scheduler.ticker_scheduler import analysis_queue

    try:
        if not analysis_queue:
            raise HTTPException(status_code=503, detail="Analysis queue not initialized")

        scheduler.enqueue_schedule(
            ticker,
            schedule_job_id=latest_job["id"],
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
        queue_any: Any = analysis_queue
        raw_pending = list(getattr(queue_any, "_queue", []))
        for entry in raw_pending:
            item = entry
            if isinstance(entry, tuple) and len(entry) == 3:
                _, _, item = entry
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


# ── Retrospective Analysis endpoints ──


class RetrospectiveAnalyzeRequest(BaseModel):
    mode: str  # "ticker" | "date" | "all"
    position_ids: Optional[List[int]] = None
    tickers: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@router.get("/retrospective/tickers", tags=["Retrospective"])
async def get_retrospective_tickers():
    """Get tickers available for retrospective analysis (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import RetrospectiveRepository
    retro_repo = RetrospectiveRepository(scheduler.db)
    return retro_repo.get_analyzable_tickers()


@router.get("/retrospective/positions/{ticker}", tags=["Retrospective"])
async def get_retrospective_positions(ticker: str):
    """Get positions for a ticker with retrospective analysis status (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import RetrospectiveRepository
    retro_repo = RetrospectiveRepository(scheduler.db)
    return retro_repo.get_positions_with_status(ticker)


@router.post("/retrospective/analyze", tags=["Retrospective"])
async def request_retrospective_analysis(
    req: RetrospectiveAnalyzeRequest,
    _: bool = Depends(check_admin_token),
):
    """Request retrospective analysis for selected positions (ADMIN)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import RetrospectiveRepository, PositionRepository
    from tradingagents.scheduler.ticker_scheduler import (
        analysis_queue, PRIORITY_RETROSPECTIVE,
    )
    import tradingagents.scheduler.ticker_scheduler as ts_module

    retro_repo = RetrospectiveRepository(scheduler.db)
    position_repo = PositionRepository(scheduler.db)

    if req.mode == "ticker":
        if not req.position_ids:
            raise HTTPException(status_code=400, detail="position_ids required for ticker mode")
        positions_to_analyze = []
        for pid in req.position_ids:
            pos = position_repo.get_by_id(pid)
            if pos:
                positions_to_analyze.append(pos)
    elif req.mode == "date":
        if not req.date_from or not req.date_to:
            raise HTTPException(status_code=400, detail="date_from and date_to required for date mode")
        positions_to_analyze_raw = retro_repo.get_analyzable_positions(
            date_from=req.date_from, date_to=req.date_to
        )
        positions_to_analyze = []
        for row in positions_to_analyze_raw:
            pos = position_repo.get_by_id(row["position_id"])
            if pos:
                positions_to_analyze.append(pos)
    elif req.mode == "all":
        positions_to_analyze_raw = retro_repo.get_analyzable_positions()
        positions_to_analyze = []
        for row in positions_to_analyze_raw:
            pos = position_repo.get_by_id(row["position_id"])
            if pos:
                positions_to_analyze.append(pos)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")

    if not positions_to_analyze:
        return {"enqueued": [], "message": "No eligible positions found"}

    enqueued_ids = []
    conn = scheduler.db.get_connection()

    ticker_sequences = {}
    for pos in positions_to_analyze:
        tk = pos["ticker"]
        if tk not in ticker_sequences:
            all_positions = conn.execute(
                """
                SELECT id, ROW_NUMBER() OVER (ORDER BY opened_at) AS seq
                FROM positions WHERE ticker = %s ORDER BY opened_at
                """,
                (tk,),
            ).fetchall()
            ticker_sequences[tk] = {row["id"]: int(row["seq"]) for row in all_positions}

    for pos in positions_to_analyze:
        position_id = pos["id"]
        ticker = pos["ticker"]
        pos_status = "closed" if pos["status"] == "closed" else "open"
        seq = ticker_sequences.get(ticker, {}).get(position_id, 1)

        existing = retro_repo.get_by_position_id(position_id)
        if existing:
            if existing["status"] in ("pending", "running"):
                continue
            if existing["status"] == "completed" and existing["position_status"] == "closed":
                continue

        retro_id = retro_repo.upsert(
            position_id=position_id,
            ticker=ticker,
            position_sequence=seq,
            position_status=pos_status,
            position_open_date=str(pos.get("opened_at", "")),
            position_close_date=str(pos.get("closed_at", "")) if pos.get("closed_at") else None,
        )

        if analysis_queue and scheduler:
            scheduler._enqueue_item(
                {
                    "type": "retrospective",
                    "ticker": ticker,
                    "position_id": position_id,
                    "retro_id": retro_id,
                },
                priority=PRIORITY_RETROSPECTIVE,
                skip_dedup=True,
            )

        enqueued_ids.append(position_id)

    return {
        "enqueued": enqueued_ids,
        "message": f"Enqueued {len(enqueued_ids)} position(s) for retrospective analysis",
    }


@router.get("/retrospective/summary", tags=["Retrospective"])
async def get_retrospective_summary():
    """Get tickers with completed retrospective analyses (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import RetrospectiveRepository
    retro_repo = RetrospectiveRepository(scheduler.db)
    return retro_repo.get_ticker_summary()


@router.get("/retrospective/detail/{ticker}", tags=["Retrospective"])
async def get_retrospective_by_ticker(ticker: str):
    """Get all retrospective analyses for a ticker (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import RetrospectiveRepository
    retro_repo = RetrospectiveRepository(scheduler.db)
    return retro_repo.list_by_ticker(ticker)


@router.get("/retrospective/{retro_id}", tags=["Retrospective"])
async def get_retrospective_result(retro_id: int):
    """Get a specific retrospective analysis result (PUBLIC)."""
    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    from tradingagents.storage import RetrospectiveRepository
    retro_repo = RetrospectiveRepository(scheduler.db)
    result = retro_repo.get_by_id(retro_id)
    if not result:
        raise HTTPException(status_code=404, detail="Retrospective analysis not found")
    return result
