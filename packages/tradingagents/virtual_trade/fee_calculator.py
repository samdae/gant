"""Market-aware trading fee calculator for portfolio mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class FeeResult:
    rate: float
    amount: float


class FeeCalculator:
    """Calculate fee amount from market/action and configured rates."""

    DEFAULT_RATES = {
        "us_fee_rate": 0.001,
        "kr_buy_fee_rate": 0.0025,
        "kr_sell_fee_rate": 0.0025,
        "kr_sell_tax_rate": 0.0018,
        "crypto_fee_rate": 0.001,
    }

    def calculate(
        self,
        market: str,
        action: str,
        amount: float,
        config: Optional[Dict[str, Any]] = None,
    ) -> FeeResult:
        if amount <= 0:
            return FeeResult(rate=0.0, amount=0.0)

        action_norm = str(action or "").strip().lower()
        if action_norm not in {"buy", "sell"}:
            return FeeResult(rate=0.0, amount=0.0)

        cfg = config or {}
        fee_enabled = bool(cfg.get("fee_enabled", True))
        if not fee_enabled:
            return FeeResult(rate=0.0, amount=0.0)

        def _rate(name: str) -> float:
            raw = cfg.get(name, self.DEFAULT_RATES[name])
            try:
                return max(float(raw), 0.0)
            except (TypeError, ValueError):
                return self.DEFAULT_RATES[name]

        market_norm = str(market or "us").strip().lower()
        if market_norm == "kr":
            if action_norm == "buy":
                rate = _rate("kr_buy_fee_rate")
            else:
                rate = _rate("kr_sell_fee_rate") + _rate("kr_sell_tax_rate")
        elif market_norm == "crypto":
            rate = _rate("crypto_fee_rate")
        else:
            rate = _rate("us_fee_rate")

        fee_amount = float(amount) * float(rate)
        return FeeResult(rate=rate, amount=fee_amount)
