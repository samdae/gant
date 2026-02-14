"""WebSocket endpoint for real-time analysis streaming.

FR-025: WebSocket /ws/analyze/{ticker}
Streams agent status during analysis execution (not persisted to report).

Architecture:
    - Client connects to WS and subscribes to status updates for a ticker
    - Queue worker broadcasts step-level updates via app_module.broadcast_status()
    - WS endpoint reads from its personal asyncio.Queue and forwards to client
    - If no analysis is running, waits until one starts
"""

import logging
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from tradingagents.api import app as app_module

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/analyze/{ticker}")
async def analyze_ws(websocket: WebSocket, ticker: str):
    """WebSocket endpoint for real-time analysis streaming.

    Args:
        ticker: Ticker symbol to observe

    Message schema:
        {
            "agent": str,          # Current agent name
            "status": str,         # "running" | "completed" | "error"
            "message": str,        # Agent output summary
            "step": int,           # Optional step number
            "phase": str,          # Optional phase label
            "total_steps": int,    # Optional total steps
            "timestamp": str       # ISO 8601
        }

    Timeout: 3600 seconds (1 hour)
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for {ticker}")

    # Create personal subscriber queue
    subscriber_queue: asyncio.Queue = asyncio.Queue()
    app_module.ws_subscribers[ticker].append(subscriber_queue)

    try:
        # Send initial status
        running = app_module.current_running_ticker
        if running == ticker:
            await websocket.send_json(
                {
                    "agent": "system",
                    "status": "running",
                    "message": f"Analysis in progress for {ticker}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        else:
            await websocket.send_json(
                {
                    "agent": "system",
                    "status": "waiting",
                    "message": f"Waiting for analysis to start for {ticker}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Stream updates from subscriber queue
        while True:
            try:
                msg = await asyncio.wait_for(
                    subscriber_queue.get(),
                    timeout=3600.0,
                )
                await websocket.send_json(msg)

                # If analysis completed or errored, close connection
                if msg.get("status") in ("completed", "error"):
                    break

            except asyncio.TimeoutError:
                logger.info(f"WebSocket timeout for {ticker}")
                await websocket.send_json(
                    {
                        "agent": "system",
                        "status": "error",
                        "message": "Connection timed out (1 hour)",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {ticker}")
    except Exception as e:
        logger.error(f"WebSocket error for {ticker}: {e}", exc_info=True)
        try:
            await websocket.send_json(
                {
                    "agent": "system",
                    "status": "error",
                    "message": f"Error: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception:
            pass
    finally:
        # Unsubscribe
        try:
            app_module.ws_subscribers[ticker].remove(subscriber_queue)
        except ValueError:
            pass
        # Clean up empty subscriber lists
        if not app_module.ws_subscribers[ticker]:
            del app_module.ws_subscribers[ticker]
        try:
            await websocket.close()
        except Exception:
            pass
