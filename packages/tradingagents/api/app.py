"""FastAPI application for TradingAgents.

FR-025: REST API + WebSocket
FR-026: Public READ + Authenticated WRITE

Deployment:
    uv run uvicorn tradingagents.api.app:app --port 8000

Architecture:
    Single process — FastAPI lifespan event starts APScheduler + queue worker
"""

import os
import sys
import time
import logging
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.scheduler.ticker_scheduler import TickerScheduler
import tradingagents.scheduler.ticker_scheduler as ticker_scheduler_module

def _configure_logging() -> None:
    level_name = os.getenv("TRADINGAGENTS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


_configure_logging()

logger = logging.getLogger(__name__)

# Global instances (initialized in lifespan)
graph: Optional[TradingAgentsGraph] = None
scheduler: Optional[TickerScheduler] = None
queue_worker_task: Optional[asyncio.Task] = None

# --- State tracking (Fix: GET /queue, GET /health, WS broadcast) ---
_app_start_time: float = 0.0
_event_loop: Optional[asyncio.AbstractEventLoop] = None
current_running_ticker: Optional[str] = None
ws_subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)


_AGENT_STEPS = {
    "Market Analyst": (1, "Data Collection"),
    "Social Analyst": (2, "Data Collection"),
    "News Analyst": (3, "Data Collection"),
    "Fundamentals Analyst": (4, "Data Collection"),
    "Bull Researcher": (5, "Investment Debate"),
    "Bear Researcher": (6, "Investment Debate"),
    "Research Manager": (7, "Investment Debate"),
    "Trader": (8, "Trade Decision"),
    "Aggressive Analyst": (9, "Risk Assessment"),
    "Neutral Analyst": (10, "Risk Assessment"),
    "Conservative Analyst": (11, "Risk Assessment"),
    "Risk Judge": (12, "Risk Assessment"),
    "Portfolio Agent": (13, "Execution"),
}
_TOTAL_STEPS = 13


def _get_cors_origins() -> List[str]:
    raw = os.getenv("TRADINGAGENTS_CORS_ORIGINS", "").strip()
    if not raw:
        return ["*"]
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["*"]


