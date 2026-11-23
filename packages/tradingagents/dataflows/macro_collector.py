"""Macro indicators + sector health collector.

v7: Collects market-level macro indicators and sector-relative strength
for injection into 12-agent pipeline and PA. All data from yfinance only.
"""

import logging
from math import isfinite
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

from .fundamental_dates import market_today

logger = logging.getLogger(__name__)

SECTOR_ETF_US = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}

SECTOR_ETF_KR = {
    "Technology": "091160.KS",
    "Consumer Cyclical": "305720.KS",
    "Consumer Defensive": "266390.KS",
    "Energy": "117460.KS",
    "Financial Services": "091170.KS",
    "Healthcare": "266420.KS",
    "Industrials": "102780.KS",
    "Basic Materials": "117680.KS",
}

_macro_cache: Dict[Tuple[str, bool], Tuple[str, str]] = {}
_sector_cache: Dict[str, Tuple[str, str]] = {}


def _history(symbol: str, days: int, cutoff: str) -> pd.DataFrame:
    """Use completed prior dates across exchanges when only a decision date is known."""
    end = datetime.strptime(cutoff, "%Y-%m-%d").date()
    bars = yf.Ticker(symbol).history(start=(end - timedelta(days=days)).isoformat(), end=cutoff)
    if bars.empty:
        return bars
    return bars.loc[bars.index.date < end].sort_index()


def _safe_latest(ticker_symbol: str, cutoff: str) -> Optional[float]:
    try:
        hist = _history(ticker_symbol, 14, cutoff)
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.debug(f"Failed to fetch {ticker_symbol}: {e}")
        return None


def _safe_sma(ticker_symbol: str, window: int, cutoff: str) -> Optional[float]:
    try:
        hist = _history(ticker_symbol, 400, cutoff)
        if hist.empty or len(hist) < window:
            return None
        return float(hist["Close"].rolling(window=window).mean().iloc[-1])
    except Exception as e:
        logger.debug(f"Failed to compute SMA({window}) for {ticker_symbol}: {e}")
        return None


def _relative_strength_20d(etf_symbol: str, benchmark_symbol: str, cutoff: str) -> Optional[float]:
    try:
        etf = _history(etf_symbol, 60, cutoff)
        bench = _history(benchmark_symbol, 60, cutoff)
        if etf.empty or bench.empty:
            return None
        closes = pd.concat([etf["Close"], bench["Close"]], axis=1, join="inner").dropna().tail(21)
        if len(closes) < 21:
            return None
        gains = (closes.iloc[-1] / closes.iloc[0] - 1) * 100
        return round(float(gains.iloc[0] - gains.iloc[1]), 2)
    except Exception as e:
        logger.debug(f"Failed to compute relative strength {etf_symbol} vs {benchmark_symbol}: {e}")
        return None


def _btc_volatility_20d(cutoff: str) -> Optional[float]:
    try:
        hist = _history("BTC-USD", 45, cutoff)
        if hist.empty or len(hist["Close"].dropna()) < 21:
            return None
        returns = hist["Close"].dropna().pct_change().dropna().tail(20)
        vol = float(returns.std() * (365 ** 0.5) * 100)
        return round(vol, 1)
    except Exception as e:
        logger.debug(f"Failed to compute BTC volatility: {e}")
        return None


def _fmt(value: Optional[float], suffix: str = "", decimals: int = 2) -> str:
    if value is None or not isfinite(value):
        return "N/A"
    return f"{value:,.{decimals}f}{suffix}"


def _trend_vs_sma(price: Optional[float], sma: Optional[float]) -> str:
    if price is None or sma is None or not isfinite(price) or not isfinite(sma) or sma == 0:
        return "N/A"
    diff_pct = (price / sma - 1) * 100
    direction = "위" if diff_pct >= 0 else "아래"
    return f"{direction} ({diff_pct:+.1f}%)"


def _collect_macro_us(cutoff: str) -> str:
    vix = _safe_latest("^VIX", cutoff)
    irx = _safe_latest("^IRX", cutoff)
    tnx = _safe_latest("^TNX", cutoff)
    spread = round(tnx - irx, 2) if (tnx is not None and irx is not None) else None
    spread_label = "" if spread is None else "정상" if spread > 0 else "역전" if spread < 0 else "평탄"

    nasdaq_price = _safe_latest("^IXIC", cutoff)
    nasdaq_sma50 = _safe_sma("^IXIC", 50, cutoff)
    nasdaq_sma200 = _safe_sma("^IXIC", 200, cutoff)

    lines = [
        "[매크로 — 나스닥]",
        f"VIX (공포지수): {_fmt(vix)}",
        f"미국 13주 국채 수익률: {_fmt(irx, '%')}",
        f"장단기 금리차 (10Y-3M): {_fmt(spread, '%p')} ({spread_label})" if spread_label else f"장단기 금리차 (10Y-3M): {_fmt(spread, '%p')}",
        f"나스닥 50일선: {_trend_vs_sma(nasdaq_price, nasdaq_sma50)}",
        f"나스닥 200일선: {_trend_vs_sma(nasdaq_price, nasdaq_sma200)}",
    ]
    return "\n".join(lines)


