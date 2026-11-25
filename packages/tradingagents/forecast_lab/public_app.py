"""Public-only HTTP reader. Run separately from the authenticated Forecast Lab console."""

import hashlib
import json
import re
import time
from collections import OrderedDict
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import date
from pathlib import Path
from threading import BoundedSemaphore, Lock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from .public_projection import public_case, public_detail, public_report, public_stats
from .public_research import (
    case_summary,
    research_detail,
    research_stats,
    research_status,
)

RESEARCH = Path(__file__).with_name("web")
SHELL = Path(__file__).resolve().parents[3] / "apps/web/dist"
ASSETS = Path(__file__).with_name("public_web")
ORIGIN = "http://127.0.0.1:8014"
CASE_LIST = "/api/cases?limit=60"
STATS = "/api/stats"
REPORTS = "/workspace-api/reports?limit=20"
MAX_BYTES = 12 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def research_filters(path, query, *, internal=False):
    allowed = {"market", "from_date", "to_date"}
    if path == "/api/cases":
        allowed.update(("limit", "before_id", "ticker"))
        if internal:
            allowed.add("published_only")
    pairs = parse_qsl(query, keep_blank_values=True, max_num_fields=10)
    params = dict(pairs)
    if len(params) != len(pairs) or not params.keys() <= allowed:
        raise ValueError("Unsupported query")
    for key, value in pairs:
        if key == "market" and value not in ("kr", "us"):
            raise ValueError("Invalid market")
        if (
            key in ("from_date", "to_date")
            and date.fromisoformat(value).isoformat() != value
        ):
            raise ValueError("Invalid date")
        if key in ("limit", "before_id") and (
            not re.fullmatch(r"[1-9][0-9]{0,15}", value)
            or (key == "limit" and int(value) > 200)
        ):
            raise ValueError("Invalid count")
        if key == "ticker" and not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,15}", value):
            raise ValueError("Invalid ticker")
        if key == "published_only" and value != "true":
            raise ValueError("Invalid publication filter")
    if params.get("from_date", "") > params.get("to_date", "9999-12-31"):
        raise ValueError("Invalid date range")
    return params


