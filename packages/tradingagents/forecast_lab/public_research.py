"""Explicit DTOs for the integrated research viewer; no upstream headers or traces."""

import re
from datetime import UTC, date, datetime

from .public_projection import case_evidence
from .classification import EQUITIES, FUNDS, VERSION
from .public_projection import METHODS, count, instant, instrument, number, public_case


def choice(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def model(value):
    return (
        value
        if isinstance(value, str)
        and re.fullmatch(
            r"(?:deterministic|gpt-[a-z0-9.-]{1,40}|o[134](?:-[a-z0-9.-]{1,32})?)",
            value,
        )
        else None
    )


def version(value):
    return choice(
        value,
        {
            "direction-5s-v1",
            "direction-5s-v2",
            "laplace-5s-v1",
            "frozen-probability-v1",
            "original-eight-nodes-1round-risk-forecast-v1",
        },
    )


def group(raw):
    if not isinstance(raw, dict) or raw.get("version") != VERSION:
        return None
    return {
        "version": VERSION,
        "asset_class": choice(raw.get("asset_class"), {"equity", "etf", "unknown"}),
        "sector": choice(raw.get("sector"), {v[0] for v in EQUITIES.values()}),
        "industry": choice(raw.get("industry"), {v[1] for v in EQUITIES.values()}),
        "exposure": choice(raw.get("exposure"), FUNDS.values()),
    }


def research_status(raw):
    tickers = []
    for row in raw.get("tickers", []):
        symbol = instrument(row)
        if symbol and row.get("market") in ("us", "kr"):
            tickers.append(
                {
                    **symbol,
                    "market": row["market"],
                    "classification": group(row.get("classification")),
                }
            )
    progress = raw.get("progress") or {}
    return {
        "tickers": tickers,
        "scheduler_enabled": raw.get("scheduler_enabled") is True,
        "reference_enabled": raw.get("reference_enabled") is True,
        "progress": {
            "phase": choice(
                progress.get("phase"), ("idle", "maturing", "issuing", "busy", "failed")
            ),
            "started_at": instant(progress.get("started_at")),
            "finished_at": instant(progress.get("finished_at")),
        },
    }


def case_summary(raw):
    if not isinstance(raw, dict) or raw.get("status") not in (
        "pending",
        "awaiting",
        "matured",
        "excluded",
    ):
        return None
    # The SQL list predicate checks actual publication independent of case state.
    base = public_case({**raw, "status": "awaiting"})
    if base:
        return {
            **base,
            "status": raw["status"],
            "experiment_version": version(raw.get("experiment_version")),
        }


def iso_day(value):
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return None


def prices(rows, cutoff):
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows[-100:]:
        if not isinstance(row, dict):
            continue
        day = iso_day(row.get("date"))
        if day and day <= cutoff and number(row.get("close"), 0) is not None:
            result.append(
                {
                    "date": day,
                    "volume": count(row.get("volume")),
                    **{
                        k: number(row.get(k), 0)
                        for k in ("open", "high", "low", "close")
                    },
                }
            )
    return result


def features(raw):
    return {
        key: number(raw.get(key))
        for key in (
            "trend_20d",
            "volatility_20d",
            "relative_trend_20d",
            "benchmark_trend_20d",
            "benchmark_volatility_20d",
        )
    }


def memory_summary(raw):
    from .console_public_reads import public_narrative

    if (
        not isinstance(raw, dict)
        or not instrument(raw)
        or raw.get("actual") not in (0, 1)
    ):
        return None
    return {
        **instrument(raw),
        "market": choice(raw.get("market"), ("kr", "us")),
        "data_session": iso_day(raw.get("data_session")),
        "created_at": instant(raw.get("created_at")),
        "probability": number(raw.get("probability"), 0, 1),
        "actual": int(raw["actual"]),
        "entry_open": number(raw.get("entry_open"), 0),
        "exit_close": number(raw.get("exit_close"), 0),
        "brier": number(raw.get("brier"), 0, 1),
        "features": features(raw.get("features") or {}),
        "rationale": public_narrative(raw.get("rationale")),
    }


def selection_summary(arm):
    raw = (arm.get("audit") or {}).get("sector_selection_v1") or {}
    basis = choice(raw.get("basis"), ("same_ticker", "equity_peer", "etf_exposure"))
    if not basis:
        return {}
    return {
        "sector_selection_v1": {
            "basis": basis,
            "peer_reference": choice(
                raw.get("peer_reference"), ("market_benchmark", "watchlist_median")
            ),
            **{
                k: (instrument({"ticker": raw.get(k)}) or {}).get("ticker")
                for k in ("selected_ticker", "peer_ticker")
            },
            **{
                k: number(raw.get(k))
                for k in ("source_window_return", "peer_window_return")
            },
            "reference_count": count(raw.get("reference_count")),
        }
    }


def research_detail(raw):
    from .console_public_reads import public_narrative

    summary = case_summary(raw)
    if not summary:
        return None
    arms = []
    for arm in raw.get("arms", []):
        when = instant(arm.get("published_at"))
        probability = number(arm.get("probability"), 0, 1)
        if (
            arm.get("status") != "published"
            or arm.get("method") not in METHODS
            or not when
            or probability is None
            or datetime.fromisoformat(when) > datetime.now(UTC)
            or datetime.fromisoformat(when)
            >= datetime.fromisoformat(summary["entry_open_at"])
        ):
            continue
        arms.append(
            {
                "method": arm["method"],
                "status": "published",
                "probability": probability,
                "published_at": when,
                "brier": number(arm.get("brier"), 0, 1),
                "model": model(arm.get("model")),
                "rationale": public_narrative(arm.get("rationale")),
            }
        )
    if not arms:
        return None
    published = {arm["method"] for arm in arms}
    for arm in raw.get("arms", []):
        if (
            arm.get("method") == "memory_sector"
            and arm.get("status") == "published"
            and "memory_sector" in published
        ):
            next(a for a in arms if a["method"] == "memory_sector")["audit"] = (
                selection_summary(arm)
            )
        if arm.get("status") == "skipped" and arm.get("method") in (
            "memory",
            "memory_sector",
        ):
            error = choice(
                arm.get("error"),
                (
                    "same_memory",
                    "no_eligible_sector_memory",
                    "no eligible matured memory",
                ),
            )
            if error:
                arms.append(
                    {"method": arm["method"], "status": "skipped", "error": error}
                )
    s = raw.get("snapshot") or {}
    source = s.get("source") or ""
    day = summary["data_session"]
    b = s.get("benchmark") or {}
    snapshot = {
        "source": next(
            (
                name
                for name in ("NAVER", "Yahoo")
                if isinstance(source, str) and name in source
            ),
            None,
        ),
        "bars": prices(s.get("bars"), day),
        "features": features(s.get("features") or {}),
        "exchange": choice(s.get("exchange"), ("XKRX", "XNYS")),
        "currency": choice(s.get("currency"), ("USD", "KRW")),
        "instrument": choice(s.get("instrument"), ("EQUITY", "ETF")),
        "observed_at": instant(s.get("observed_at")),
        "entry_open_at": summary["entry_open_at"],
        "exit_close_at": summary["exit_close_at"],
        "retrieval_policy": choice(s.get("retrieval_policy"), ("sector-v1",)),
        "classification": group(s.get("classification")),
        "benchmark": {
            "ticker": choice(b.get("ticker"), ("069500.KS", "SPY")),
            "status": choice(b.get("status"), ("available", "unavailable")),
            "bars": prices(b.get("bars"), day),
        },
    }
    o = raw.get("outcome") or {}
    outcome = None
    if (
        summary["status"] == "matured"
        and o.get("status") == "scored"
        and o.get("actual") in (0, 1)
    ):
        evidence = o.get("evidence") or {}
        outcome = {
            "status": "scored",
            "actual": int(o["actual"]),
            "observed_at": instant(o.get("observed_at")),
            "entry_open": number(o.get("entry_open"), 0),
            "exit_close": number(o.get("exit_close"), 0),
            "evidence": {
                "bars": prices(
                    (evidence.get("evidence") or evidence).get("bars"),
                    summary["exit_close_at"][:10],
                )
            },
        }
    elif summary["status"] == "excluded":
        outcome = {"status": "excluded"}
    reference = raw.get("reference") or {}
    return {
        **summary,
        **case_evidence(raw),
        "snapshot": snapshot,
        "arms": arms,
        "outcome": outcome,
        "selected_memories": {
            k: memory_summary(v)
            for k, v in (raw.get("selected_memories") or {}).items()
            if k in published and k in ("memory", "memory_sector")
        },
        "selected_memory": memory_summary(raw.get("selected_memory"))
        if "memory" in published
        else None,
        "memory": memory_summary(raw.get("memory"))
        if outcome and outcome["status"] == "scored"
        else None,
        "reference": {
            "model": model(reference.get("model")),
            "probability": number(reference.get("probability"), 0, 1),
            "captured_at": instant(reference.get("captured_at")),
            "source_published_at": instant(reference.get("source_published_at")),
        }
        if reference
        else None,
    }


def research_stats(raw):
    def metric(row):
        return {
            **{
                k: count(row.get(k))
                for k in ("n", "distinct_tickers", "distinct_entry_dates")
            },
            **{
                k: number(row.get(k))
                for k in (
                    "lower",
                    "upper",
                    "mean_probability",
                    "observed_rate",
                    "control_brier",
                    "treated_brier",
                    "method_brier",
                    "source_brier",
                    "improvement",
                    "control_paper_return",
                    "treated_paper_return",
                )
            },
            **{
                k: choice(row.get(k), METHODS) for k in ("control", "treated", "method")
            },
            **{
                k: model(row.get(k))
                for k in ("model", "source_model", "control_model", "treated_model")
            },
            **{
                k: version(row.get(k))
                for k in (
                    "version",
                    "experiment_version",
                    "control_version",
                    "treated_version",
                )
            },
            "basis": choice(
                row.get("basis"), ("same_ticker", "equity_peer", "etf_exposure")
            ),
        }

    return {
        **{
            k: [metric(row) for row in raw.get(k, []) if isinstance(row, dict)]
            for k in (
                "comparisons",
                "reference_comparisons",
                "sector_by_basis",
                "calibration",
            )
        },
        "counts": {
            k: count((raw.get("counts") or {}).get(k))
            for k in ("pending", "awaiting", "matured", "excluded", "unpublished")
        },
        "sector_coverage": {
            k: count((raw.get("sector_coverage") or {}).get(k))
            for k in (
                "eligible_cases",
                "published",
                "scored",
                "same_memory",
                "no_eligible_sector_memory",
            )
        },
    }
