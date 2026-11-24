"""Prospective daily-bar forecasts. No trading, database, or model-side data access."""

import hashlib
import itertools
import json
import math
import os
import re
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from statistics import stdev
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import exchange_calendars as calendars
import requests
import yfinance as yf
from yfinance.exceptions import YFPricesMissingError

from .classification import POLICY, classify

EXPERIMENT_VERSION = "direction-5s-v2"
DELAY = timedelta(minutes=20)
MARKETS = {
    "us": (
        "XNYS",
        "America/New_York",
        "USD",
        {"NMS", "NGM", "NCM", "NYQ", "NYS", "ASE", "PCX", "BTS", "BATS"},
    ),
    "kr": ("XKRX", "Asia/Seoul", "KRW", {"KSC", "KOE"}),
}
SOURCE = "Yahoo Finance via yfinance; daily Open/High/Low/Close, actions=True, auto_adjust=False"
KR_SOURCE = (
    "NAVER Finance fchart Korean daily OHLCV (provider's historical chart, split-adjusted); "
    "Yahoo Finance instrument metadata, split and dividend action flags"
)
PROMPT = """동결된 시장 데이터만 근거로 지정된 진입 세션 시가보다 다섯 번째 세션 종가가 높을 확률을 추정하세요.
수익률이나 매매 추천이 아닌 이진 사건의 확률입니다. 확률은 0~1 숫자, rationale은 확인 가능한 수치 근거와 불확실성을 담은 한국어 문장으로 작성하세요.
뉴스, 외부 도구, 이후 시세 또는 제시되지 않은 기업정보는 사용하지 마세요. JSON 객체 {"probability": 숫자, "rationale": "근거"}만 출력하세요."""


class ForecastUnavailable(ValueError):
    """The market or clock does not support this prospective observation."""


def _iso(moment):
    if moment.utcoffset() is None:
        raise ValueError("Expected an aware clock")
    return moment.astimezone(UTC).isoformat()


def _json(data):
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


@lru_cache(maxsize=1)
def _configure_yahoo_cache():
    root = (
        os.getenv("FORECAST_LAB_STATE_DIR")
        or Path(os.getenv("LOCALAPPDATA", Path.home())) / "TradingAgentsForecastLab"
    )
    yf.set_tz_cache_location(str(Path(root) / "yfinance-cache"))


def _clean_window(rows):
    return all(
        row and not row["split"] and not row.get("adjustment_uncertain") for row in rows
    )


