"""Finite public read models for the paper-trading console."""

import json
import math
import re
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

from fastapi import HTTPException, Request

from .public_projection import NAMES

NARRATIVES = [
    "market_report",
    "fundamentals_report",
    "investment_debate_judge_decision",
    "bull_history",
    "bear_history",
    "investment_plan",
    "trader_investment_decision",
    "trader_investment_judge_decision",
    "aggressive_history",
    "conservative_history",
    "neutral_history",
    "final_trade_decision",
    "pa_opinion",
]

PRIVATE = re.compile(
    r"""(?ix)
(?:-----BEGIN\s+[A-Z ]*PRIVATE\s+KEY|\bBearer\s+[A-Za-z0-9._~+/=-]{4,}
|\b(?:sk-(?:proj-)?[\w-]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|AKIA[A-Z0-9]{16}|eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+)
|\b(?:[A-Z][A-Z0-9_]*_)?(?:authorization|(?:api|access|secret|admin|refresh|auth|broker)[_ -]?(?:key|token|secret)|password|passwd|client[_ -]?secret|cookie|set-cookie|database_url|dsn)\s*["']?\s*[:=]
|\b(?:system[_ -]?prompt|developer[_ -]?message|traceback|stacktrace|tool_calls?|additional_kwargs|response_metadata|tool_call_id|AIMessage|HumanMessage|SystemMessage|credential[s]?|TRADINGAGENTS_ADMIN_TOKEN|PGPASSWORD)\b
|(?:postgres(?:ql)?|redis|amqp|file|ssh)://|\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.\d{1,3}){2})\b|\b(?:127\.0\.0\.1|localhost)\b
|(?:[a-z]:[\\/]|\\\\[a-z0-9]|/(?:home|users|etc|var|mnt|usr|tmp|opt|root|proc|run)/)
|\b[a-z]+://[^\s/]+@|(?:system|assistant|tool|developer)\s*:\s*\n
|^\s*(?:Traceback|File\s+"|at\s+[\w.]+\s*\()|(?:계좌번호|비밀번호|비밀키|접근\s*토큰)
)""",
    re.MULTILINE,
)


def public_narrative(value):
    """Publish finished analytical prose; never return opaque provider envelopes."""
    if not isinstance(value, str) or not value.strip() or len(value) > 64000:
        return None
    if PRIVATE.search(value) or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
        return None
    if re.search(
        r'(?m)^\s*(?:system|assistant|human|user|tool|developer)\s*:|[\[{]\s*["\'](?:role|tool_calls|content|trace|messages|rag_docs|audit)["\']\s*:',
        value,
        re.IGNORECASE,
    ):
        return None
    if value.lstrip().startswith(("{", '["', "[{")):
        return None
    # Historical reports sometimes append a fenced machine-readable strategy payload.
    prose = re.split(r"(?m)^\s*\x60{3}", value, maxsplit=1)[0].strip()
    prose = re.sub(r"!?\[([^\]\n]*)\]\([^\n)]*\)", r"\1", prose)
    prose = re.sub(r"https?://[^\s<>()]+", "", prose, flags=re.IGNORECASE)
    if re.search(r"<(?:[a-z!/])|(?:https?|ftp)://", prose, re.IGNORECASE):
        return None
    return prose or None


def num(x):
    return (
        x if type(x) in (float, int) and math.isfinite(x) and abs(x) <= 1e22 else None
    )


def time_value(x):
    if not isinstance(x, str) or len(x) > 40:
        return None
    try:
        return (
            date.fromisoformat(x).isoformat()
            if len(x) == 10
            else datetime.fromisoformat(x).isoformat()
        )
    except ValueError:
        return None


def symbol(x):
    return (
        x
        if isinstance(x, str) and re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,15}", x)
        else None
    )


def row(value, *, numbers="", times="", enums=None, symbols="", prose=""):
    if not isinstance(value, dict):
        return {}
    result = {}
    for fields, convert in (
        (numbers, num),
        (times, time_value),
        (symbols, symbol),
        (prose, public_narrative),
    ):
        result.update({k: convert(value[k]) for k in fields.split() if k in value})
    for key, options in (enums or {}).items():
        if key in value:
            result[key] = (
                value[key]
                if isinstance(value[key], str) and value[key] in options
                else None
            )
    return result


def collection(value, project, limit=2000):
    if not isinstance(value, list):
        raise TypeError("Invalid read model")
    return [project(v) for v in value[:limit] if isinstance(v, dict)]


