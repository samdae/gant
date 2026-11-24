"""Predeclared sector-v1 retrieval gates. All trend inputs are decimal returns."""

import math
import re
from collections import defaultdict
from statistics import median


# Each denominator is also a hard upper bound for that individual difference.
SCALES = {
    "trend_20d": 0.12,
    "volatility_20d": 0.015,
    "benchmark_trend_20d": 0.08,
    "benchmark_volatility_20d": 0.012,
    "relative_trend_20d": 0.10,
}


def token(value):
    return isinstance(value, str) and bool(
        re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}", value)
    )


def valid_classification(group):
    return (
        isinstance(group, dict)
        and token(group.get("version"))
        and group.get("asset_class") in ("equity", "etf", "unknown")
        and all(
            k in group
            and (
                group[k] is None
                or (
                    token(group[k])
                    and group[k] not in ("unknown", "none", "unclassified")
                )
            )
            for k in ("sector", "industry", "exposure")
        )
    )


def vector(features):
    if not isinstance(features, dict):
        return None
    keys = ("trend_20d", "volatility_20d")
    if any(
        type(features.get(k)) not in (int, float) or not math.isfinite(features[k])
        for k in keys
    ):
        return None
    if features["volatility_20d"] < 0:
        return None
    return {
        k: features[k]
        for k in SCALES
        if type(features.get(k)) in (int, float)
        and math.isfinite(features[k])
        and ("volatility" not in k or features[k] >= 0)
    }


def watchlist_reference(peers, source):
    tickers = {}
    for peer in peers:
        group = peer["classification"]
        features = vector(peer["features"])
        if (
            features
            and valid_classification(group)
            and group["asset_class"] == "equity"
            and group["version"] == source["version"]
            and group["sector"] is not None
            and group["sector"] != source["sector"]
        ):
            tickers[peer["ticker"]] = (group["sector"], features["trend_20d"])
    if len(tickers) >= 3 and len({sector for sector, _ in tickers.values()}) >= 2:
        return median(v for _, v in tickers.values()), len(tickers)
    return None, 0


def matched_group(source, target, key):
    return (
        valid_classification(source)
        and valid_classification(target)
        and source["version"] == target["version"]
        and source["asset_class"] == target["asset_class"]
        and source[key] is not None
        and source[key] == target[key]
    )


def window_return(row):
    entry, close = row.get("entry_open"), row.get("exit_close")
    if not all(
        type(v) in (float, int) and math.isfinite(v) and v > 0 for v in (entry, close)
    ):
        return None
    return close / entry - 1


def comparable_outcome(row, peer, source_features, peer_features):
    if row["entry_at"] != peer["entry_at"] or row["exit_at"] != peer["exit_at"]:
        return False
    source, observed = window_return(row), window_return(peer)
    if source is None or observed is None or source * observed <= 0:
        return False
    tolerance = math.sqrt(5) * min(
        source_features["volatility_20d"], peer_features["volatility_20d"]
    )
    return abs(source - observed) <= tolerance


def sector_candidates(case, rows, peers):
    target = vector(case["snapshot"].get("features"))
    group = case["snapshot"].get("classification")
    if target is None or not valid_classification(group):
        return []
    by_session = defaultdict(list)
    for peer in peers:
        by_session[peer["data_session"]].append(peer)
    candidates = []
    for row in rows:
        past = vector(row["features"])
        if past is None:
            continue
        distances = [
            abs(target[k] - past[k]) / scale
            for k, scale in SCALES.items()
            if k in target and k in past
        ]
        if max(distances) > 1:
            continue
        distance = sum(distances) / len(distances)
        source = row["classification"]
        witness = None
        reference = None
        reference_count = 0
        strength = past.get("relative_trend_20d")
        corroborating_strength = None
        if row["ticker"] == case["ticker"]:
            basis = "same_ticker"
        elif group["asset_class"] == "etf" and matched_group(source, group, "exposure"):
            basis = "etf_exposure"
        elif group["asset_class"] == "equity" and matched_group(
            source, group, "sector"
        ):
            # Different or unknown industries require a closer price match and stronger corroboration.
            same_industry = (
                source["industry"] is not None
                and source["industry"] == group["industry"]
            )
            if not same_industry and max(distances) > 0.5:
                continue
            midpoint, count = watchlist_reference(
                by_session[row["data_session"]], source
            )
            corroborators = []
            for peer in by_session[row["data_session"]]:
                if peer["ticker"] == row["ticker"] or not matched_group(
                    peer["classification"], source, "sector"
                ):
                    continue
                features = vector(peer["features"])
                if features is None or not comparable_outcome(
                    row, peer, past, features
                ):
                    continue
                if "relative_trend_20d" in past and "relative_trend_20d" in features:
                    source_strength = past["relative_trend_20d"]
                    observed = features["relative_trend_20d"]
                    kind, n = "market_benchmark", 1
                elif midpoint is not None:
                    source_strength = past["trend_20d"] - midpoint
                    observed = features["trend_20d"] - midpoint
                    kind, n = "watchlist_median", count
                else:
                    continue
                if abs(source_strength) < 0.015:
                    continue
                tolerance = min(
                    0.03, abs(source_strength) * (0.50 if same_industry else 0.25)
                )
                if (
                    abs(observed) < 0.015
                    or source_strength * observed <= 0
                    or abs(observed - source_strength) > tolerance
                ):
                    continue
                corroborators.append(
                    (
                        kind != "market_benchmark",
                        abs(observed - source_strength),
                        peer["id"],
                        peer,
                        source_strength,
                        observed,
                        kind,
                        n,
                    )
                )
            if not corroborators:
                continue
            (
                _,
                _,
                _,
                witness,
                strength,
                corroborating_strength,
                reference,
                reference_count,
            ) = min(corroborators, key=lambda x: x[:3])
            basis = "equity_peer"
        else:
            continue
        row["feature_distance"] = distance
        row["sector_selection_v1"] = {
            "basis": basis,
            "selected_ticker": row["ticker"],
            "selected_case_id": row["case_id"],
            "selected_memory_id": row["id"],
            "feature_distance": distance,
            "peer_ticker": witness["ticker"] if witness else None,
            "peer_case_id": witness["id"] if witness else None,
            "source_relative_trend_20d": strength,
            "peer_relative_trend_20d": corroborating_strength,
            "peer_reference": reference,
            "reference_count": reference_count,
            "source_window_return": window_return(row) if witness else None,
            "peer_window_return": window_return(witness) if witness else None,
        }
        candidates.append(row)
    return candidates