def broadcast_status(
    ticker: str,
    agent: str,
    status: str,
    message: str,
    schedule_job_id: Optional[int] = None,
):
    """Thread-safe broadcast to WebSocket subscribers.

    Can be called from any thread (including analysis worker thread).
    Uses run_coroutine_threadsafe to push to async queues.
    """
    step_info = _AGENT_STEPS.get(agent)
    msg = {
        "agent": agent,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if step_info:
        msg["step"] = step_info[0]
        msg["phase"] = step_info[1]
        msg["total_steps"] = _TOTAL_STEPS

    try:
        from tradingagents.runtime_context import get_current_schedule_job_id
        from tradingagents.storage import ScheduleEventRepository

        if schedule_job_id is None:
            schedule_job_id = get_current_schedule_job_id()

        ScheduleEventRepository(scheduler.db).create(
            ticker=ticker,
            agent=agent,
            status=status,
            message=message,
            schedule_job_id=schedule_job_id,
            step=msg.get("step"),
            phase=msg.get("phase"),
        )
    except Exception as e:
        logger.warning(f"Failed to store schedule event: {e}")

    if ticker not in ws_subscribers or not ws_subscribers[ticker]:
        return

    logger.info(
        "Status update: ticker=%s agent=%s status=%s message=%s",
        ticker,
        agent,
        status,
        message,
    )

    for q in ws_subscribers[ticker]:
        if _event_loop and _event_loop.is_running():
            asyncio.run_coroutine_threadsafe(q.put(msg), _event_loop)


async def _queue_worker():
    """Worker: Consume analysis queue sequentially (max_workers=1).

    FR-025: Single queue worker for sequential execution (LLM rate limit)
    """
    from tradingagents.scheduler.ticker_scheduler import analysis_queue

    global current_running_ticker

    logger.info("Queue worker started")

    def _extract_ticker(item: Any) -> Optional[str]:
        if isinstance(item, tuple) and len(item) == 3:
            _, _, payload = item
            return _extract_ticker(payload)
        if isinstance(item, dict):
            return item.get("ticker")
        if isinstance(item, str):
            return item
        return None

    def _queue_snapshot(queue: Optional[asyncio.PriorityQueue]) -> list[str]:
        if not queue:
            return []
        try:
            pending = list(getattr(queue, "_queue", []))
        except Exception:
            return []

        tickers = []
        for item in pending:
            ticker = _extract_ticker(item)
            if ticker:
                tickers.append(str(ticker))
        return tickers

    while True:
        try:
            priority, _seq, item = await analysis_queue.get()
            if isinstance(item, dict):
                ticker = item.get("ticker")
                job_id = item.get("schedule_job_id")
            else:
                ticker = item
                job_id = None

            if not ticker:
                logger.warning("Queue worker: Skipping empty ticker")
                analysis_queue.task_done()
                continue

            logger.info(
                "Queue dequeue: ticker=%s pending=%s",
                ticker,
                _queue_snapshot(analysis_queue),
            )
            current_running_ticker = ticker
            logger.info(f"Queue worker: Processing {ticker}")

            broadcast_status(
                ticker,
                "system",
                "running",
                f"Starting analysis for {ticker}",
                schedule_job_id=job_id,
            )

            if graph:
                graph.set_status_callback(
                    lambda agent, status, msg, t=ticker: broadcast_status(
                        t, agent, status, msg
                    )
                )

            is_retrospective = isinstance(item, dict) and item.get("type") == "retrospective"
            is_rag_validation = isinstance(item, dict) and item.get("type") == "rag_validation"

            try:
                if is_retrospective:
                    from tradingagents.retrospective.service import run_retrospective_analysis
                    await asyncio.to_thread(
                        run_retrospective_analysis,
                        scheduler.db,
                        item,
                        scheduler.config,
                    )
                    broadcast_status(
                        ticker, "system", "completed",
                        f"Retrospective analysis complete for {ticker}",
                    )
                elif is_rag_validation:
                    from tradingagents.rag_validator import RAGValidatorService

                    service = RAGValidatorService(scheduler.db, scheduler.config)
                    retrospective_id = item.get("retrospective_id")
                    await asyncio.to_thread(service.validate, retrospective_id)
                    broadcast_status(
                        ticker,
                        "system",
                        "completed",
                        f"RAG validation complete for {ticker}",
                    )
                else:
                    await asyncio.to_thread(
                        scheduler._run_analysis_cycle,
                        ticker,
                        job_id,
                    )
                    broadcast_status(
                        ticker, "system", "completed",
                        f"Analysis complete for {ticker}",
                        schedule_job_id=job_id,
                    )
                if graph:
                    graph.set_status_callback(None)
            except Exception as e:
                broadcast_status(
                    ticker, "system", "error",
                    (
                        f"Retrospective analysis failed: {str(e)}"
                        if is_retrospective
                        else (
                            f"RAG validation failed: {str(e)}"
                            if is_rag_validation
                            else f"Analysis failed: {str(e)}"
                        )
                    ),
                    schedule_job_id=job_id,
                )
                if graph:
                    graph.set_status_callback(None)
                raise

            analysis_queue.task_done()
            current_running_ticker = None
            logger.info(f"Queue worker: Completed {ticker}")

        except asyncio.CancelledError:
            logger.info("Queue worker cancelled")
            current_running_ticker = None
            break
        except Exception as e:
            logger.error(f"Queue worker error: {e}", exc_info=True)
            current_running_ticker = None
            try:
                analysis_queue.task_done()
            except ValueError:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event: Start scheduler + queue worker on startup."""
    global graph, scheduler, queue_worker_task, _app_start_time, _event_loop

    _app_start_time = time.time()
    _event_loop = asyncio.get_running_loop()

    logger.info("Starting TradingAgents API...")

    # P3-D: Fail fast if ADMIN_TOKEN not set
    if not os.getenv("TRADINGAGENTS_ADMIN_TOKEN"):
        raise RuntimeError(
            "TRADINGAGENTS_ADMIN_TOKEN environment variable is required. "
            "Set it before starting the server."
        )

    # P1-A: Initialize global analysis queue (PriorityQueue for scheduled vs retrospective)
    ticker_scheduler_module.analysis_queue = asyncio.PriorityQueue()

    # Initialize graph
    graph = TradingAgentsGraph(config=DEFAULT_CONFIG)
    logger.info("TradingAgentsGraph initialized")

    # Initialize scheduler
    scheduler = TickerScheduler(graph=graph, config=DEFAULT_CONFIG)
    scheduler.set_queue(ticker_scheduler_module.analysis_queue, _event_loop)

    # Auto-load schedules from config into DB + scheduler
    from tradingagents.storage import ScheduleConfigRepository

    schedule_config_repo = ScheduleConfigRepository(scheduler.db)
    for schedule_item in DEFAULT_CONFIG.get("schedules", []):
        ticker = schedule_item["ticker"]
        interval_days = schedule_item.get("interval_days", 1)

        schedule_config_repo.upsert(ticker, interval_days)
        logger.info(f"Auto-loaded schedule: {ticker} (every {interval_days} days)")

    # Load schedules from DB into scheduler
    try:
        for cfg in schedule_config_repo.get_all():
            scheduler.add_ticker(
                cfg["ticker"], cfg["interval_days"], market=cfg.get("market", "us"),
            )
    except Exception as e:
        logger.warning(f"Failed to load schedules from DB: {e}")

    # Start scheduler
    if DEFAULT_CONFIG.get("scheduler_enabled", False):
        scheduler.start()
        logger.info("APScheduler started")
    else:
        logger.info("APScheduler disabled (scheduler_enabled=False)")

    # Start queue worker
    queue_worker_task = asyncio.create_task(_queue_worker())
    logger.info("Queue worker task started")

    # Re-queue incomplete retrospective analyses from previous run
    try:
        from tradingagents.storage.retrospective_repo import RetrospectiveRepository
        from tradingagents.scheduler.ticker_scheduler import PRIORITY_RETROSPECTIVE
        retro_repo = RetrospectiveRepository(scheduler.db)
        incomplete = retro_repo.get_incomplete()
        for row in incomplete:
            scheduler._enqueue_item(
                {
                    "type": "retrospective",
                    "ticker": row["ticker"],
                    "position_id": row["position_id"],
                    "retro_id": row["id"],
                },
                priority=PRIORITY_RETROSPECTIVE,
                skip_dedup=True,
            )
        if incomplete:
            logger.info(f"Re-queued {len(incomplete)} incomplete retrospective analyses")
    except Exception as e:
        logger.warning(f"Failed to re-queue retrospective analyses: {e}")

    logger.info("✅ TradingAgents API ready")

    yield

    # Shutdown
    logger.info("Shutting down TradingAgents API...")

    # Cancel queue worker
    if queue_worker_task:
        queue_worker_task.cancel()
        try:
            await queue_worker_task
        except asyncio.CancelledError:
            pass

    # Stop scheduler
    if scheduler:
        scheduler.stop()
        logger.info("APScheduler stopped")

    _event_loop = None
    logger.info("✅ TradingAgents API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="TradingAgents API",
        description="REST API + WebSocket for AI-driven trading analysis pipeline",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS: Allow from configured origins
    cors_origins = _get_cors_origins()
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from tradingagents.api import routes
    from tradingagents.api import ws

    app.include_router(routes.router)
    app.include_router(ws.router)

    return app


# App instance (for uvicorn)
app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = DEFAULT_CONFIG.get("api_port", 8000)

    uvicorn.run(
        "tradingagents.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