ACTION = ("BUY", "SELL", "HOLD", "buy", "sell", "hold", "매수", "매도", "관망", "보유")
STATUS = (
    "completed",
    "done",
    "failed",
    "skipped",
    "pending",
    "running",
    "queued",
    "active",
    "closed",
    "reset",
    "open",
    "paused",
    "inactive",
    "missing",
    "success",
)
CURRENCY = ("USD", "KRW")
METRICS = """active_positions closed_positions wins losses incomplete_positions unpriced_positions
realized_cost open_cost total_unrealized_pnl total_unrealized_return_pct total_realized_pnl
total_realized_return_pct total_pnl total_return_pct analysis_accuracy_avg analysis_accuracy_count
rag_contribution_avg rag_contribution_count"""


def position(v):
    return row(
        v,
        symbols="ticker",
        numbers="id position_id shares avg_cost current_price pnl return_pct current_value_local current_value_base allocation_pct",
        times="as_of opened_at closed_at last_trade_at",
        enums={
            "currency": CURRENCY,
            "status": STATUS,
            "outcome": ("win", "loss", "unknown", "incomplete", "flat"),
        },
    )


def trade(v):
    return row(
        v,
        symbols="ticker",
        numbers="id trade_id report_id position_id shares price fee_amount amount_local amount_krw",
        times="executed_at",
        enums={"action": ACTION, "currency": CURRENCY},
    )


def report(v):
    result = row(
        v,
        symbols="ticker",
        numbers="id report_count latest_cycle scheduled_cycle portfolio_shares trade_shares",
        times="created_at latest_at",
        enums={
            k: ACTION
            for k in (
                "last_decision",
                "decision_position",
                "stored_decision_position",
                "portfolio_action",
                "trade_action",
            )
        },
        prose=" ".join(NARRATIVES),
    )
    if isinstance(v.get("execution_trades"), list):
        result["execution_trades"] = collection(v["execution_trades"], trade)
    return result


def review(v):
    result = row(
        v,
        symbols="ticker",
        numbers="id position_id reflection_id position_count completed_count total_count position_sequence analysis_count return_pct shares avg_cost",
        times="opened_at closed_at created_at latest_at position_open_date position_close_date",
        enums={
            "status": STATUS,
            "pos_status": STATUS,
            "position_status": STATUS,
            "outcome": ("win", "loss", "incomplete", "flat"),
            "market": ("us", "kr", "US", "KR"),
        },
        prose="reflection key_lessons analysis_content",
    )
    if result.get("ticker") in NAMES:
        result["display_name"] = NAMES[result["ticker"]]
    return result


def cycle(v):
    return row(
        v,
        numbers="id scheduled_cycle",
        symbols="ticker",
        times="created_at",
        enums={"status": STATUS},
    )


def schedule(v):
    result = row(v, symbols="ticker", numbers="interval_days", times="next_run_time")
    result["latest_cycle"] = cycle(v["latest_cycle"]) if v.get("latest_cycle") else None
    return result


def metrics(v):
    result = row(v, numbers=METRICS, times="as_of")
    source = v.get("by_currency") or {}
    result["by_currency"] = {
        c: row(source[c], numbers=METRICS) for c in CURRENCY if c in source
    }
    return result


def portfolio(v, kind):
    out = {"schema_version": "v1"}
    if kind == "config":
        cfg = v.get("config")
        out["config"] = (
            None
            if not cfg
            else row(
                cfg,
                numbers="id initial_capital total_fund available_cash",
                times="created_at updated_at",
                enums={"base_currency": CURRENCY, "status": STATUS},
            )
        )
        if cfg and isinstance(cfg.get("fee_enabled"), bool):
            out["config"]["fee_enabled"] = cfg["fee_enabled"]
            out["config"]["fee_rates"] = row(
                cfg.get("fee_rates"),
                numbers="us_fee_rate kr_buy_fee_rate kr_sell_fee_rate kr_sell_tax_rate crypto_fee_rate",
            )
    elif kind == "holdings":
        out.update(
            row(v, times="snapshot_date", enums={"base_currency": CURRENCY}),
            holdings=collection(v.get("holdings", []), position),
        )
    else:
        out["items"] = collection(
            v.get("items", []), trade if kind == "trades" else position
        )
    return out


def position_detail(v):
    return {
        "position": position(v.get("position", {})),
        "trades": collection(v.get("trades", []), trade),
        "reports": collection(v.get("reports", []), report, 200),
    }


