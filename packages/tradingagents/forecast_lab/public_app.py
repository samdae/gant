"""Public-only HTTP reader. Run separately from the authenticated Forecast Lab console."""

import json
import re
import time
from collections import OrderedDict
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from threading import BoundedSemaphore, Lock
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .public_projection import public_case, public_detail, public_report, public_stats

ASSETS = Path(__file__).with_name("public_web")
ORIGIN = "http://127.0.0.1:8014"
CASE_LIST = "/api/cases?limit=60"
STATS = "/api/stats"
REPORTS = "/workspace-api/reports?limit=20"
MAX_BYTES = 12 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def read_upstream(path):
    if path not in (CASE_LIST, STATS, REPORTS) and not re.fullmatch(
        r"/api/cases/[1-9][0-9]{0,15}", path
    ):
        raise ValueError("Invalid internal route")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(ORIGIN + path, timeout=4) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("Invalid response")
            return json.loads(body)
    except (URLError, ValueError, OSError, HTTPError):
        raise HTTPException(503, "Public research temporarily unavailable") from None


class ProjectionCache:
    """Bound retained public DTOs, concurrent private requests, and duplicate in-flight reads."""

    def __init__(self):
        self.lock = Lock()
        self.values = OrderedDict()
        self.running = {}
        self.slots = BoundedSemaphore(4)

    def get(self, key, project):
        with self.lock:
            entry = self.values.get(key)
            if entry and time.monotonic() < entry[0]:
                self.values.move_to_end(key)
                return entry[1]
            future = self.running.get(key)
            owner = future is None
            if owner:
                if not self.slots.acquire(blocking=False):
                    raise HTTPException(503, "Public research temporarily unavailable")
                future = self.running[key] = Future()
        if not owner:
            try:
                return future.result(timeout=6)
            except FutureTimeout:
                raise HTTPException(
                    503, "Public research temporarily unavailable"
                ) from None
        try:
            try:
                value = project()
            except Exception as exc:  # noqa: BLE001 -- public boundary must redact private upstream errors
                # Short negative caching prevents an outage from multiplying private reads.
                code = (
                    404
                    if isinstance(exc, HTTPException) and exc.status_code == 404
                    else 503
                )
                failure = HTTPException(code, "Research item unavailable")
                value = None
            else:
                failure = None
            result = value if failure is None else failure
            with self.lock:
                self.values[key] = (time.monotonic() + (5 if failure else 45), result)
                self.values.move_to_end(key)
                while len(self.values) > 64:
                    self.values.popitem(last=False)
                future.set_result(result)
            return result
        finally:
            with self.lock:
                self.running.pop(key, None)
            self.slots.release()


def create_app(reader=read_upstream):
    app = FastAPI(
        docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False
    )
    cache = ProjectionCache()

    def cached(key, project):
        result = cache.get(key, project)
        if isinstance(result, HTTPException):
            raise HTTPException(result.status_code, result.detail)
        return result

    def rows(path):
        raw = reader(path)
        if not isinstance(raw, list):
            raise TypeError("Invalid upstream list")
        return raw

    def cases():
        return cached(
            "cases",
            lambda: [
                item for row in rows(CASE_LIST)[:60] if (item := public_case(row))
            ][:30],
        )

    def reports():
        return cached(
            "reports",
            lambda: [
                item for row in rows(REPORTS)[:20] if (item := public_report(row))
            ],
        )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.method != "GET":
            response = JSONResponse(
                {"detail": "Method not allowed"}, 405, headers={"Allow": "GET"}
            )
        elif len(request.scope.get("raw_path", b"")) > 128:
            response = JSONResponse({"detail": "Unknown route"}, 404)
        elif request.url.query and not (
            request.url.path in ("/", "/research/")
            and re.fullmatch(r"case=[1-9][0-9]{0,15}", request.url.query)
        ):
            response = JSONResponse({"detail": "Unsupported query"}, 400)
        else:
            response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'",
                "Cache-Control": "public, max-age=30"
                if response.status_code == 200 and request.url.path != "/healthz"
                else "no-store",
            }
        )
        return response

    @app.get("/healthz")
    def health():
        return {"service": "forecast-lab-public", "ok": True}

    @app.get("/research/")
    @app.get("/")
    def home():
        return FileResponse(ASSETS / "index.html", media_type="text/html")

    @app.get("/public.css")
    def styles():
        return FileResponse(ASSETS / "public.css", media_type="text/css")

    @app.get("/public.js")
    def script():
        return FileResponse(ASSETS / "public.js", media_type="application/javascript")

    @app.get("/public-api/overview")
    def overview():
        return {
            "cases": cases(),
            **cached("stats", lambda: public_stats(reader(STATS))),
        }

    @app.get("/public-api/cases/{case_id:int}")
    def case(case_id: int):
        summary = next((row for row in cases() if row["id"] == case_id), None)
        if summary is None:
            raise HTTPException(404, "Unknown published case")

        def project():
            result = public_detail(reader(f"/api/cases/{case_id}"), summary)
            if result is None:
                raise HTTPException(404, "Unknown published case")
            return result

        return cached(("case", case_id, summary["status"]), project)

    @app.get("/public-api/reports")
    def report_list():
        return {
            "reports": [
                {k: v for k, v in row.items() if k != "sections"} for row in reports()
            ]
        }

    @app.get("/public-api/reports/{report_id:int}")
    def report_detail(report_id: int):
        for row in reports():
            if row["id"] == report_id:
                return row
        raise HTTPException(404, "Unknown published report")

    return app


app = create_app()