def _collect_macro_kr(cutoff: str) -> str:
    vix = _safe_latest("^VIX", cutoff)
    usdkrw = _safe_latest("USDKRW=X", cutoff)

    kospi_price = _safe_latest("^KS11", cutoff)
    kospi_sma50 = _safe_sma("^KS11", 50, cutoff)
    kospi_sma200 = _safe_sma("^KS11", 200, cutoff)

    lines = [
        "[매크로 — 코스피]",
        f"VIX (글로벌 공포지수): {_fmt(vix)}",
        f"USDKRW 환율: {_fmt(usdkrw, '원', 0)}",
        f"코스피 50일선: {_trend_vs_sma(kospi_price, kospi_sma50)}",
        f"코스피 200일선: {_trend_vs_sma(kospi_price, kospi_sma200)}",
    ]
    return "\n".join(lines)


def _collect_macro_crypto(cutoff: str) -> str:
    btc_vol = _btc_volatility_20d(cutoff)
    dxy = _safe_latest("DX-Y.NYB", cutoff)

    btc_cap = None
    try:
        info = (yf.Ticker("BTC-USD").info or {}) if cutoff == market_today("BTC-USD").isoformat() else {}
        btc_cap = info.get("marketCap")
    except Exception:
        pass

    lines = [
        "[매크로 — 코인]",
        f"BTC 20일 변동성 (연율화): {_fmt(btc_vol, '%', 1)}",
        f"DXY (달러 인덱스): {_fmt(dxy)}",
        f"BTC 시가총액: ${btc_cap / 1e12:.2f}T" if btc_cap else "BTC 시가총액: N/A",
    ]
    return "\n".join(lines)


def _collect_sector(ticker: str, market: str, cutoff: str) -> str:
    if cutoff != market_today(ticker).isoformat():
        return ""
    sector = None
    try:
        info = yf.Ticker(ticker).info or {}
        sector = info.get("sector")
    except Exception as e:
        logger.debug(f"Failed to get sector for {ticker}: {e}")

    if not sector:
        return "[섹터] 판별 불가 — 매크로만 참조"

    if market == "kr":
        etf_map = SECTOR_ETF_KR
        benchmark = "^KS11"
        benchmark_name = "코스피"
    else:
        etf_map = SECTOR_ETF_US
        benchmark = "SPY"
        benchmark_name = "SPY"

    etf_ticker = etf_map.get(sector)
    if not etf_ticker:
        return f"[섹터 — {sector}] 대응 ETF 없음 — 시장 전체 지수 참조"

    today = cutoff
    cache_key = etf_ticker
    if cache_key in _sector_cache and _sector_cache[cache_key][0] == today:
        return _sector_cache[cache_key][1]

    rs = _relative_strength_20d(etf_ticker, benchmark, cutoff)
    etf_price = _safe_latest(etf_ticker, cutoff)
    etf_sma50 = _safe_sma(etf_ticker, 50, cutoff)

    rs_label = "" if rs is None else "강세" if rs > 0 else "약세" if rs < 0 else "보합"
    lines = [
        f"[섹터 — {sector} ({etf_ticker})]",
        f"{benchmark_name} 대비 상대 강도 (20일): {_fmt(rs, '%')}" + (f" ({rs_label})" if rs_label else ""),
        f"{etf_ticker} 50일선: {_trend_vs_sma(etf_price, etf_sma50)}",
    ]
    result = "\n".join(lines)
    _sector_cache[cache_key] = (today, result)
    return result


def collect_macro_context(ticker: str, market: str, as_of: Optional[str] = None) -> str:
    """Collect macro indicators + sector health for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g. "NVDA", "005930.KS", "BTC-USD")
        market: Market type from schedule_configs ("us", "kr", "crypto")
        as_of: Decision date (YYYY-MM-DD). Daily bars strictly precede this date.

    Returns:
        Formatted text for injection into agent prompts.
        On total failure, returns empty string (graceful degradation).
    """
    today = market_today(ticker).isoformat()
    cutoff = as_of or today
    if cutoff > today:
        raise ValueError("Macro analysis date cannot be in the future")

    cache_key = (market, cutoff == today)
    if cache_key in _macro_cache and _macro_cache[cache_key][0] == cutoff:
        macro_text = _macro_cache[cache_key][1]
    else:
        try:
            if market == "kr":
                macro_text = _collect_macro_kr(cutoff)
            elif market == "crypto":
                macro_text = _collect_macro_crypto(cutoff)
            else:
                macro_text = _collect_macro_us(cutoff)
            _macro_cache[cache_key] = (cutoff, macro_text)
        except Exception as e:
            logger.warning(f"Macro collection failed for market={market}: {e}")
            macro_text = ""

    if market == "crypto":
        sector_text = ""
    else:
        try:
            sector_text = _collect_sector(ticker, market, cutoff)
        except Exception as e:
            logger.warning(f"Sector collection failed for {ticker}: {e}")
            sector_text = ""

    parts = [p for p in [macro_text, sector_text] if p]
    return "\n\n".join(parts)
