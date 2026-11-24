"""Loopback research dashboard and operator-only CLI. No dependency on the production API."""

import argparse
import logging
import os
import re
import threading
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg import Error as DatabaseError
from psycopg.conninfo import conninfo_to_dict

from .classification import catalog_classification
from .worker import Progress, Worker

LOG = logging.getLogger(__name__)
STATIC = Path(__file__).with_name("web")


def runtime_root():
    return (
        Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TradingAgentsForecastLab"
    )


def settings():
    dsn = os.environ.get("FORECAST_LAB_DSN", "")
    cfg = conninfo_to_dict(dsn)
    if (
        cfg.get("host") != "127.0.0.1"
        or cfg.get("port") != "55434"
        or not re.fullmatch(
            r"forecast_lab_(research|acceptance|test[a-z0-9_]*)", cfg.get("dbname", "")
        )
        or any(key in cfg for key in ("hostaddr", "service", "options"))
    ):
        raise ValueError(
            "Expected isolated forecast_lab_research/test database on 127.0.0.1:55434"
        )
    return dsn


def application(
    store,
    worker,
    progress,
    enabled=True,
    interval=900,
    *,
    console=None,
    dist=None,
    readiness=None,
):
    stop = threading.Event()

    def scheduled():
        while not stop.is_set():
            try:
                worker.scan(stopping=stop.is_set)
            except Exception:
                LOG.exception("Forecast lab scan failed")
            stop.wait(interval)

    def capture_references():
        while not stop.wait(min(interval, 60)):
            worker.capture()

    @asynccontextmanager
    async def lifespan(app):
        store.init()
        async with AsyncExitStack() as stack:
            if console is not None:
                await stack.enter_async_context(
                    console.router.lifespan_context(console)
                )
            threads = []
            if enabled:
                thread = threading.Thread(
                    target=scheduled, name="forecast-lab", daemon=True
                )
                threads.append(thread)
                if worker.reference:
                    threads.append(
                        threading.Thread(
                            target=capture_references,
                            name="forecast-lab-reference",
                            daemon=True,
                        )
                    )
                for thread in threads:
                    thread.start()
            try:
                yield
            finally:
                stop.set()
                for thread in threads:
                    thread.join(timeout=1)

    app = FastAPI(
        title="Forecast Lab", lifespan=lifespan, docs_url=None, redoc_url=None
    )

    @app.get("/health")
    def health():
        return {"service": "forecast-lab", "ok": True}

    @app.get("/ready")
    def ready():
        try:
            store.list_tickers()
            if console is not None and not readiness():
                raise HTTPException(503, "Workspace console unavailable")
        except DatabaseError:
            raise HTTPException(503, "Database unavailable") from None
        return {"ready": True, **({"console": True} if console is not None else {})}

    @app.get("/api/status")
    def status():
        return {
            "scheduler_enabled": enabled,
            "interval_seconds": interval,
            "reference_enabled": bool(worker.reference),
            "progress": progress.read(),
            "tickers": [
                {**item, "classification": catalog_classification(item["ticker"], item["market"])}
                for item in store.list_tickers()
            ],
        }

    def validate_range(from_date, to_date):
        if from_date and to_date and from_date > to_date:
            raise HTTPException(422, "from_date must be on or before to_date")

    @app.get("/api/stats")
    def stats(
        market: Literal["us", "kr"] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ):
        validate_range(from_date, to_date)
        return store.stats(market=market, from_date=from_date, to_date=to_date)

    @app.get("/api/cases")
    def cases(
        limit: int = Query(50, ge=1, le=200),
        published_only: bool = False,
        before_id: int | None = Query(None, ge=1),
        market: Literal["us", "kr"] | None = None,
        ticker: str | None = Query(None, max_length=24),
        from_date: date | None = None,
        to_date: date | None = None,
    ):
        validate_range(from_date, to_date)
        return store.recent_cases(
            limit=limit,
            before_id=before_id,
            published_only=published_only,
            market=market,
            ticker=ticker,
            from_date=from_date,
            to_date=to_date,
        )

    @app.get("/api/cases/{case_id}")
    def case(case_id: int, request: Request, response: Response):
        validators = {
            value.strip().removeprefix("W/")
            for value in request.headers.get("if-none-match", "").split(",")
        }
        tag, detail = store.detail_if_changed(case_id, validators)
        if tag is None:
            raise HTTPException(404, "Unknown case")
        headers = {"ETag": "W/" + tag, "Cache-Control": "private, no-cache"}
        if detail is None:
            return Response(status_code=304, headers=headers)
        response.headers.update(headers)
        return detail

    app.mount("/research", StaticFiles(directory=STATIC, html=True), name="research")
    if console is None:

        @app.get("/")
        def home():
            return FileResponse(STATIC / "index.html")
    else:
        app.mount("/workspace-api", console)

    @app.get("/lab.js")
    def script():
        return FileResponse(STATIC / "lab.js", media_type="application/javascript")

    @app.get("/lab.css")
    def style():
        return FileResponse(STATIC / "lab.css", media_type="text/css")

    if console is not None:
        from .console import mount_frontend

        mount_frontend(app, dist)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=runtime_root() / "lab.env")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--console", action="store_true")
    seed = sub.add_parser("seed")
    seed.add_argument("--us", nargs="+", default=[])
    seed.add_argument("--kr", nargs="+", default=[])
    run = sub.add_parser("run-once")
    run.add_argument("--limit", type=int)
    args = parser.parse_args()
    console = None
    readiness = None
    dist = None
    if getattr(args, "console", False):
        from .console import configure_runtime, console_ready

        dist = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"
        console = configure_runtime(runtime_root(), args.env_file)
        readiness = console_ready
    else:
        load_dotenv(args.env_file, override=False, interpolate=False)
    dsn = settings()
    from .store import Store

    logging.basicConfig(level=logging.INFO)
    store = Store(dsn)
    if args.command == "seed":
        entries = [(t.upper(), m) for m in ("us", "kr") for t in getattr(args, m)]
        if not entries or any(
            not re.fullmatch(
                r"[A-Z]{1,6}(?:[.-][A-Z]{1,2})?"
                if market == "us"
                else r"[0-9]{6}\.(KS|KQ)",
                ticker,
            )
            for ticker, market in entries
        ):
            parser.error(
                "Supply listed US stock/ETF symbols or six-digit KR .KS/.KQ symbols"
            )
        store.init()
        for ticker, market in entries:
            store.set_ticker(ticker, market)
        print(f"Seeded {len(entries)} entries.")
        return
    from .engine import EXPERIMENT_VERSION, ForecastEngine

    progress = Progress(os.environ.get("FORECAST_LAB_STATE_DIR") or runtime_root())
    reference = None
    if os.getenv("FORECAST_LAB_LEGACY_REFERENCE", "0").lower() in {"1", "true", "yes"}:
        from .incumbent import IncumbentCollector

        reference = IncumbentCollector(store)
    worker = Worker(
        store,
        ForecastEngine(),
        progress,
        reference=reference,
        experiment_version=EXPERIMENT_VERSION,
    )
    if args.command == "run-once":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be positive")
        store.init()
        print(worker.scan(limit=args.limit))
        return
    import uvicorn

    enabled = os.getenv("FORECAST_LAB_SCHEDULER_ENABLED", "1").lower() in {
        "1",
        "true",
        "yes",
    }
    interval = max(1, int(os.getenv("FORECAST_LAB_INTERVAL_SECONDS", "900")))
    uvicorn.run(
        application(
            store,
            worker,
            progress,
            enabled,
            interval,
            console=console,
            dist=dist,
            readiness=readiness,
        ),
        host="127.0.0.1",
        port=8014,
        access_log=False,
    )


if __name__ == "__main__":
    main()
