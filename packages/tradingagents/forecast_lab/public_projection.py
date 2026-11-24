"""Public research DTOs. Never serialize an upstream dictionary or pass through narrative."""

import json
import math
import re
from datetime import UTC, date, datetime
from pathlib import Path

METHODS = {"baseline", "single", "debate", "memory", "memory_sector"}
# Reviewed instrument names. Console display aliases are editable and may contain private text.
NAMES = json.loads(
    (Path(__file__).with_name("web") / "instrument-names.json").read_text(
        encoding="utf8"
    )
)
DECISIONS = {"BUY": "매수", "SELL": "매도", "HOLD": "관망"}


def number(v, low=-1e18, high=1e18):
    return (
        v if type(v) in (float, int) and math.isfinite(v) and low <= v <= high else None
    )


def count(v):
    return v if type(v) is int and 0 <= v <= 2**53 - 1 else None


def instant(v):
    try:
        parsed = datetime.fromisoformat(v)
        return parsed.isoformat() if parsed.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def instrument(row):
    ticker = row.get("ticker")
    if not isinstance(ticker, str) or not re.fullmatch(
        r"[A-Z0-9][A-Z0-9.-]{0,15}", ticker
    ):
        return None
    return {"ticker": ticker, "name": NAMES.get(ticker, ticker)}


def public_case(row):
    if not isinstance(row, dict) or row.get("status") not in ("awaiting", "matured"):
        return None
    symbol = instrument(row)
    if not symbol or not count(row.get("id")) or row.get("market") not in ("us", "kr"):
        return None
    try:
        session = date.fromisoformat(row["data_session"]).isoformat()
    except (TypeError, KeyError, ValueError):
        return None
    entry, exit_at = (
        instant(row.get("entry_open_at")),
        instant(row.get("exit_close_at")),
    )
    if not entry or not exit_at:
        return None
    return {
        **symbol,
        "id": row["id"],
        "market": row["market"],
        "status": row["status"],
        "data_session": session,
        "entry_open_at": entry,
        "exit_close_at": exit_at,
    }


def public_detail(raw, summary):
    if not isinstance(raw, dict) or public_case(raw) != summary:
        return None
    forecasts = []
    for a in raw.get("arms", []):
        if (
            not isinstance(a, dict)
            or a.get("status") != "published"
            or a.get("method") not in METHODS
        ):
            continue
        prob, when = number(a.get("probability"), 0, 1), instant(a.get("published_at"))
        if (
            prob is not None
            and when
            and datetime.fromisoformat(when) <= datetime.now(UTC)
            and datetime.fromisoformat(when)
            < datetime.fromisoformat(summary["entry_open_at"])
        ):
            forecasts.append(
                {
                    "method": a["method"],
                    "probability": prob,
                    "published_at": when,
                    "brier": number(a.get("brier"), 0, 1),
                }
            )
    if not forecasts:
        return None
    o = raw.get("outcome") or {}
    outcome = None
    if (
        summary["status"] == "matured"
        and o.get("status") == "scored"
        and o.get("actual") in (0, 1)
    ):
        entry, close = number(o.get("entry_open"), 0), number(o.get("exit_close"), 0)
        if entry and close:
            outcome = {
                "actual": int(o["actual"]),
                "entry_open": entry,
                "exit_close": close,
            }
    return {
        **summary,
        "forecasts": forecasts,
        "outcome": outcome,
        "summary": f"{summary['name']}의 다음 거래일 시가부터 다섯 번째 거래일 종가까지의 상승 확률을 비교합니다.",
    }


def public_stats(raw):
    comparisons = []
    for pair in raw.get("comparisons", []):
        if (
            not isinstance(pair, dict)
            or pair.get("control") not in METHODS
            or pair.get("treated") not in METHODS
        ):
            continue
        version = pair.get("experiment_version")
        if not isinstance(version, str) or not re.fullmatch(
            r"direction-5s-v[0-9]{1,3}", version
        ):
            continue
        result = {
            key: number(pair.get(key), low, 1)
            for key, low in (
                ("control_brier", 0),
                ("treated_brier", 0),
                ("improvement", -1),
            )
        }
        if None not in result.values() and count(pair.get("n")):
            comparisons.append(
                {
                    **result,
                    "control": pair["control"],
                    "treated": pair["treated"],
                    "experiment_version": version,
                    "n": pair["n"],
                }
            )
    source = raw.get("sector_coverage") or {}
    coverage = {
        k: count(source.get(k))
        for k in (
            "eligible_cases",
            "published",
            "scored",
            "same_memory",
            "no_eligible_sector_memory",
        )
    }
    return {"comparisons": comparisons, "sector_coverage": coverage}


