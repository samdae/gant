"""Collect dated public issuer research with the provisioned last30days engine."""

import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .bounded_process import bounded_run
from .issue_collector import ENGLISH, KOREAN

SOURCES = ("hackernews", "youtube")
TIMEOUT_SECONDS = 70
SUCCESS_STATES = {"ok", "no-results"}

# The research database uses exchange-qualified Korean symbols. English issuer
# names make the same instruments discoverable in Hacker News story titles.
ALTERNATES = {
    "000660.KS": ("SK Hynix", "하이닉스"),
    "005380.KS": ("Hyundai Motor", "현대차"),
    "005930.KS": ("Samsung Electronics", "삼성전자"),
    "009830.KS": ("Hanwha Solutions",),
    "012450.KS": ("Hanwha Aerospace", "한화에어로"),
    "034020.KS": ("Doosan Enerbility",),
    "036460.KS": ("Korea Gas Corporation", "KOGAS"),
    "069500.KS": ("KODEX 200", "코덱스200"),
    "096770.KS": ("SK Innovation",),
    "267260.KS": ("HD Hyundai Electric",),
    "316140.KS": ("Woori Financial Group", "우리금융", "우리은행"),
    "BTC-USD": ("Bitcoin", "BTC"),
    "GOOGL": ("Alphabet", "Google"),
    "KO": ("Coca Cola",),
    "SCHP": ("Schwab U.S. TIPS",),
    "SPY": ("SPDR S&P 500",),
}
MARKET_QUERIES = {
    "BTC-USD": "Bitcoin market price and ETF flows",
    "GLD": "GLD SPDR Gold Shares price and gold ETF flows",
    "SLV": "SLV iShares Silver Trust price and silver ETF flows",
    "SCHP": "SCHP TIPS ETF inflation and real bond yields",
    "SPY": "SPY S&P 500 ETF market performance",
    "069500.KS": "KODEX 200 ETF 지수 수급과 수익률",
}
BUSINESS_TERMS = re.compile(
    r"\b(stock|shares?|invest\w*|earnings?|sales|revenue|margin|profit\w*|guidance|"
    r"financial|quarter\w*|dividend|portfolio|market|prices?|valuation|debt|inflation|"
    r"etf|tariffs?|trade|supply|demand|production|exports?|shipments?|capex|funding|"
    r"capacity|buybacks?|launch\w*|regulat\w*|antitrust|ceo|merger|layoffs?|lawsuit|"
    r"flows?|yields?|outlook|index|holdings?)\b"
    r"|주가|주식|투자|실적|공시|영업이익|매출|배당|밸류|증권|상장|자사주|수출|"
    r"양산|출하|계약|공급|경영|전망|금리|물가|환율|목표가|수익률|지수|수급",
    re.IGNORECASE,
)
PROMOTION = re.compile(
    r"guaranteed (?:profit|return)|get rich|next 100x|"
    r"세력의 속셈|몰래 줍|무조건.{0,8}(?:매수|상승)|원금 보장|무료.{0,5}종목 추천|"
    r"(?:문자|카톡|오픈채팅).{0,8}(?:참여|신청|문의)",
    re.IGNORECASE,
)


class EngineFailure(RuntimeError):
    pass


def has_source_failure(export):
    states = export.get("source_status") or {}
    return any(states.get(source) not in SUCCESS_STATES for source in SOURCES)


def _issuer(ticker, market):
    if market not in ("kr", "us") or not re.fullmatch(
        r"[A-Z0-9][A-Z0-9.\-]{0,15}", ticker
    ):
        raise EngineFailure("Invalid research instrument")
    names = KOREAN if market == "kr" else ENGLISH
    return names.get(ticker, ticker)


def _relevant(title, ticker, issuer):
    if (
        not isinstance(title, str)
        or not BUSINESS_TERMS.search(title)
        or PROMOTION.search(title)
    ):
        return False
    aliases = (issuer, *ALTERNATES.get(ticker, ()))
    for alias in aliases:
        if alias == ticker:
            continue
        if re.search(
            r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", title, re.I
        ):
            return True
    # Bare English words such as "spy" and "slv" must not stand in for an ETF.
    return bool(
        re.search(r"(?<![A-Za-z0-9])" + re.escape(ticker) + r"(?![A-Za-z0-9])", title)
    )