class YahooBars:
    def fetch(self, ticker, start, end):
        """Return metadata and raw daily records; end is an inclusive exchange date."""
        _configure_yahoo_cache()
        instrument = yf.Ticker(ticker)
        frame = instrument.history(
            start=start,
            end=(date.fromisoformat(end) + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            actions=True,
            repair=False,
            raise_errors=True,
            timeout=20,
        )
        # Only identity fields are used from metadata; live price/volume fields never enter evidence.
        meta = instrument.history_metadata
        records = []
        for timestamp, row in frame.iterrows():
            records.append(
                {
                    "date": timestamp.date().isoformat(),
                    **{
                        field: float(row[column])
                        for field, column in [
                            ("open", "Open"),
                            ("high", "High"),
                            ("low", "Low"),
                            ("close", "Close"),
                            ("volume", "Volume"),
                            ("split", "Stock Splits"),
                            ("dividend", "Dividends"),
                        ]
                    },
                }
            )
        if ticker.endswith((".KS", ".KQ")):
            # Never splice Yahoo and NAVER price rows. Yahoo supplies instrument identity
            # and action flags only, and a missing action observation is not assumed zero.
            code = ticker.split(".")[0]
            actions = {row["date"]: row for row in records}
            response = requests.get(
                "https://fchart.stock.naver.com/sise.nhn",
                timeout=15,
                params={
                    "symbol": code,
                    "timeframe": "day",
                    "startTime": start.replace("-", ""),
                    "endTime": end.replace("-", ""),
                    "requestType": "1",
                },
            )
            response.raise_for_status()
            chart = ElementTree.fromstring(response.content.decode("euc-kr")).find(
                ".//chartdata"
            )
            if chart is None or chart.get("symbol") != code:
                raise ForecastUnavailable("NAVER chart identity mismatch")
            records = []
            for item in chart.findall("item"):
                day, *values = item.attrib["data"].split("|")
                day = datetime.strptime(day, "%Y%m%d").date().isoformat()
                action = actions.get(day)
                if (
                    action
                    and len(values) == 5
                    and all(math.isfinite(action[k]) for k in ("split", "dividend"))
                ):
                    records.append(
                        dict(
                            date=day,
                            split=action["split"],
                            dividend=action["dividend"],
                            adjustment_uncertain=bool(action["dividend"]),
                            **dict(
                                zip(
                                    ("open", "high", "low", "close", "volume"),
                                    map(float, values),
                                )
                            ),
                        )
                    )
            meta = dict(meta, price_source=KR_SOURCE)
        return meta, records


def _validate_market(meta, ticker, market):
    _, zone, currency, exchanges = MARKETS[market]
    if (
        meta.get("instrumentType") not in {"EQUITY", "ETF"}
        or meta.get("currency") != currency
        or meta.get("exchangeTimezoneName") != zone
        or meta.get("exchangeName") not in exchanges
        or str(meta.get("symbol", "")).upper() != ticker.upper()
    ):
        raise ForecastUnavailable(
            f"Unsupported market metadata for {ticker}: "
            f"{meta.get('exchangeName')} / {meta.get('instrumentType')} / {meta.get('currency')}"
        )


def _valid_bar(row):
    values = [
        row.get(key) for key in ("open", "high", "low", "close", "volume", "split")
    ]
    return (
        all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
        and row["volume"] > 0
        and row["split"] >= 0
        and 0 < row["low"] <= min(row["close"], row["open"])
        and max(row["open"], row["close"]) <= row["high"]
    )


def _usable_bars(rows, sessions):
    seen, bars = set(), {}
    for row in rows:
        day = row["date"]
        if day in sessions:
            if day in seen:
                bars.pop(day, None)
            elif _valid_bar(row):
                bars[day] = row
            seen.add(day)
    return bars


def _baseline(days, bars):
    wins, total = 0, 0
    for i in range(len(days) - 4):
        window = [bars.get(d) for d in days[i : i + 5]]
        if _clean_window(window):
            total += 1
            wins += int(window[-1]["close"] > window[0]["open"])
    if total < 20:
        raise ForecastUnavailable(
            "Fewer than 20 complete historical five-session windows"
        )
    return {"windows": total, "up": wins, "probability": (wins + 1) / (total + 2)}


def _parse_probability(text):
    def pairs(pairs_):
        if len(dict(pairs_)) != len(pairs_):
            raise ValueError("Duplicate JSON keys")
        return dict(pairs_)

    result = json.loads(text, object_pairs_hook=pairs)
    if not isinstance(result, dict) or set(result) != {"probability", "rationale"}:
        raise ValueError("Expected probability and rationale")
    p, reason = result["probability"], result["rationale"]
    if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Probability must be a finite JSON number between 0 and 1")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Missing forecast rationale")
    return float(p), reason.strip()


def _risk_forecast(text):
    blocks = list(re.finditer(r"```strategy_json\s*(.*?)\s*```", text, re.DOTALL))
    if len(blocks) != 1 or text[blocks[0].end() :].strip():
        raise ValueError("Risk judge must end with one strategy_json block")
    rationale = text[: blocks[0].start()].strip()

    def unique(pairs):
        if len(dict(pairs)) != len(pairs):
            raise ValueError("Duplicate risk-judge JSON keys")
        return dict(pairs)

    data = json.loads(blocks[0][1], object_pairs_hook=unique)
    forecast = data.get("forecast_5s") if isinstance(data, dict) else None
    if not isinstance(forecast, dict) or "p_up" not in forecast:
        raise ValueError("Missing risk-judge forecast_5s")
    probability = forecast.get("p_up")
    if (
        type(probability) not in (int, float)
        or not 0 <= probability <= 1
        or not rationale
    ):
        raise ValueError("No valid risk-judge probability/rationale")
    return rationale, float(probability)