# Only extract an indicator when its label, value, units and statement boundary match.
# No raw prose, names, reasoning, user data, operations or quoted strings leave this module.
NUM = r"([−–+\-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,10})(?:\.[0-9]{1,4})?)"
END = r"(?=으로|로|이며|입니다|이었다|였다|에 마감|\([+−–\-0-9]|[.,;\s]|$)"
RULES = (
    (
        "market_report",
        "종가",
        r"종가(?:는|가|:)? *" + NUM + r" *(원|달러)" + END,
        "{0}{1}",
    ),
    ("market_report", "종가", r"종가(?:는|가|:)? *\$" + NUM + END, "{0}달러"),
    ("market_report", "종가", r"\$" + NUM + r"에 마감(?:해|했|한)", "{0}달러"),
    (
        "market_report",
        "거래량",
        r"거래량(?:은|이|:) *" + NUM + r" *(억 주|만 주|주)" + END,
        "{0}{1}",
    ),
    (
        "market_report",
        "RSI 변화",
        r"RSI(?:는|가|:) *" + NUM + r" *(?:→|에서) *" + NUM + r"(?=으로|로|[,;\s]|$)",
        "{0} → {1}",
    ),
    ("market_report", "ATR", r"ATR(?:은|이|:) *\$" + NUM + END, "{0}달러"),
    ("market_report", "50일 이동평균", r"50일선\(\$" + NUM + r"\)", "{0}달러"),
    ("market_report", "200일 이동평균", r"200일선\(\$" + NUM + r"\)", "{0}달러"),
    (
        "fundamentals_report",
        "영업이익률",
        r"영업이익률(?:은|이|:) *" + NUM + r" *(%)(?=로|이며|입니다|였다|[.,]|$)",
        "{0}{1}",
    ),
    (
        "fundamentals_report",
        "선행 PER",
        r"선행 PER(?:은|이|:)? *" + NUM + r" *(배)(?=로|는|이며|입니다|였다|[.,\s]|$)",
        "{0}{1}",
    ),
)


def reported_facts(row):
    facts = {}
    for field, label, pattern, template in RULES:
        prose = row.get(field)
        if not isinstance(prose, str) or label in facts:
            continue
        for match in re.finditer(
            r"(?<![가-힣A-Za-z0-9_])" + pattern, prose[:16000].replace("**", "")
        ):
            # A valuation target, conditional instruction or previous closing price is not a current quote.
            previous = match.string[max(0, match.start() - 24) : match.start()]
            if re.search(
                r"(?:예상|목표|예측|추정|가정|포트폴리오|계좌|매수|매도|주문|직전|이전)\s*$",
                previous,
            ):
                continue
            remainder = match.string[match.end() : match.end() + 35]
            if re.match(
                r"\s*(?:[~∼→]|에서|라면|이면|일 경우|이상|이하|돌파|미만|초과)",
                remainder,
            ):
                continue
            values = match.groups()
            if label == "RSI 변화" and any(
                not 0
                <= float(x.replace(",", "").replace("−", "-").replace("–", "-"))
                <= 100
                for x in values
            ):
                continue
            facts[label] = template.format(*values)
            break
    return [f"{label} {value}" for label, value in facts.items()]


def public_report(raw):
    if not isinstance(raw, dict) or not count(raw.get("id")):
        return None
    symbol = instrument(raw)
    published = instant(raw.get("created_at"))
    if (
        not published
        or datetime.fromisoformat(published) > datetime.now(UTC)
        or not symbol
    ):
        return None
    decision = raw.get("stored_decision_position", raw.get("decision_position"))
    decision = decision if isinstance(decision, str) and decision in DECISIONS else None
    market = "kr" if symbol["ticker"].endswith((".KS", ".KQ")) else "us"
    if symbol["ticker"].endswith("-USD"):
        market = "crypto"
    summary = (
        f"{symbol['name']}에 대한 분석 판단은 {DECISIONS[decision]}입니다."
        if decision
        else f"{symbol['name']}의 분석 리포트입니다."
    )
    sections = [{"title": "분석 판단", "text": summary}]
    facts = reported_facts(raw)
    if facts:
        sections.append({"title": "리포트에 기록된 지표", "text": " · ".join(facts)})
    return {
        **symbol,
        "id": raw["id"],
        "market": market,
        "created_at": published,
        "decision": decision,
        "summary": summary,
        "sections": sections,
    }
