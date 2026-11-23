"""Offline directional diagnostic; run from the checkout using its Python environment.

Reads saved pipeline decisions (including unfilled reports) in one read-only SELECT.
US and Korean stocks/ETFs use their exchange-local report date. Keep the last
non-automatic report per ticker/date, including HOLDs. BUY predicts up, SELL down,
HOLD abstains. Entry is the next session open and exit the fifth session close.
Without an exchange calendar we conservatively require every weekday from after
the signal through exit in one cached OHLC file. Holiday windows are therefore
omitted together with missing data. Newest coverage end wins, then largest file
by row count. Never splice price levels across separately adjusted CSVs.
Saved forecast_5s.p_up probabilities are scored independently of actions on the
same deduplicated reports. Brier is mean squared error against 1 for UP and 0
for DOWN or FLAT. Missing probabilities are never inferred from actions.
Ties score as misses for all directions. Always-up/down use identical windows.
Windows overlap and signals cluster across securities. Gross directional accuracy
is a retrospective proxy, not realized returns or out-of-sample model validation.
"""

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
ZONES = {"us": "America/New_York", "kr": "Asia/Seoul"}

QUERY = """
SELECT r.id, r.created_at, sc.ticker, sc.market, r.decision_position, r.pipeline_strategy,
       r.position_id IS NULL AS without_position,
       COALESCE(r.portfolio_rationale ILIKE 'Automatic liquidation:%', false) AS automatic
FROM reports r JOIN schedule_jobs j ON j.id = r.schedule_job_id
JOIN schedule_configs sc ON sc.id = j.schedule_config_id
ORDER BY r.created_at, r.id
"""


def load_prices(folder, ticker):
    files = []
    for path in sorted(folder.glob(f"{ticker}-YFin-data-*.csv")):
        bars = {}
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    day = date.fromisoformat(row["Date"][:10])
                    opening, closing = float(row["Open"]), float(row["Close"])
                except (ValueError, KeyError, TypeError):
                    continue
                if all(math.isfinite(x) and x > 0 for x in (opening, closing)):
                    bars[day] = opening, closing
        if bars:
            files.append(bars)
    return sorted(files, key=lambda bars: (max(bars), len(bars)), reverse=True)


def outcome(signal_day, files):
    days = []
    day = signal_day
    while len(days) < 5:
        day += timedelta(days=1)
        if day.weekday() < 5:
            days.append(day)
    for bars in files:
        if all(day in bars for day in days):
            entry, exit_price = bars[days[0]][0], bars[days[-1]][1]
            return "UP" if exit_price > entry else "DOWN" if exit_price < entry else "FLAT"
    return None


def forecast_probability(strategy):
    # JSONB may contain a legacy serialized object rather than the object itself.
    if isinstance(strategy, str):
        try:
            strategy = json.loads(strategy)
        except ValueError:
            return None
    if not isinstance(strategy, dict):
        return None
    forecast = strategy.get("forecast_5s")
    if not isinstance(forecast, dict):
        return None
    p_up = forecast.get("p_up")
    if type(p_up) not in (int, float) or not 0 <= p_up <= 1:
        return None
    return float(p_up)


def evaluate(rows, cache):
    coverage = Counter()
    signals = {}
    for row in rows:
        coverage["reports"] += 1
        ticker, market = row["ticker"], row["market"]
        if row["automatic"]:
            coverage["automatic_excluded"] += 1
            continue
        if market == "crypto" or ticker.endswith("-USD"):
            coverage["crypto_excluded"] += 1
            continue
        if market not in ZONES:
            coverage["unknown_market"] += 1
            continue
        day = row["created_at"].astimezone(ZoneInfo(ZONES[market])).date()
        if (ticker, day) in signals:
            coverage["same_day_superseded"] += 1
        signals[ticker, day] = row

    files = {}
    results = defaultdict(Counter)
    squared_errors = []
    pending_forecasts = 0
    for (ticker, day), row in signals.items():
        action = (row["decision_position"] or "").strip().upper()
        p_up = forecast_probability(row.get("pipeline_strategy"))
        directional = action in ("BUY", "SELL")
        if directional:
            coverage["directional_signals"] += 1
        else:
            coverage["hold_abstention" if action == "HOLD" else "unknown_action"] += 1
            if p_up is None:
                continue
        if ticker not in files:
            files[ticker] = load_prices(cache, ticker)
        direction = outcome(day, files[ticker])
        if p_up is not None:
            if direction is None:
                pending_forecasts += 1
            else:
                squared_errors.append((p_up - int(direction == "UP")) ** 2)
        if not directional:
            continue
        if direction is None:
            coverage["missing_window"] += 1
            continue
        coverage["scored"] += 1
        coverage["scored_without_position"] += int(row["without_position"])
        results[action][direction] += 1

    by_action = {}
    for action, predicted in (("BUY", "UP"), ("SELL", "DOWN")):
        counts = results[action]
        by_action[action] = {"n": sum(counts.values()), "correct": counts[predicted],
                             **{d: counts[d] for d in ("UP", "DOWN", "FLAT")}}
    n = coverage["scored"]
    scores = {"signal": results["BUY"]["UP"] + results["SELL"]["DOWN"],
              "always_up": sum(c["UP"] for c in results.values()),
              "always_down": sum(c["DOWN"] for c in results.values())}
    forecast = {"n": len(squared_errors), "pending_or_missing_window": pending_forecasts,
                "mean_brier": math.fsum(squared_errors) / len(squared_errors) if squared_errors else None,
                "paired_brier_p_0_5": 0.25 if squared_errors else None}
    return {"coverage": dict(coverage), "by_action": by_action, "forecast_5s": forecast,
            "paired_accuracy_pct": {k: round(v * 100 / n, 2) if n else None for k, v in scores.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "packages/tradingagents/dataflows/data_cache")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    env = {**dotenv_values(args.env_file), **os.environ}
    if env.get("POSTGRES_HOST") not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("This diagnostic requires a local PostgreSQL host.")
    with psycopg.connect(host=env["POSTGRES_HOST"], port=env["POSTGRES_PORT"], dbname=env["POSTGRES_DB"],
                         user=env["POSTGRES_USER"], password=env["POSTGRES_PASSWORD"],
                         connect_timeout=5, options="-c default_transaction_read_only=on",
                         row_factory=dict_row) as conn:
        rows = conn.execute(QUERY).fetchall()
    print(json.dumps(evaluate(rows, args.cache), indent=2))


if __name__ == "__main__":
    main()
