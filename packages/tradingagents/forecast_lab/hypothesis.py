"""Predeclared, falsifiable price-breakout study. Never used as a directional label."""

import math
import re
from datetime import date, datetime

VERSION = "price-breakout-v1"
ORIGIN = "predeclared_rule"
RULES = (("breakout", "exit_close", "gt"), ("review", "min_close", "lt"))


def price(x):
    return type(x) in (int, float) and math.isfinite(x) and x > 0


def freeze(snapshot, reference_sessions):
    """Create a card using only five *completed* exchange sessions."""
    expected_currency = {"us": "USD", "kr": "KRW"}.get(snapshot.get("market"))
    if not expected_currency or snapshot.get("currency") != expected_currency:
        raise ValueError("Hypothesis currency differs from listing market")
    days = list(reference_sessions)
    rows = snapshot["bars"][-5:]
    if (
        len(days) != 5
        or days != sorted(set(days))
        or days[-1] != snapshot["data_session"]
        or [r["date"] for r in rows] != days
        or len({r["date"] for r in snapshot["bars"]}) != len(snapshot["bars"])
        or any(r["date"] > days[-1] for r in snapshot["bars"])
        or any(
            not all(price(r.get(k)) for k in ("open", "high", "low", "close"))
            or not r["low"]
            <= min(r["open"], r["close"])
            <= max(r["open"], r["close"])
            <= r["high"]
            or r.get("split") != 0
            or r.get("adjustment_uncertain")
            for r in rows
        )
    ):
        raise ValueError("Hypothesis requires clean contiguous historical OHLC")
    thresholds = [max(r["high"] for r in rows), min(r["low"] for r in rows)]
    return {
        "version": VERSION,
        "origin": ORIGIN,
        "ticker": snapshot["ticker"],
        "currency": expected_currency,
        "source": snapshot["source"],
        "data_session": days[-1],
        "observed_at": snapshot["observed_at"],
        "reference_window_start": days[0],
        "reference_close": rows[-1]["close"],
        "window_start": snapshot["sessions"][0],
        "window_end": snapshot["sessions"][-1],
        "conditions": [
            {"id": key, "metric": metric, "operator": op, "threshold": threshold}
            for (key, metric, op), threshold in zip(RULES, thresholds, strict=True)
        ],
    }


def evaluate(card, bars):
    """Evaluate the two frozen inequalities only after all five session closes."""
    last = bars[-1]
    lowest = min(bars, key=lambda r: r["close"])  # report earliest session on a tie
    results = []
    for condition, observation in zip(card["conditions"], (last, lowest), strict=True):
        value = observation["close"]
        met = (
            value > condition["threshold"]
            if condition["id"] == "breakout"
            else value < condition["threshold"]
        )
        results.append(
            {
                "id": condition["id"],
                "status": "met" if met else "not_met",
                "observed_value": value,
                "observed_session": observation["date"],
            }
        )
    return results


def detail(snapshot, outcome):
    card = snapshot.get("hypothesis")
    if not card:
        return None
    scored = outcome and outcome.get("status") == "scored"
    results = (
        ((outcome.get("evidence") or {}).get("hypothesis_results") or [])
        if scored
        else []
    )
    fallback = "unavailable" if outcome else "pending"
    by_id = {r["id"]: r for r in results}
    conditions = []
    for condition in card["conditions"]:
        result = by_id.get(
            condition["id"],
            {"status": fallback, "observed_value": None, "observed_session": None},
        )
        conditions.append({**condition, **result})
    return {**card, "conditions": conditions}


def public_hypothesis(raw):
    """Project original price facts and finite rule outputs, without private snapshot prose."""
    if (
        not isinstance(raw, dict)
        or raw.get("version") != VERSION
        or raw.get("origin") != ORIGIN
    ):
        return None
    try:
        if (
            not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,15}", raw["ticker"])
            or raw["currency"] not in ("USD", "KRW")
            or not price(raw["reference_close"])
        ):
            return None
        out = {
            k: date.fromisoformat(raw[k]).isoformat()
            for k in (
                "data_session",
                "reference_window_start",
                "window_start",
                "window_end",
            )
        }
        observed = datetime.fromisoformat(raw["observed_at"])
        if observed.utcoffset() is None:
            return None
        source = raw["source"]
        out.update(
            version=VERSION,
            origin=ORIGIN,
            ticker=raw["ticker"],
            currency=raw["currency"],
            reference_close=raw["reference_close"],
            observed_at=observed.isoformat(),
            source="NAVER"
            if source.startswith("NAVER Finance")
            else "Yahoo"
            if source.startswith("Yahoo Finance")
            else None,
        )
        conditions = []
        for rule, c in zip(RULES, raw["conditions"], strict=True):
            if tuple(
                c.get(k) for k in ("id", "metric", "operator")
            ) != rule or not price(c["threshold"]):
                return None
            status = c["status"]
            if status not in ("pending", "met", "not_met", "unavailable"):
                return None
            value, day = None, None
            if status in ("met", "not_met"):
                value = c["observed_value"]
                day = date.fromisoformat(c["observed_session"]).isoformat()
                if (
                    not price(value)
                    or not out["window_start"] <= day <= out["window_end"]
                ):
                    return None
            conditions.append(
                {
                    "id": rule[0],
                    "metric": rule[1],
                    "operator": rule[2],
                    "threshold": c["threshold"],
                    "status": status,
                    "observed_value": value,
                    "observed_session": day,
                }
            )
        return {**out, "conditions": conditions}
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