def graph(v):
    return {
        **row(v, symbols="ticker", times="start end"),
        "points": collection(
            v.get("points", []),
            lambda p: row(p, numbers="open high low close volume", times="date"),
            90,
        ),
    }


def activity(v):
    return row(
        v,
        symbols="ticker",
        times="created_at",
        numbers="scheduled_cycle schedule_job_id shares price report_id trade_id",
        enums={
            "event_type": ("trade", "report", "analysis"),
            "action": ACTION,
            "decision": ACTION,
        },
    )


def items(fn):
    return lambda v: collection(v, fn)


def health(v):
    out = row(
        v,
        numbers="queue_length schedules_count",
        enums={"status": ("ok", "healthy", "degraded", "running")},
    )
    out["scheduler_running"] = v.get("scheduler_running") is True
    return out


def queue_status(v):
    return {
        **row(v, numbers="total", symbols="running"),
        "pending": [s for s in (v.get("pending") or [])[:100] if symbol(s)],
    }


FIXED = {
    "health": health,
    "metrics": metrics,
    "queue": queue_status,
    "positions/market": items(position),
    "positions/closed": items(position),
    "schedules/summary": lambda v: row(
        v, numbers="total done failed skipped running pending", times="as_of"
    ),
    "reports/tickers": items(report),
    "retrospective/summary": items(review),
    "portfolio/config": lambda v: portfolio(v, "config"),
    "portfolio/holdings": lambda v: portfolio(v, "holdings"),
    "portfolio/closed": lambda v: portfolio(v, "closed"),
}


# Query values are parsed, validated, then re-encoded; a caller cannot choose a host or path.
# Standard list requests share a bounded upstream page even when the client requests fewer rows.
def query_params(request, allowed):
    pairs = request.query_params.multi_items()
    if len(pairs) != len({k for k, _ in pairs}) or any(
        k not in allowed or len(v) > 64 for k, v in pairs
    ):
        raise HTTPException(400, "Unsupported query")
    return dict(pairs)


