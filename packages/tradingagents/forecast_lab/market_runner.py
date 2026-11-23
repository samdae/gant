"""Isolate all HTTP, retries and metadata requests needed for one market history read."""

import json
import sys

from .bounded_process import bounded_run


class MarketProvider:
    def fetch(self, ticker, start, end):
        from .engine import ForecastUnavailable

        command = [sys.executable, "-m", "tradingagents.forecast_lab.market_runner"]
        result = json.loads(
            bounded_run(
                command, json.dumps([ticker, start, end]), 60, "Market price provider"
            )
        )
        if result.get("missing"):
            raise ForecastUnavailable(result["missing"])
        if result.get("error"):
            raise RuntimeError(f"Market price provider failed: {result['error']}")
        return result["identity"], result["bars"]


def main():
    ticker, start, end = json.load(sys.stdin)
    from yfinance.exceptions import YFPricesMissingError

    from .engine import ForecastUnavailable, YahooBars

    try:
        meta, bars = YahooBars().fetch(ticker, start, end)
        keys = (
            "symbol",
            "currency",
            "exchangeName",
            "exchangeTimezoneName",
            "instrumentType",
            "price_source",
        )
        result = {"identity": {k: meta[k] for k in keys if k in meta}, "bars": bars}
    except (ForecastUnavailable, YFPricesMissingError) as exc:
        result = {"missing": str(exc)}
    except Exception as exc:  # noqa: BLE001 -- expose only the error kind from the isolated vendor
        result = {"error": type(exc).__name__}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
