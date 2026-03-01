"""Portfolio mode REST endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from tradingagents.api.auth import check_admin_token, check_portfolio_read_access
from tradingagents.storage import (
    PortfolioConfigRepository,
    PortfolioDecisionRepository,
    PortfolioHoldingRepository,
    PortfolioReflectionRepository,
    PortfolioTradeRepository,
)
from tradingagents.virtual_trade.exchange_rate import ExchangeRateService

router = APIRouter(tags=["Portfolio"])


class PortfolioFeeRatesRequest(BaseModel):
    us_fee_rate: Optional[float] = None
    kr_buy_fee_rate: Optional[float] = None
    kr_sell_fee_rate: Optional[float] = None
    kr_sell_tax_rate: Optional[float] = None
    crypto_fee_rate: Optional[float] = None


class PortfolioConfigRequest(BaseModel):
    initial_capital: float = Field(..., gt=0)
    base_currency: str = Field(..., pattern="^(KRW|USD)$")
    fee_enabled: bool = True
    fee_rates: Optional[PortfolioFeeRatesRequest] = None
    reset_fund_to_initial: bool = True


def _get_scheduler():
    # Avoid circular import at module import time.
    from tradingagents.api import app as app_module

    scheduler = app_module.scheduler
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    return scheduler


def _config_to_response(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": "v1",
        "config": {
            "id": config.get("id"),
            "initial_capital": config.get("initial_capital"),
            "total_fund": config.get("total_fund"),
            "available_cash": config.get("available_cash"),
            "base_currency": config.get("base_currency"),
            "fee_enabled": config.get("fee_enabled"),
            "fee_rates": {
                "us_fee_rate": config.get("us_fee_rate"),
                "kr_buy_fee_rate": config.get("kr_buy_fee_rate"),
                "kr_sell_fee_rate": config.get("kr_sell_fee_rate"),
                "kr_sell_tax_rate": config.get("kr_sell_tax_rate"),
                "crypto_fee_rate": config.get("crypto_fee_rate"),
            },
            "status": config.get("status"),
            "created_at": config.get("created_at"),
            "updated_at": config.get("updated_at"),
        },
    }


def _ticker_currency(ticker: str) -> str:
    tk = str(ticker).upper()
    return "KRW" if tk.endswith(".KS") or tk.endswith(".KQ") else "USD"


def _fetch_prices(tickers: List[str]) -> Dict[str, Optional[float]]:
    if not tickers:
        return {}
    try:
        import yfinance as yf

        data = yf.download(
            tickers=tickers,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
        )
    except Exception:
        return {ticker: None for ticker in tickers}

    if data is None or data.empty:
        return {ticker: None for ticker in tickers}

    multi = len(tickers) > 1
    prices: Dict[str, Optional[float]] = {}
    for ticker in tickers:
        try:
            series = data[ticker]["Close"] if multi else data["Close"]
            prices[ticker] = float(series.iloc[-1])
        except Exception:
            prices[ticker] = None
    return prices


@router.get("/portfolio/config")
async def get_portfolio_config(_: bool = Depends(check_portfolio_read_access)):
    scheduler = _get_scheduler()
    repo = PortfolioConfigRepository(scheduler.db)
    config = repo.get_active() or repo.get_latest()
    if not config:
        return {"schema_version": "v1", "config": None}
    return _config_to_response(config)


@router.post("/portfolio/config")
async def upsert_portfolio_config(
    req: PortfolioConfigRequest,
    _: bool = Depends(check_admin_token),
):
    scheduler = _get_scheduler()
    repo = PortfolioConfigRepository(scheduler.db)
    config = repo.upsert_default(
        initial_capital=req.initial_capital,
        base_currency=req.base_currency,
        fee_enabled=req.fee_enabled,
        fee_rates=req.fee_rates.model_dump(exclude_none=True) if req.fee_rates else None,
        reset_fund_to_initial=req.reset_fund_to_initial,
    )
    return _config_to_response(config)


@router.post("/portfolio/config/pause")
async def pause_portfolio_config(_: bool = Depends(check_admin_token)):
    scheduler = _get_scheduler()
    repo = PortfolioConfigRepository(scheduler.db)
    config = repo.get_active() or repo.get_latest()
    if not config:
        raise HTTPException(status_code=404, detail="Portfolio config not found")
    repo.pause(int(config["id"]))
    return {"schema_version": "v1", "message": "paused", "config_id": int(config["id"])}


@router.post("/portfolio/config/resume")
async def resume_portfolio_config(_: bool = Depends(check_admin_token)):
    scheduler = _get_scheduler()
    repo = PortfolioConfigRepository(scheduler.db)
    config = repo.get_latest()
    if not config:
        raise HTTPException(status_code=404, detail="Portfolio config not found")
    repo.resume(int(config["id"]))
    return {"schema_version": "v1", "message": "resumed", "config_id": int(config["id"])}


@router.get("/portfolio/decisions")
async def get_portfolio_decisions(
    cursor: Optional[int] = Query(None, ge=1),
    limit: int = Query(10, ge=1, le=100),
    _: bool = Depends(check_portfolio_read_access),
):
    scheduler = _get_scheduler()
    cfg_repo = PortfolioConfigRepository(scheduler.db)
    config = cfg_repo.get_active() or cfg_repo.get_latest()
    if not config:
        return {"schema_version": "v1", "items": []}

    repo = PortfolioDecisionRepository(scheduler.db)
    items = repo.list_recent(int(config["id"]), cursor=cursor, limit=limit)
    return {"schema_version": "v1", "items": items}


@router.get("/portfolio/decisions/{decision_id}")
async def get_portfolio_decision_detail(
    decision_id: int,
    _: bool = Depends(check_portfolio_read_access),
):
    scheduler = _get_scheduler()
    decision_repo = PortfolioDecisionRepository(scheduler.db)
    trade_repo = PortfolioTradeRepository(scheduler.db)
    decision = decision_repo.get_by_id(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    trades = trade_repo.list_by_decision(decision_id)
    return {"schema_version": "v1", "decision": decision, "trades": trades}


@router.get("/portfolio/holdings")
async def get_portfolio_holdings(_: bool = Depends(check_portfolio_read_access)):
    scheduler = _get_scheduler()
    cfg_repo = PortfolioConfigRepository(scheduler.db)
    holding_repo = PortfolioHoldingRepository(scheduler.db)
    config = cfg_repo.get_active() or cfg_repo.get_latest()
    if not config:
        return {
            "schema_version": "v1",
            "base_currency": "KRW",
            "snapshot_date": None,
            "holdings": [],
        }

    holdings = holding_repo.list_latest(int(config["id"]))
    if not holdings:
        return {
            "schema_version": "v1",
            "base_currency": config.get("base_currency", "KRW"),
            "snapshot_date": None,
            "holdings": [],
        }

    exchange_rate = ExchangeRateService().get_usd_krw()
    tickers = [str(h["ticker"]).upper() for h in holdings]
    prices = _fetch_prices(tickers)

    base_currency = str(config.get("base_currency") or "KRW").upper()
    snapshot_date = holdings[0].get("snapshot_date")
    if hasattr(snapshot_date, "isoformat"):
        snapshot_date = snapshot_date.isoformat()

    payload: List[Dict[str, Any]] = []
    for row in holdings:
        ticker = str(row["ticker"]).upper()
        shares = float(row.get("shares") or 0.0)
        avg_cost = float(row.get("avg_cost") or 0.0)
        currency = str(row.get("currency") or _ticker_currency(ticker)).upper()
        current_price = prices.get(ticker)
        current_value_local = (
            float(current_price) * shares if current_price is not None else avg_cost * shares
        )
        current_value_base = (
            current_value_local
            if currency == base_currency
            else (
                current_value_local * exchange_rate
                if base_currency == "KRW"
                else current_value_local / exchange_rate
            )
        )
        payload.append(
            {
                "ticker": ticker,
                "shares": shares,
                "avg_cost": avg_cost,
                "currency": currency,
                "current_price": current_price,
                "current_value_local": current_value_local,
                "current_value_base": current_value_base,
                "allocation_pct": float(row.get("allocation_pct") or 0.0),
            }
        )

    return {
        "schema_version": "v1",
        "base_currency": base_currency,
        "snapshot_date": snapshot_date,
        "holdings": payload,
    }


@router.get("/portfolio/trades")
async def get_portfolio_trades(
    ticker: Optional[str] = Query(None),
    cursor: Optional[int] = Query(None, ge=1),
    limit: int = Query(10, ge=1, le=100),
    _: bool = Depends(check_portfolio_read_access),
):
    scheduler = _get_scheduler()
    cfg_repo = PortfolioConfigRepository(scheduler.db)
    config = cfg_repo.get_active() or cfg_repo.get_latest()
    if not config:
        return {"schema_version": "v1", "items": []}

    repo = PortfolioTradeRepository(scheduler.db)
    items = repo.list_recent(
        config_id=int(config["id"]),
        ticker=ticker,
        cursor=cursor,
        limit=limit,
    )
    return {"schema_version": "v1", "items": items}


@router.get("/portfolio/reflections")
async def get_portfolio_reflections(
    cursor: Optional[int] = Query(None, ge=1),
    limit: int = Query(10, ge=1, le=100),
    _: bool = Depends(check_portfolio_read_access),
):
    scheduler = _get_scheduler()
    cfg_repo = PortfolioConfigRepository(scheduler.db)
    config = cfg_repo.get_active() or cfg_repo.get_latest()
    if not config:
        return {"schema_version": "v1", "items": []}

    repo = PortfolioReflectionRepository(scheduler.db)
    items = repo.list_recent(
        config_id=int(config["id"]),
        cursor=cursor,
        limit=limit,
    )
    return {"schema_version": "v1", "items": items}