def read_upstream(path):
    parts = urlsplit(path)
    if parts.path in ("/api/cases", "/api/stats") and not (
        parts.scheme or parts.netloc or parts.fragment
    ):
        research_filters(parts.path, parts.query, internal=True)
    elif path not in ("/api/status", REPORTS) and not re.fullmatch(
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
    except HTTPError as exc:
        code = 404 if exc.code == 404 else 503
        raise HTTPException(code, "Public research temporarily unavailable") from None
    except (URLError, ValueError, OSError):
        raise HTTPException(503, "Public research temporarily unavailable") from None


class ProjectionCache:
    """Bound retained public DTOs, concurrent private requests, and duplicate in-flight reads."""

    def __init__(self, max_inflight=4):
        self.lock = Lock()
        self.values = OrderedDict()
        self.running = {}
        self.slots = BoundedSemaphore(max_inflight)

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


def create_app(reader=read_upstream, *, dist=SHELL, workspace_reader=None):
    from .console_public_reads import install_console_reads

    dist = Path(dist).resolve()
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
        elif (
            len(request.scope.get("query_string", b"")) > 1024
            or request.url.query
            and not (
                request.url.path.startswith("/workspace-api/")
                or request.url.path in ("/api/cases", "/api/stats")
                or (
                    request.url.path == "/sw.js"
                    and len(request.query_params.multi_items()) == 1
                    and re.fullmatch(
                        r"/assets/index-[a-zA-Z0-9_-]{1,100}\.js",
                        request.query_params.get("build", ""),
                    )
                )
                or (
                    request.url.path == "/"
                    and re.fullmatch(r"case=[1-9][0-9]{0,15}", request.url.query)
                )
                or (
                    request.url.path == "/research/"
                    and set(request.query_params)
                    <= {"case", "embedded", "market", "from_date", "to_date", "pages"}
                )
                or (
                    request.url.path
                    in (
                        "/lab.css",
                        "/lab.js",
                        "/research/workspace-tokens.css",
                        "/research/instrument-names.json",
                    )
                    and re.fullmatch(r"v=[A-Za-z0-9.-]{1,40}", request.url.query)
                )
            )
        ):
            response = JSONResponse({"detail": "Unsupported query"}, 400)
        else:
            response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "SAMEORIGIN",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-src 'self'; frame-ancestors 'self'; form-action 'none'; base-uri 'none'",
                "Cache-Control": "public, max-age=30"
                if response.status_code == 200
                and request.url.path not in ("/", "/research/", "/healthz", "/ready", "/sw.js")
                else "no-store",
            }
        )
        return response

    @app.get("/healthz")
    def health():
        return {"service": "forecast-lab-public", "ok": True}

    def shell_html():
        try:
            return (dist / "index.html").read_text(encoding="utf-8")
        except OSError:
            raise HTTPException(503, "Workspace build unavailable") from None

    @app.get("/")
    def home():
        marker = '<meta name="forecast-console-access" content="public-readonly">'
        return HTMLResponse(shell_html().replace("</head>", marker + "</head>", 1))

    @app.get("/sw.js")
    def retire_v1_worker():
        return FileResponse(ASSETS / "retire-v1.js", media_type="application/javascript")

    @app.get("/assets/{asset}")
    def shell_asset(asset: str):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+\.(?:css|js)", asset) or not re.search(
            r'(?:src|href)="/assets/' + re.escape(asset) + r'"', shell_html()
        ):
            raise HTTPException(404)
        candidate = dist / "assets" / asset
        if not candidate.is_file():
            raise HTTPException(404)
        return FileResponse(candidate)

    @app.get("/favicon.svg")
    def icon():
        return FileResponse(dist / "favicon.svg", media_type="image/svg+xml")

    @app.get("/ready")
    def ready():
        return {"ready": True, "console": True}

    @app.get("/research/")
    def research_home():
        return FileResponse(RESEARCH / "index.html", media_type="text/html")

    @app.get("/research/{asset}")
    def research_asset(asset: str):
        if asset not in ("workspace-tokens.css", "instrument-names.json"):
            raise HTTPException(404)
        return FileResponse(RESEARCH / asset)

    @app.get("/lab.js")
    def research_js():
        return FileResponse(RESEARCH / "lab.js", media_type="application/javascript")

    @app.get("/lab.css")
    def research_css():
        return FileResponse(RESEARCH / "lab.css", media_type="text/css")

    @app.get("/api/status")
    def status():
        return cached("research-status", lambda: research_status(reader("/api/status")))

    @app.get("/api/stats")
    @app.get("/api/cases")
    def research_list(request: Request):
        path = request.url.path
        try:
            params = research_filters(path, request.url.query)
        except ValueError:
            raise HTTPException(400, "Unsupported research filter") from None
        if path == "/api/cases":
            params["published_only"] = "true"
        query = urlencode(sorted(params.items()))
        source = path + ("?" + query if query else "")
        if path == "/api/stats":
            return cached(
                ("research-stats", source), lambda: research_stats(reader(source))
            )
        return cached(
            ("research-list", source),
            lambda: [item for row in rows(source) if (item := case_summary(row))],
        )

    @app.get("/api/cases/{case_id:int}")
    def research_case(case_id: int, request: Request):
        if not 0 < case_id < 10**16:
            raise HTTPException(404)

        def project():
            raw = reader("/api/cases/" + str(case_id))
            data = research_detail(raw)
            if not data or data["id"] != case_id:
                raise HTTPException(404)
            body = JSONResponse(data).body
            return body, '"' + hashlib.sha256(body).hexdigest() + '"'

        body, tag = cached(("research-detail", case_id), project)
        headers = {"ETag": tag}
        if request.headers.get("if-none-match") == tag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type="application/json", headers=headers)

    install_console_reads(app, reader=workspace_reader)

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
