"""Read a bounded set of already observed headlines for one trading decision."""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from .issue_collector import EXPORT, SOURCE, case_issues, timestamp
from .shared_archive import LocalSupplement


def trade_news(conn, ticker, as_of):
    cutoff = timestamp(as_of)
    if cutoff > datetime.now(UTC) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,15}", ticker):
        raise ValueError("Invalid decision identity or cutoff")
    # Both provenance checks see the same committed archive, even during collection.
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
    groups = [case_issues(conn, ticker, cutoff, source=source) for source in (EXPORT, SOURCE)]
    items, urls = [], set()
    covered = 0
    for group in groups:
        if not group:
            continue
        if group["status"] in ("available", "empty"):
            covered += 1
        # case_issues already applies the archive limit; pass every eligible row.
        for row in group["items"]:
            if row["url"] in urls:
                continue
            urls.add(row["url"])
            item = {key: row[key] for key in (
                "source", "title", "url", "publisher", "published_at", "first_seen_at"
            )}
            if row.get("published_day"):
                item["published_day"] = row["published_day"]
            items.append({**item, "ref": f"N{len(items) + 1}"})
    if covered == len(groups):
        status = "available" if items else "empty"
    else:
        status = "partial" if items or covered else "unavailable"
    return {"version": 1, "ticker": ticker, "as_of": cutoff.isoformat(), "status": status, "items": items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    if os.environ.get("GANT_LAST30DAYS_SCHEDULED_HANDSHAKE") == "1" and sys.stdin.readline() != "start\n":
        return 1
    config = Path(os.environ["LOCALAPPDATA"]) / "TradingAgentsV3/shared-read/logins.json"
    with LocalSupplement(config).connect("v3_archive") as conn:
        packet = trade_news(conn, args.ticker, args.as_of)
    print(json.dumps(packet, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