def integer(text, low, high):
    if not re.fullmatch("[0-9]{1,15}", str(text)):
        raise HTTPException(400, "Invalid number")
    x = int(text)
    if not low <= x <= high:
        raise HTTPException(400, "Invalid number")
    return x


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def install_console_reads(app, reader=None):
    from collections import OrderedDict
    from threading import BoundedSemaphore, Lock

    from .public_app import ProjectionCache

    opener = build_opener(ProxyHandler({}), NoRedirect())

    def local_get(path):
        # path is constructed exclusively by the finite dispatch below.
        try:
            with opener.open("http://127.0.0.1:8024" + path, timeout=5) as response:
                body = response.read(12 * 1024 * 1024 + 1)
            if len(body) > 12 * 1024 * 1024:
                raise ValueError("Invalid read response")
            return json.loads(body)
        except HTTPError as exc:
            raise HTTPException(
                404 if exc.code == 404 else 503, "Public data unavailable"
            ) from None
        except (URLError, OSError, ValueError):
            raise HTTPException(503, "Public data unavailable") from None

    get = reader or local_get
    cache = ProjectionCache(max_inflight=16)
    upstream_slots = BoundedSemaphore(4)
    issued = OrderedDict()
    issued_lock = Lock()

    def cached(path, project, query=None):
        key = "/workspace-api/" + path
        if query:
            key += "?" + urlencode(sorted(query.items()))

        def load():
            if not upstream_slots.acquire(timeout=6):
                raise HTTPException(503, "Public data temporarily unavailable")
            try:
                return project(get(key))
            finally:
                upstream_slots.release()

        result = cache.get(key, load)
        if isinstance(result, HTTPException):
            raise HTTPException(result.status_code, result.detail)
        return result

    def remember(group, ids):
        with issued_lock:
            for key in ids:
                if type(key) is int:
                    issued[group, key] = True
                    issued.move_to_end((group, key))
            while len(issued) > 2048:
                issued.popitem(last=False)

    def known(group, key):
        with issued_lock:
            return (group, key) in issued

    def checked_symbol(ticker):
        if symbol(ticker) is None:
            raise HTTPException(404, "Unknown instrument")
        if ticker not in NAMES and not any(
            r.get("ticker") == ticker
            for r in cached("reports/tickers", FIXED["reports/tickers"])
        ):
            raise HTTPException(404, "Unknown instrument")
        return ticker

    @app.get("/workspace-api/{path:path}", include_in_schema=False)
    def console_read(path: str, request: Request):
        if len(path) > 100 or len(request.scope["query_string"]) > 180:
            raise HTTPException(400, "Invalid read request")
        if path in FIXED:
            query_params(request, ())
            return cached(path, FIXED[path])
        if path == "tickers/names":
            query_params(request, ())
            return NAMES
        if path == "search/tickers":
            q = query_params(request, ("q",)).get("q", "").strip().casefold()
            if not 1 <= len(q) <= 20:
                raise HTTPException(400, "Invalid search")
            return [
                {"symbol": s, "name": n}
                for s, n in NAMES.items()
                if q in s.casefold() or q in n.casefold()
            ][:8]
        if path in (
            "schedules",
            "activity",
            "positions",
            "reports",
            "portfolio/trades",
            "reflections",
        ):
            permitted = {
                "schedules": ("limit",),
                "activity": ("limit",),
                "positions": ("status", "limit"),
                "reports": ("ticker", "limit"),
                "portfolio/trades": ("ticker", "limit", "cursor"),
                "reflections": ("limit", "outcome", "cursor"),
            }[path]
            q = query_params(request, permitted)
            limit = integer(q.get("limit", 10), 1, 100)
            extra = {}
            if "ticker" in q:
                extra["ticker"] = checked_symbol(q["ticker"])
            for k, choices in (
                ("outcome", ("win", "loss")),
                ("status", ("active", "closed", "reset")),
            ):
                if k in q:
                    if q[k] not in choices:
                        raise HTTPException(400, "Invalid filter")
                    extra[k] = q[k]
            cursor_group = (path, tuple(extra.items()))
            if "cursor" in q:
                cursor = integer(q["cursor"], 1, 2**49)
                if not known(cursor_group, cursor):
                    raise HTTPException(404, "Unknown page")
                extra["cursor"] = cursor
            projection = {
                "schedules": items(schedule),
                "activity": items(activity),
                "positions": items(position),
                "reports": items(report),
                "portfolio/trades": lambda v: portfolio(v, "trades"),
                "reflections": items(review),
            }[path]
            # Reports include full narratives; the Svelte detail uses at most twenty per ticker.
            cap = 20 if path == "reports" else 100
            data = cached(path, projection, {**extra, "limit": cap})
            page = (data["items"] if path == "portfolio/trades" else data)[:limit]
            if page:
                remember(cursor_group, [r.get("id") for r in page])
                if path == "reflections":
                    remember("reflection", [r.get("id") for r in page])
            return (
                {"schema_version": "v1", "items": page}
                if path == "portfolio/trades"
                else page
            )

        match = re.fullmatch(r"schedules/([^/]+)/cycles", path)
        if match:
            q = query_params(request, ("limit",))
            limit = integer(q.get("limit", 1), 1, 100)
            ticker = checked_symbol(match[1])
            return cached(f"schedules/{ticker}/cycles", items(cycle), {"limit": 100})[
                :limit
            ]

        match = re.fullmatch(r"retrospective/detail/([^/]+)", path)
        if match:
            query_params(request, ())
            ticker = checked_symbol(match[1])
            return [
                entry
                for entry in cached(f"retrospective/detail/{ticker}", items(review))
                if entry.get("status") == "completed"
            ]

        match = re.fullmatch(
            r"(positions/([0-9]+)|position/([0-9]+)/graph|reflections/detail/([0-9]+))",
            path,
        )
        if match:
            key = integer(match[2] or match[3] or match[4], 1, 2**49)
            q = query_params(request, ("days",) if match[3] else ())
            days = integer(q.get("days", 7), 1, 60)
            if match[4]:
                if not known("reflection", key):
                    first = cached("reflections", items(review), {"limit": 100})
                    remember("reflection", [r.get("id") for r in first])
                if not known("reflection", key):
                    raise HTTPException(404, "Unknown reflection")
                return cached(f"reflections/detail/{key}", review)
            ids = {
                r.get("position_id")
                for source in ("positions/market", "positions/closed")
                for r in cached(source, FIXED[source])
            }
            if key not in ids:
                raise HTTPException(404, "Unknown position")
            if match[3]:
                return cached(f"position/{key}/graph", graph, {"days": days})
            return cached(f"positions/{key}", position_detail)
        raise HTTPException(404, "Unknown read route")