def _calendar_horizon_matches(snapshot):
    cal = calendars.get_calendar(MARKETS[snapshot["market"]][0])
    day = date.fromisoformat(snapshot["data_session"])
    if not cal.is_session(day):
        return False
    sessions = cal.sessions_in_range(day + timedelta(days=1), day + timedelta(days=40))[
        :5
    ]
    return (
        [s.date().isoformat() for s in sessions] == snapshot["sessions"]
        and len(sessions) == 5
        and cal.session_open(sessions[0])
        == datetime.fromisoformat(snapshot["entry_open_at"])
        and cal.session_close(sessions[-1])
        == datetime.fromisoformat(snapshot["exit_close_at"])
    )


class ForecastEngine:
    def __init__(self, provider=None, clock=None, llm=None, model=None):
        if provider is None:
            from .market_runner import MarketProvider

            provider = MarketProvider()
        self.provider = provider
        self.clock = clock or (lambda: datetime.now(UTC))
        self.llm = llm
        self.model = model or os.getenv("FORECAST_LAB_MODEL", "gpt-6.2-sol")

    def _before_open(self, snapshot):
        now = self.clock()
        if snapshot.get("observed_at") and now < datetime.fromisoformat(
            snapshot["observed_at"]
        ):
            raise ForecastUnavailable("Snapshot has not been observed yet")
        if now >= datetime.fromisoformat(snapshot["entry_open_at"]):
            raise ForecastUnavailable("Entry session has already opened")
        return now

    def snapshot(self, ticker, market):
        market, ticker = market.lower(), ticker.strip().upper()
        if market not in MARKETS:
            raise ForecastUnavailable(f"Unsupported market {market}")
        calendar_id, zone, currency, _ = MARKETS[market]
        cal = calendars.get_calendar(calendar_id)
        now = self.clock()
        today = now.astimezone(ZoneInfo(zone)).date()
        candidates = cal.sessions_in_range(
            today - timedelta(days=165), today + timedelta(days=40)
        )
        last = max(
            i
            for i, day in enumerate(candidates)
            if cal.session_close(day) + DELAY <= now
        )
        day = candidates[last]
        future = candidates[last + 1 : last + 6]
        stamp = lambda session: session.date().isoformat()
        history = [stamp(s) for s in candidates[max(0, last - 64) : last + 1]]
        days = [stamp(s) for s in future]
        snapshot = {
            "ticker": ticker,
            "market": market,
            "experiment_version": EXPERIMENT_VERSION,
            "input_policy": "corporate-action-clean-trailing-windows-v2",
            "calendar_version": calendars.__version__,
            "data_session": stamp(day),
            "data_close_at": _iso(cal.session_close(day)),
            "entry_open_at": _iso(cal.session_open(future[0])),
            "exit_close_at": _iso(cal.session_close(future[-1])),
            "entry_date": days[0],
            "exit_date": days[-1],
            "sessions": days,
            "exchange": calendar_id,
            "currency": currency,
            "source": SOURCE,
        }
        self._before_open(snapshot)
        meta, records = self.provider.fetch(ticker, history[0], history[-1])
        _validate_market(meta, ticker, market)
        bars = _usable_bars(records, set(history))
        recent = [bars.get(session) for session in history[-21:]]
        if len(recent) < 21 or not _clean_window(recent):
            raise ForecastUnavailable(
                "Latest 21-session prices incomplete or crossed an uncertain corporate action"
            )
        baseline = _baseline(history, bars)
        returns = [b["close"] / a["close"] - 1 for a, b in itertools.pairwise(recent)]
        ticker_trend = recent[-1]["close"] / recent[0]["close"] - 1
        benchmark = "SPY" if market == "us" else "069500.KS"
        benchmark_info = {"ticker": benchmark, "status": "unavailable"}
        if ticker == benchmark:
            benchmark_rows, benchmark_meta = recent, meta
        else:
            try:
                benchmark_meta, raw = self.provider.fetch(
                    benchmark, history[-21], history[-1]
                )
                _validate_market(benchmark_meta, benchmark, market)
                by_date = _usable_bars(raw, set(history[-21:]))
                benchmark_rows = [by_date.get(d) for d in history[-21:]]
            except Exception as exc:  # noqa: BLE001 -- optional benchmark may fail independently across providers
                benchmark_rows = []
                benchmark_info["reason"] = type(exc).__name__
        features = {"trend_20d": ticker_trend, "volatility_20d": stdev(returns)}
        if len(benchmark_rows) == 21 and _clean_window(benchmark_rows):
            trend = benchmark_rows[-1]["close"] / benchmark_rows[0]["close"] - 1
            vol = stdev(
                b["close"] / a["close"] - 1
                for a, b in itertools.pairwise(benchmark_rows)
            )
            features.update(
                benchmark_trend_20d=trend,
                benchmark_volatility_20d=vol,
                relative_trend_20d=ticker_trend - trend,
            )
            benchmark_info.update(
                status="available",
                bars=benchmark_rows,
                source=benchmark_meta.get("price_source", SOURCE),
            )
        elif "reason" not in benchmark_info:
            benchmark_info["reason"] = (
                "Incomplete, split or uncertain corporate-action window"
            )
        snapshot.update(
            source=meta.get("price_source", SOURCE),
            benchmark=benchmark_info,
            observed_at=_iso(self._before_open(snapshot)),
            bars=[bars[s] for s in history if s in bars],
            provider_exchange=meta["exchangeName"],
            instrument=meta["instrumentType"],
            classification=classify(ticker, meta["instrumentType"]),
            retrieval_policy=POLICY,
            history_sessions=history,
            baseline=baseline,
            features=features,
        )
        return snapshot

    def outcome(self, snapshot):
        if self.clock() < datetime.fromisoformat(snapshot["exit_close_at"]) + DELAY:
            return None
        if not _calendar_horizon_matches(snapshot):
            return {
                "status": "excluded",
                "reason": "Exchange calendar revised the frozen five-session horizon",
                "source": snapshot["source"],
                "observed_at": _iso(self.clock()),
                "evidence": {
                    "calendar_version": calendars.__version__,
                    "sessions": snapshot["sessions"],
                },
            }
        days = snapshot["sessions"]
        grace_end = datetime.fromisoformat(snapshot["exit_close_at"]) + timedelta(
            days=7
        )
        try:
            meta, rows = self.provider.fetch(snapshot["ticker"], days[0], days[-1])
            _validate_market(meta, snapshot["ticker"], snapshot["market"])
            if (
                meta["exchangeName"] != snapshot["provider_exchange"]
                or meta["instrumentType"] != snapshot["instrument"]
            ):
                raise ForecastUnavailable(
                    "Instrument classification or listing exchange changed"
                )
        except (ForecastUnavailable, YFPricesMissingError) as exc:
            observed = self.clock()
            if observed < grace_end:
                return None
            return {
                "status": "excluded",
                "reason": "No verified instrument price window after seven days",
                "source": snapshot["source"],
                "observed_at": _iso(observed),
                "evidence": {"sessions": days, "vendor_error": str(exc)},
            }
        bars = _usable_bars(rows, set(days))
        observed = self.clock()
        evidence = {
            "bars": [bars[d] for d in days if d in bars],
            "sessions": days,
            "exchange": meta["exchangeName"],
        }
        source = meta.get("price_source", SOURCE)
        if source != snapshot["source"]:
            raise ForecastUnavailable(
                "Outcome price source differs from frozen issuance source"
            )
        base = {"observed_at": _iso(observed), "source": source, "evidence": evidence}
        if len(bars) != 5:
            # Give delayed historical bars seven days to settle before classifying incomplete evidence.
            if observed < grace_end:
                return None
            return dict(
                base,
                status="excluded",
                reason="Incomplete or invalid five-session OHLCV window",
            )
        if any(row["split"] for row in bars.values()):
            return dict(
                base,
                status="excluded",
                reason="Split occurred during the outcome window",
            )
        if any(row.get("adjustment_uncertain") for row in bars.values()):
            return dict(
                base,
                status="excluded",
                reason="NAVER historical adjustment basis uncertain across dividend",
            )
        entry, exit_price = bars[days[0]]["open"], bars[days[-1]]["close"]
        return dict(
            base,
            status="scored",
            entry_open=entry,
            exit_close=exit_price,
            actual=int(exit_price > entry),
            reason=None,
        )

    @staticmethod
    def _memory_evidence(snapshot, memory):
        if not memory or not memory.get("id"):
            raise ForecastUnavailable("No eligible matured memory")
        cutoff = datetime.fromisoformat(snapshot["observed_at"])
        for key in ("created_at", "observed_at"):
            value = memory.get(key)
            if isinstance(value, str):
                value = datetime.fromisoformat(value)
            if (
                not isinstance(value, datetime)
                or value.utcoffset() is None
                or value >= cutoff
            ):
                raise ForecastUnavailable(
                    "Memory was not already available at snapshot observation"
                )
        if (
            memory.get("market") != snapshot["market"]
            or memory.get("experiment_version") != snapshot["experiment_version"]
        ):
            raise ForecastUnavailable("Memory market or experiment version mismatch")
        keys = (
            "ticker",
            "market",
            "probability",
            "rationale",
            "actual",
            "features",
            "entry_open",
            "exit_close",
            "brier",
        )
        return {key: memory[key] for key in keys if key in memory}

    def _chat(self, prompt, snapshot):
        now = self._before_open(snapshot)
        if self.llm is None:
            from .model_runner import invoke_codex

            remaining = (
                datetime.fromisoformat(snapshot["entry_open_at"]) - now
            ).total_seconds()
            response = invoke_codex(self.model, prompt, min(300, remaining))
        else:
            response = self.llm.invoke(prompt).content
        self._before_open(snapshot)
        if not isinstance(response, str) or not response.strip():
            raise ValueError("Model returned empty text")
        return response

    def _debate(self, snapshot, evidence):
        from langchain_core.messages import AIMessage
        from tradingagents.agents.managers.research_manager import (
            create_research_manager,
        )
        from tradingagents.agents.managers.risk_manager import create_risk_manager
        from tradingagents.agents.researchers.bear_researcher import (
            create_bear_researcher,
        )
        from tradingagents.agents.researchers.bull_researcher import (
            create_bull_researcher,
        )
        from tradingagents.agents.risk_mgmt.aggressive_debator import (
            create_aggressive_debator,
        )
        from tradingagents.agents.risk_mgmt.conservative_debator import (
            create_conservative_debator,
        )
        from tradingagents.agents.risk_mgmt.neutral_debator import (
            create_neutral_debator,
        )
        from tradingagents.agents.trader.trader import create_trader

        engine = self
        trace = []

        class FrozenChat:
            def invoke(self, prompt):
                instruction = (
                    "Use only supplied frozen evidence, no outside facts or tools. "
                    "Respond concisely in Korean. The authoritative five-session target starts "
                    f"at {snapshot['entry_open_at']} and ends at {snapshot['exit_close_at']}."
                )
                if (
                    isinstance(prompt, str)
                    and "Risk Management Judge and Debate Facilitator" in prompt
                ):
                    old = (
                        "the close of the fifth trading\nsession exceeds the opening price of the "
                        "first trading session strictly after the\nreport publication date in the ticker's market."
                    )
                    if old not in prompt:
                        raise ValueError(
                            "Production risk-judge horizon changed; review forecast adapter"
                        )
                    prompt = prompt.replace(
                        old,
                        f"the close on {snapshot['exit_date']} exceeds the opening price "
                        f"on {snapshot['entry_date']} for this frozen five-session case.",
                    )
                messages = [{"role": "system", "content": instruction}]
                messages.extend(
                    [{"role": "user", "content": prompt}]
                    if isinstance(prompt, str)
                    else prompt
                )
                content = engine._chat(messages, snapshot)
                trace.append(
                    {
                        "input_sha256": hashlib.sha256(
                            _json(messages).encode()
                        ).hexdigest(),
                        "output": content,
                    }
                )
                return AIMessage(content=content)

        adapter = FrozenChat()
        state = {
            "company_of_interest": snapshot["ticker"],
            "risk_debate_state": {"count": 0},
            "investment_debate_state": {"count": 0},
            "market_report": evidence,
            "sentiment_report": "Unavailable",
            "news_report": "Unavailable",
            "fundamentals_report": "Unavailable",
        }
        factories = (
            create_bull_researcher,
            create_bear_researcher,
            create_research_manager,
            create_trader,
            create_aggressive_debator,
            create_conservative_debator,
            create_neutral_debator,
        )
        for factory in factories:
            state.update(factory(adapter)(state))
            trace[-1]["role"] = factory.__name__
        judge = create_risk_manager(adapter)
        for attempt in range(2):
            text = judge(state)["final_trade_decision"]
            trace[-1]["role"] = "create_risk_manager"
            try:
                rationale, probability = _risk_forecast(text)
                return probability, rationale, trace
            except ValueError:
                if attempt:
                    raise

    def forecast(self, snapshot, method, memory=None):
        self._before_open(snapshot)
        if not _calendar_horizon_matches(snapshot):
            raise ForecastUnavailable(
                "Exchange calendar revised the frozen five-session horizon"
            )
        # The deterministic arm may be independently reconstructed from raw prices.
        # Its computed probability is never included in an LLM control prompt.
        evidence = _json(
            {
                key: value for key, value in snapshot.items()
                if key not in {"baseline", "classification", "retrieval_policy"}
            }
        )
        audit = {
            "snapshot_sha256": hashlib.sha256(_json(snapshot).encode()).hexdigest(),
            "market_input_sha256": hashlib.sha256(evidence.encode()).hexdigest(),
        }
        memory_id = None
        if method == "baseline":
            historical = snapshot["baseline"]
            p = historical["probability"]
            reason = f"완료된 과거 5세션 창 {historical['windows']}개 중 상승 {historical['up']}개. Laplace +1/+2 보정."
            model, version = "deterministic", "laplace-5s-v1"
        elif method == "debate":
            model, version = self.model, "original-eight-nodes-1round-risk-forecast-v1"
            p, reason, audit["debate"] = self._debate(snapshot, evidence)
        else:
            if method not in {"single", "memory", "memory_sector"}:
                raise ValueError(f"Unknown forecast method {method}")
            model, version = self.model, "frozen-probability-v1"
            prompt = PROMPT + "\n" + evidence
            if method == "memory_sector" and snapshot.get("retrieval_policy") != POLICY:
                raise ValueError("Sector retrieval requires an opted-in snapshot")
            if method in {"memory", "memory_sector"}:
                prior = self._memory_evidence(snapshot, memory)
                memory_id = memory["id"]
                prompt += "\n이전 성숙 사례 하나:\n" + _json(prior)
            audit["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
            for attempt in range(2):
                text = self._chat(prompt, snapshot)
                try:
                    p, reason = _parse_probability(text)
                    break
                except ValueError:
                    if attempt:
                        raise
                    prompt += "\nJSON 형식 오류입니다. 지정된 스키마만 출력하세요."
            audit["attempts"] = attempt + 1
        return {
            "method": method,
            "probability": p,
            "rationale": reason,
            "model": model,
            "version": version,
            "memory_id": memory_id,
            "audit": audit,
            "published_at": _iso(self._before_open(snapshot)),
        }
