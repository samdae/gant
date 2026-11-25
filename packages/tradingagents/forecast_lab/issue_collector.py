"""Thirty-day, per-instrument issue observations. No calls from the prediction path."""

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

SOURCE = "Google News RSS"
EXPORT = "last30days agent export"
MAX_FEED_BYTES = 1_048_576
MAX_ITEMS = 40
ENGLISH = {
    "BTC-USD": "Bitcoin",
    "DLR": "Digital Realty",
    "FSLR": "First Solar",
    "GLD": "SPDR Gold Shares",
    "GOOGL": "Alphabet Google",
    "KO": "Coca-Cola",
    "NVDA": "Nvidia",
    "OXY": "Occidental Petroleum",
    "SCHP": "Schwab U.S. TIPS ETF",
    "SLV": "iShares Silver Trust",
    "SPY": "SPDR S&P 500 ETF",
    "TSLA": "Tesla",
    "VST": "Vistra",
    "WMT": "Walmart",
}
KOREAN = {
    "000660.KS": "SK하이닉스",
    "005380.KS": "현대자동차",
    "005930.KS": "삼성전자",
    "009830.KS": "한화솔루션",
    "012450.KS": "한화에어로스페이스",
    "034020.KS": "두산에너빌리티",
    "036460.KS": "한국가스공사",
    "069500.KS": "KODEX 200",
    "096770.KS": "SK이노베이션",
    "267260.KS": "HD현대일렉트릭",
    "316140.KS": "우리금융지주",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS v3_issue_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker text NOT NULL, source text NOT NULL, query text NOT NULL,
    collected_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    status text NOT NULL CHECK(status IN ('available','empty','failed')),
    item_count integer NOT NULL CHECK(item_count >= 0)
);
CREATE INDEX IF NOT EXISTS v3_issue_runs_lookup ON v3_issue_runs(ticker,collected_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS v3_issues (
    ticker text NOT NULL, url text NOT NULL, title text NOT NULL, publisher text NOT NULL,
    published_at timestamptz NOT NULL, first_seen_at timestamptz NOT NULL,
    published_day date,
    run_id bigint NOT NULL REFERENCES v3_issue_runs(id),
    PRIMARY KEY(ticker,url), UNIQUE(ticker,publisher,title,published_at),
    CHECK(published_at<=first_seen_at)
);
CREATE INDEX IF NOT EXISTS v3_issues_lookup ON v3_issues(ticker,published_at DESC,first_seen_at);
"""


def init_issues(conn):
    conn.execute(SCHEMA)


def timestamp(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("A timezone-aware issue cutoff is required")
    return value.astimezone(UTC)


def article_url(value):
    if (
        not isinstance(value, str)
        or len(value) > 3000
        or any(ord(c) < 33 for c in value)
    ):
        return None
    try:
        link = urlsplit(value)
    except ValueError:
        return None
    if (
        link.scheme != "https"
        or link.netloc != "news.google.com"
        or not re.fullmatch(r"/rss/articles/[A-Za-z0-9_-]{6,2000}", link.path)
    ):
        return None
    return "https://news.google.com" + link.path


EXPORT_LINKS = {
    "reddit": (
        {"www.reddit.com", "reddit.com"},
        r"/r/[A-Za-z0-9_]+/comments/[A-Za-z0-9]+(?:/[A-Za-z0-9_-]+)?/?",
    ),
    "x": ({"x.com", "twitter.com"}, r"/[A-Za-z0-9_]+/status/[0-9]+"),
    "youtube": ({"www.youtube.com", "youtube.com"}, r"/watch"),
    "hackernews": ({"news.ycombinator.com"}, r"/item"),
    "github": (
        {"github.com"},
        r"/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+/(?:issues|pull|discussions)/[0-9]+",
    ),
}


def submitted_article(parts):
    """Validate a clickable public DNS syntax without fetching or resolving user URLs."""
    host = parts.hostname or ""
    if parts.scheme != "https":
        return None
    if (
        parts.netloc.lower() not in (host, host + ":443")
        or len(host) > 253
        or not re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host
        )
        or host.rsplit(".", 1)[-1]
        in {
            "local",
            "localhost",
            "internal",
            "test",
            "invalid",
            "onion",
            "lan",
            "corp",
            "home",
            "arpa",
            "example",
        }
        or any(
            host == suffix or host.endswith("." + suffix)
            for suffix in ("nip.io", "sslip.io", "lvh.me", "localtest.me")
        )
    ):
        return None
    decoded = unquote(parts.path)
    if (
        len(decoded) < 2
        or not parts.path.startswith("/")
        or "\\" in decoded
        or "//" in decoded
        or any(ord(c) < 32 or c in "<>" for c in decoded)
        or any(
            segment.lower()
            in {".", "..", "redirect", "redir", "login", "logout", "oauth", "authorize"}
            for segment in decoded.split("/")
        )
    ):
        return None
    # Avoid forwarding tracking tokens, credentials or arbitrary destination arguments.
    try:
        params = parse_qsl(
            parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=12
        )
    except ValueError:
        return None
    identifiers = []
    for key, val in params:
        if key.startswith("utm_") or key in {"fbclid", "gclid"}:
            continue
        if key not in {"p", "id", "article", "story"} or not re.fullmatch(
            r"[0-9]{1,18}", val
        ):
            return None
        identifiers.append((key, val))
    return (
        "https://"
        + host
        + parts.path
        + ("?" + urlencode(identifiers) if identifiers else "")
    )


def export_url(value, publisher):
    if (
        not isinstance(value, str)
        or len(value) > 2000
        or any(ord(c) < 33 for c in value)
    ):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if (
        parts.hostname != "news.ycombinator.com"
        and isinstance(publisher, str)
        and (publisher == "hackernews" or publisher.endswith(" · Hacker News"))
    ):
        return submitted_article(parts)
    if not isinstance(publisher, str) or publisher not in EXPORT_LINKS:
        return None
    hosts, pattern = EXPORT_LINKS[publisher]
    if (
        parts.scheme != "https"
        or parts.netloc not in hosts
        or not re.fullmatch(pattern, parts.path)
    ):
        return None
    query = ""
    if publisher in ("youtube", "hackernews"):
        required = (
            r"v=[A-Za-z0-9_-]{11}" if publisher == "youtube" else r"id=[0-9]{1,12}"
        )
        if not re.fullmatch(required, parts.query):
            return None
        query = "?" + parts.query
    return "https://" + parts.netloc + parts.path + query


def published_bounds(day):
    # The export's plain date has no timezone. Account for UTC+14 to UTC-12.
    start = datetime.fromisoformat(day).replace(tzinfo=UTC)
    return start - timedelta(hours=14), start + timedelta(hours=36)


def parse_export(payload, observed, ticker):
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("Oversized export")
    raw = json.loads(payload)
    if (
        not isinstance(raw, dict)
        or not re.fullmatch(r"1\.\d+", str(raw.get("schema_version")))
        or raw.get("window_days") != 30
        or not isinstance(raw.get("results"), list)
    ):
        raise ValueError("Expected a last30days v1 agent export with a 30-day window")
    query = label(raw.get("query"), 500) or ""
    aliases = [ticker, ENGLISH.get(ticker), KOREAN.get(ticker)]
    if not any(
        re.search(
            r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])",
            query,
            re.IGNORECASE,
        )
        for alias in aliases
        if alias
    ):
        raise ValueError("Export query does not identify the selected instrument")
    results = {}
    for entry in raw["results"][:200]:
        if not isinstance(entry, dict):
            continue
        source = label(entry.get("source"), 40)
        url = export_url(entry.get("url"), source)
        title = label(entry.get("title"), 500)
        if not url or not title:
            continue
        value = entry.get("published_at")
        try:
            if isinstance(value, str) and re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
            ):
                day = date.fromisoformat(value)
                earliest, latest = published_bounds(value)
            else:
                earliest = latest = timestamp(value)
                day = None
        except (ValueError, TypeError, OverflowError):
            continue
        if observed - timedelta(days=30) <= earliest and latest <= observed:
            host = urlsplit(url).hostname
            publisher = (
                host + " · Hacker News"
                if source == "hackernews" and host != "news.ycombinator.com"
                else source
            )
            results.setdefault(url, (url, title, publisher, latest, day))
    return sorted(results.values(), key=lambda item: (item[3], item[0]), reverse=True)[
        :MAX_ITEMS
    ]


def label(value, max_length):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        return None
    if any(ord(c) < 32 for c in value) or "<" in value or ">" in value:
        return None
    return value.strip()


def search_query(ticker, market):
    if market == "kr":
        phrase = KOREAN.get(ticker, ticker)
        return f'"{phrase}" when:30d', "ko", "KR", "KR:ko"
    if market == "us":
        phrase = ENGLISH.get(ticker)
        query = f'"{phrase}"' if phrase else f'"{ticker}" stock'
        return f"{query} when:30d", "en-US", "US", "US:en"
    raise ValueError("Unsupported issue market")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def fetch_feed(query, lang, country, edition):
    params = urlencode({"q": query, "hl": lang, "gl": country, "ceid": edition})
    req = Request(
        "https://news.google.com/rss/search?" + params,
        headers={"User-Agent": "GANT-V3/1.0 (market research RSS reader)"},
    )
    deadline = time.monotonic() + 12
    data = bytearray()
    with build_opener(NoRedirect()).open(req, timeout=5) as response:
        while len(data) <= MAX_FEED_BYTES:
            if time.monotonic() >= deadline:
                raise TimeoutError("Issue source timeout")
            block = response.read1(min(65536, MAX_FEED_BYTES + 1 - len(data)))
            if not block:
                break
            data.extend(block)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("Oversized issue feed")
    return bytes(data)


def parse_feed(payload, observed):
    if (
        len(payload) > MAX_FEED_BYTES
        or b"<!DOCTYPE" in payload.upper()
        or b"<!ENTITY" in payload.upper()
    ):
        raise ValueError("Unsupported issue feed")
    channel = ElementTree.fromstring(payload).find("channel")
    if channel is None:
        raise ValueError("Missing RSS channel")
    result = {}
    for row in channel.findall("item")[:200]:
        publisher = label(row.findtext("source"), 160)
        title = label(row.findtext("title"), 500)
        url = article_url(row.findtext("link"))
        if not publisher or not title or not url:
            continue
        try:
            published = timestamp(parsedate_to_datetime(row.findtext("pubDate") or ""))
        except (ValueError, TypeError, OverflowError):
            continue
        if observed - timedelta(days=30) <= published <= observed:
            title = title.removesuffix(" - " + publisher).strip()
            if title:
                result.setdefault(url, (url, title, publisher, published, None))
    return sorted(result.values(), key=lambda item: (item[3], item[0]), reverse=True)[
        :MAX_ITEMS
    ]


def record_observation(conn, ticker, source, query, observed, status, rows):
    """Insert the run and its newly seen URLs in the caller's transaction."""
    run = conn.execute(
        """INSERT INTO v3_issue_runs(ticker,source,query,collected_at,status,item_count)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,status,item_count,collected_at""",
        (ticker, source, query, observed, status, len(rows)),
    ).fetchone()
    if rows:
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO v3_issues(ticker,url,title,publisher,published_at,published_day,first_seen_at,run_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [(ticker, *row, observed, run["id"]) for row in rows],
            )
    return run


def collect_one(store, entry, fetch=fetch_feed, export_path=None):
    ticker = entry["ticker"]
    source = EXPORT if export_path else SOURCE
    query = (ticker,)
    try:
        query = search_query(ticker, entry["market"])
        if export_path:
            with export_path.open("rb") as export:
                payload = export.read(MAX_FEED_BYTES + 1)
        else:
            payload = fetch(*query)
        with store._connect() as conn:
            observed = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
            rows = (
                parse_export(payload, observed, ticker)
                if export_path
                else parse_feed(payload, observed)
            )
            status = "available" if rows else "empty"
            stored_query = json.loads(payload)["query"] if export_path else query[0]
            record_observation(conn, ticker, source, stored_query, observed, status, rows)
        return status
    except Exception:  # noqa: BLE001 -- isolate each instrument and redact transport errors
        try:
            with store._connect() as conn:
                conn.execute(
                    """INSERT INTO v3_issue_runs(ticker,source,query,status,item_count)
                    VALUES (%s,%s,%s,'failed',0)""",
                    (ticker, source, query[0]),
                )
        except Exception:  # noqa: BLE001 -- storage may also be unavailable
            return "storage_failed"
        return "failed"


def case_issues(conn, ticker, as_of, *, source=None):
    if source not in (None, SOURCE, EXPORT):
        raise ValueError("Unknown archive source")
    cutoff = timestamp(as_of)
    since = cutoff - timedelta(days=30)
    run = conn.execute(
        """SELECT source,status,collected_at FROM v3_issue_runs WHERE ticker=%s
        AND (%s::text IS NULL OR source=%s)
        AND collected_at>=%s AND collected_at<%s ORDER BY collected_at DESC,id DESC LIMIT 1""",
        (ticker, source, source, since, cutoff),
    ).fetchone()
    rows = conn.execute(
        """SELECT i.title,i.publisher,i.url,i.published_at,i.published_day,i.first_seen_at,r.source
        FROM v3_issues i JOIN v3_issue_runs r ON r.id=i.run_id WHERE i.ticker=%s
        AND (%s::text IS NULL OR r.source=%s) AND r.collected_at < %s
        AND i.published_at >= %s
        AND (i.published_day IS NULL OR (i.published_day::timestamp AT TIME ZONE 'UTC') - interval '14 hours' >= %s)
        AND i.published_at < %s AND i.first_seen_at < %s
        ORDER BY i.published_at DESC,i.url LIMIT %s""",
        (ticker, source, source, cutoff, since, since, cutoff, cutoff, MAX_ITEMS),
    ).fetchall()
    status = run["status"] if run else "uncollected"
    if status != "failed":
        status = "available" if rows else ("empty" if run else "uncollected")
    return public_issues(
        {
            "status": status,
            "source": run["source"] if run else (source or SOURCE),
            "as_of": cutoff,
            "collected_at": run["collected_at"] if run else None,
            "items": rows,
        }
    )


def public_issues(raw):
    """Closed public projection, also safe to apply to JSON received over loopback."""
    if not isinstance(raw, dict):
        return None
    try:
        cutoff = timestamp(raw.get("as_of"))
        collected = timestamp(raw["collected_at"]) if raw.get("collected_at") else None
    except (ValueError, TypeError):
        return None
    status = raw.get("status")
    if (
        status not in ("available", "empty", "uncollected", "failed")
        or raw.get("source") not in (SOURCE, EXPORT)
        or collected
        and collected >= cutoff
    ):
        return None
    items = []
    supplied = raw.get("items")
    if not isinstance(supplied, list):
        return None
    for row in supplied[:MAX_ITEMS]:
        if not isinstance(row, dict):
            continue
        source = row.get("source")
        url = (
            article_url(row.get("url"))
            if source == SOURCE
            else export_url(row.get("url"), row.get("publisher"))
        )
        title, publisher = (
            label(row.get("title"), 500),
            label(row.get("publisher"), 160),
        )
        try:
            pub, seen = (
                timestamp(row.get("published_at")),
                timestamp(row.get("first_seen_at")),
            )
        except (TypeError, ValueError):
            continue
        if (
            url
            and source == EXPORT
            and isinstance(publisher, str)
            and publisher.endswith(" · Hacker News")
        ):
            publisher = urlsplit(url).hostname + " · Hacker News"
        day = row.get("published_day")
        if day is not None:
            day = str(day)
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
                    continue
                earliest, upper = published_bounds(day)
                if (
                    source != EXPORT
                    or earliest < cutoff - timedelta(days=30)
                    or pub != upper
                ):
                    continue
            except (ValueError, OverflowError):
                continue
        if (
            url
            and title
            and publisher
            and source in (SOURCE, EXPORT)
            and cutoff - timedelta(days=30) <= pub <= seen < cutoff
        ):
            items.append(
                {
                    "url": url,
                    "title": title,
                    "publisher": publisher,
                    "source": source,
                    "published_day": str(row["published_day"])
                    if row.get("published_day")
                    else None,
                    "published_precision": "day"
                    if row.get("published_day")
                    else "timestamp",
                    "published_at": pub.isoformat(),
                    "first_seen_at": seen.isoformat(),
                }
            )
    return {
        "status": status,
        "source": raw["source"],
        "as_of": cutoff.isoformat(),
        "collected_at": collected.isoformat() if collected else None,
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--ticker", help="Collect only this watchlist ticker")
    parser.add_argument(
        "--import-agent-export",
        type=Path,
        help="Import a last30days v1 agent export for --ticker",
    )
    args = parser.parse_args()
    if args.import_agent_export and not args.ticker:
        parser.error("--import-agent-export requires --ticker")
    from dotenv import load_dotenv

    from .app import settings
    from .store import Store

    if not args.env_file.is_file():
        parser.error("Missing v3 environment file")
    from dotenv import dotenv_values

    if not dotenv_values(args.env_file, interpolate=False).get("FORECAST_LAB_DSN"):
        parser.error("Missing FORECAST_LAB_DSN in v3 environment file")
    load_dotenv(args.env_file, override=True, interpolate=False)
    from psycopg.conninfo import conninfo_to_dict

    dsn = settings()
    if conninfo_to_dict(dsn).get("port") != "55436":
        parser.error("The issue collector requires the isolated v3 port 55436")
    store = Store(dsn)
    store.init()
    watch = store.list_tickers()
    if args.ticker:
        watch = [
            entry for entry in watch if entry["ticker"] == args.ticker.strip().upper()
        ]
        if not watch:
            parser.error("Ticker is not in this watchlist")
    with ThreadPoolExecutor(max_workers=3) as pool:
        statuses = list(
            pool.map(
                lambda entry: collect_one(
                    store, entry, export_path=args.import_agent_export
                ),
                watch,
            )
        )
    print(
        json.dumps(
            dict(zip([entry["ticker"] for entry in watch], statuses, strict=True))
        )
    )
    return int(any(status in ("failed", "storage_failed") for status in statuses))


if __name__ == "__main__":
    raise SystemExit(main())
