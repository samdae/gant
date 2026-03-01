"""Exchange rate service with in-memory TTL cache."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Fetch USD/KRW exchange rate via yfinance with graceful fallback."""

    def __init__(
        self,
        ttl_seconds: Optional[int] = None,
        fallback_rate: Optional[float] = None,
    ):
        self.ttl_seconds = (
            int(ttl_seconds)
            if ttl_seconds is not None
            else int(os.getenv("EXCHANGE_RATE_CACHE_TTL", "3600"))
        )
        self.fallback_rate = (
            float(fallback_rate)
            if fallback_rate is not None
            else float(os.getenv("EXCHANGE_RATE_FALLBACK", "1380.0"))
        )
        self._cached_rate: Optional[float] = None
        self._cached_at: float = 0.0

    def _cache_valid(self) -> bool:
        if self._cached_rate is None:
            return False
        return (time.time() - self._cached_at) < max(self.ttl_seconds, 1)

    def get_usd_krw(self) -> float:
        if self._cache_valid():
            return float(self._cached_rate)

        errors = []
        for attempt in range(1, 3):
            try:
                import yfinance as yf

                data = yf.download(
                    tickers="USDKRW=X",
                    period="5d",
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                )
                if data is None or data.empty:
                    raise ValueError("empty response")
                close_val = data["Close"].iloc[-1]
                # yfinance may return a one-row Series for "Close" depending on shape.
                if hasattr(close_val, "iloc"):
                    close_val = close_val.iloc[-1]
                rate = float(close_val)
                if rate <= 0:
                    raise ValueError(f"non-positive rate: {rate}")
                self._cached_rate = rate
                self._cached_at = time.time()
                return rate
            except Exception as exc:
                errors.append(str(exc))
                logger.warning(
                    "USDKRW fetch failed (attempt %s/2): %s",
                    attempt,
                    exc,
                )

        if self._cached_rate is not None:
            logger.warning(
                "USDKRW fetch failed, using stale cached rate=%s (errors=%s)",
                self._cached_rate,
                errors,
            )
            return float(self._cached_rate)

        logger.warning(
            "USDKRW fetch failed, using fallback rate=%s (errors=%s)",
            self.fallback_rate,
            errors,
        )
        self._cached_rate = float(self.fallback_rate)
        self._cached_at = time.time()
        return float(self._cached_rate)