def _environment(folder, scripts):
    env = {
        k: os.environ[k]
        for k in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT")
        if k in os.environ
    }
    env.update(
        {
            k: str(folder)
            for k in ("USERPROFILE", "HOME", "LOCALAPPDATA", "APPDATA", "TMP", "TEMP")
        }
    )
    env.update(
        PATH=os.pathsep.join((str(scripts), str(Path(env["SystemRoot"]) / "System32"))),
        LAST30DAYS_CONFIG_DIR=str(folder),
        LAST30DAYS_SKIP_KEYCHAIN="1",
        LAST30DAYS_MEMORY_DIR="",
        FROM_BROWSER="off",
        LAST30DAYS_YT_SUB_LANGS="ko,en",
        LAST30DAYS_YT_TRANSCRIPT_FAST_ATTEMPTS="1",
        LAST30DAYS_YT_TRANSCRIPT_FAST_TIMEOUT="3",
        LAST30DAYS_YT_SEARCH_TIMEOUT="30",
    )
    return env


def _collect_source(source, ticker, market, issuer, programs):
    cli = programs / "last30days/skills/last30days/scripts/last30days.py"
    scripts = programs / "last30days-python/Scripts"
    python = scripts / "python.exe"
    if (
        not cli.is_file()
        or not python.is_file()
        or (source == "youtube" and not (scripts / "yt-dlp.exe").is_file())
    ):
        raise EngineFailure("Scheduled source runtime is unavailable")
    query = issuer
    if source == "hackernews" and ticker in ALTERNATES:
        query = ALTERNATES[ticker][0]
    elif source == "youtube":
        query = MARKET_QUERIES.get(ticker) or (
            issuer + (" 실적 발표" if market == "kr" else " earnings results")
        )
    plan = {
        "intent": "breaking_news",
        "freshness_mode": "strict_recent",
        "cluster_mode": "story",
        "subqueries": [
            {
                "label": "issuer",
                "search_query": query,
                "ranking_query": query,
                "sources": [source],
                "weight": 1.0,
            }
        ],
    }
    cmd = [
        str(python),
        "-I",
        "-B",
        str(cli),
        issuer,
        "--plan",
        "-",
        "--research-only",
        "--no-research-persistence",
        "--no-browser-cookies",
        "--save-dir=",
        "--days",
        "30",
        "--search",
        source,
        "--quick",
        "--emit=json",
        "--json-profile=agent",
    ]
    with tempfile.TemporaryDirectory(prefix="gant-research-") as folder:
        raw = bounded_run(
            cmd,
            json.dumps(plan),
            TIMEOUT_SECONDS,
            source,
            env=_environment(folder, scripts),
            cwd=folder,
        )
    if len(raw) > 2_000_000:
        raise EngineFailure("Oversized research export")
    report = json.loads(raw)
    if (
        not isinstance(report, dict)
        or not re.fullmatch(r"1\.\d+", str(report.get("schema_version")))
        or report.get("window_days") != 30
        or report.get("query") != issuer
        or not isinstance(report.get("source_status"), dict)
        or not isinstance(report.get("results"), list)
    ):
        raise EngineFailure("Unexpected research export")
    status = report["source_status"].get(source)
    if not isinstance(status, str):
        raise EngineFailure("Missing source outcome")
    rows = [
        row
        for row in report["results"]
        if isinstance(row, dict)
        and row.get("source") == source
        and _relevant(row.get("title"), ticker, issuer)
    ]
    return status, rows


def run_export(ticker, market):
    """Keep good sources even when an independent lookup times out or fails."""
    issuer = _issuer(ticker, market)
    programs = Path(os.environ["LOCALAPPDATA"]) / "TradingAgentsV3/integrations"
    # Only the fields consumed by parse_export cross the service boundary.
    report = {
        "schema_version": "1.0",
        "query": issuer,
        "window_days": 30,
        "source_status": {},
        "results": [],
    }
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        pending = {
            source: pool.submit(
                _collect_source, source, ticker, market, issuer, programs
            )
            for source in SOURCES
        }
        for source, result in pending.items():
            try:
                state, rows = result.result()
            except TimeoutError:
                state, rows = "timeout", []
            except (RuntimeError, OSError, ValueError):
                state, rows = "error", []
            report["source_status"][source] = state
            report["results"].extend(
                {
                    key: row.get(key)
                    for key in ("source", "url", "title", "published_at")
                }
                for row in rows
            )
    return report
