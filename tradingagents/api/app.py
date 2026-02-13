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
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.scheduler.ticker_scheduler import TickerScheduler

logger = logging.getLogger(__name__)

# Global instances (initialized in lifespan)
graph: Optional[TradingAgentsGraph] = None
scheduler: Optional[TickerScheduler] = None
queue_worker_task: Optional[asyncio.Task] = None


async def _queue_worker():
    """Worker: Consume analysis queue sequentially (max_workers=1).

    FR-025: Single queue worker for sequential execution (LLM rate limit)
    """
    from tradingagents.scheduler.ticker_scheduler import analysis_queue

    logger.info("Queue worker started")
    
    while True:
        try:
            ticker = await analysis_queue.get()
            logger.info(f"Queue worker: Processing {ticker}")
            
            # Run analysis in thread (blocking I/O)
            await asyncio.to_thread(scheduler._run_analysis_cycle, ticker)
            
            analysis_queue.task_done()
            logger.info(f"Queue worker: Completed {ticker}")
            
        except asyncio.CancelledError:
            logger.info("Queue worker cancelled")
            break
        except Exception as e:
            logger.error(f"Queue worker error: {e}", exc_info=True)
            analysis_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event: Start scheduler + queue worker on startup."""
    global graph, scheduler, queue_worker_task

    logger.info("Starting TradingAgents API...")

    # Initialize graph
    graph = TradingAgentsGraph(config=DEFAULT_CONFIG)
    logger.info("TradingAgentsGraph initialized")

    # Initialize scheduler
    scheduler = TickerScheduler(graph=graph, config=DEFAULT_CONFIG)
    
    # Auto-load schedules from config
    for schedule_item in DEFAULT_CONFIG.get("schedules", []):
        ticker = schedule_item["ticker"]
        interval_days = schedule_item.get("interval_days", 4)
        initial_capital = schedule_item.get("initial_capital", DEFAULT_CONFIG["default_initial_capital"])
        
        scheduler.add_ticker(ticker, interval_days, initial_capital)
        logger.info(f"Auto-loaded schedule: {ticker} (every {interval_days} days)")

    # Start scheduler
    if DEFAULT_CONFIG.get("scheduler_enabled", False):
        scheduler.start()
        logger.info("APScheduler started")
    else:
        logger.info("APScheduler disabled (scheduler_enabled=False)")

    # Start queue worker
    queue_worker_task = asyncio.create_task(_queue_worker())
    logger.info("Queue worker task started")

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

    # CORS: Allow all (behind Cloudflare Tunnel)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
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
