"""Portfolio configuration repository."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .database import Database

logger = logging.getLogger(__name__)


DEFAULT_FEE_RATES = {
    "us_fee_rate": 0.001,
    "kr_buy_fee_rate": 0.0025,
    "kr_sell_fee_rate": 0.0025,
    "kr_sell_tax_rate": 0.0018,
    "crypto_fee_rate": 0.001,
}


class PortfolioConfigRepository:
    """Repository for `portfolio_configs` table."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _normalize_base_currency(value: str | None) -> str:
        currency = (value or "KRW").upper().strip()
        return currency if currency in {"KRW", "USD"} else "KRW"

    @staticmethod
    def _normalize_fee_rates(fee_rates: Optional[Dict[str, Any]]) -> Dict[str, float]:
        rates = dict(DEFAULT_FEE_RATES)
        if not fee_rates:
            return rates
        for key in DEFAULT_FEE_RATES.keys():
            raw = fee_rates.get(key)
            if raw is None:
                continue
            try:
                parsed = float(raw)
            except (TypeError, ValueError):
                continue
            rates[key] = max(parsed, 0.0)
        return rates

    def create(
        self,
        initial_capital: float,
        base_currency: str = "KRW",
        fee_enabled: bool = True,
        fee_rates: Optional[Dict[str, Any]] = None,
        name: str = "default",
        status: str = "active",
        commit: bool = True,
        conn=None,
    ) -> int:
        initial_capital = float(initial_capital)
        if initial_capital <= 0:
            raise ValueError("initial_capital must be greater than 0")

        now = datetime.now().isoformat()
        rates = self._normalize_fee_rates(fee_rates)
        currency = self._normalize_base_currency(base_currency)
        status = status if status in {"active", "paused"} else "active"
        connection = conn or self.db.get_connection()

        cursor = connection.execute(
            """
            INSERT INTO portfolio_configs (
                name, initial_capital, total_fund, available_cash,
                base_currency, fee_enabled,
                us_fee_rate, kr_buy_fee_rate, kr_sell_fee_rate,
                kr_sell_tax_rate, crypto_fee_rate,
                status, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            RETURNING id
            """,
            (
                name,
                initial_capital,
                initial_capital,
                initial_capital,
                currency,
                bool(fee_enabled),
                rates["us_fee_rate"],
                rates["kr_buy_fee_rate"],
                rates["kr_sell_fee_rate"],
                rates["kr_sell_tax_rate"],
                rates["crypto_fee_rate"],
                status,
                now,
                now,
            ),
        )
        if commit:
            connection.commit()
        row = cursor.fetchone()
        config_id = int(row["id"]) if row else 0
        logger.info("Created portfolio_config %s", config_id)
        return config_id

    def get_by_id(self, config_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.get_connection().execute(
            """
            SELECT id, name, initial_capital, total_fund, available_cash,
                   base_currency, fee_enabled,
                   us_fee_rate, kr_buy_fee_rate, kr_sell_fee_rate,
                   kr_sell_tax_rate, crypto_fee_rate,
                   status, created_at, updated_at
            FROM portfolio_configs
            WHERE id = %s
            LIMIT 1
            """,
            (config_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_latest(self) -> Optional[Dict[str, Any]]:
        row = self.db.get_connection().execute(
            """
            SELECT id, name, initial_capital, total_fund, available_cash,
                   base_currency, fee_enabled,
                   us_fee_rate, kr_buy_fee_rate, kr_sell_fee_rate,
                   kr_sell_tax_rate, crypto_fee_rate,
                   status, created_at, updated_at
            FROM portfolio_configs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None

    def get_active(self) -> Optional[Dict[str, Any]]:
        row = self.db.get_connection().execute(
            """
            SELECT id, name, initial_capital, total_fund, available_cash,
                   base_currency, fee_enabled,
                   us_fee_rate, kr_buy_fee_rate, kr_sell_fee_rate,
                   kr_sell_tax_rate, crypto_fee_rate,
                   status, created_at, updated_at
            FROM portfolio_configs
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None

    def update_settings(
        self,
        config_id: int,
        initial_capital: Optional[float] = None,
        base_currency: Optional[str] = None,
        fee_enabled: Optional[bool] = None,
        fee_rates: Optional[Dict[str, Any]] = None,
        reset_fund_to_initial: bool = False,
        commit: bool = True,
        conn=None,
    ) -> Optional[Dict[str, Any]]:
        existing = self.get_by_id(config_id)
        if not existing:
            return None

        now = datetime.now().isoformat()
        rates = self._normalize_fee_rates(
            {
                "us_fee_rate": existing.get("us_fee_rate"),
                "kr_buy_fee_rate": existing.get("kr_buy_fee_rate"),
                "kr_sell_fee_rate": existing.get("kr_sell_fee_rate"),
                "kr_sell_tax_rate": existing.get("kr_sell_tax_rate"),
                "crypto_fee_rate": existing.get("crypto_fee_rate"),
                **(fee_rates or {}),
            }
        )
        next_initial = (
            float(initial_capital)
            if initial_capital is not None
            else float(existing.get("initial_capital") or 0.0)
        )
        if next_initial <= 0:
            raise ValueError("initial_capital must be greater than 0")

        next_currency = self._normalize_base_currency(
            base_currency or str(existing.get("base_currency") or "KRW")
        )
        next_fee_enabled = (
            bool(fee_enabled)
            if fee_enabled is not None
            else bool(existing.get("fee_enabled"))
        )
        next_total_fund = (
            next_initial
            if reset_fund_to_initial
            else float(existing.get("total_fund") or next_initial)
        )
        next_available_cash = (
            next_initial
            if reset_fund_to_initial
            else float(existing.get("available_cash") or next_initial)
        )

        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE portfolio_configs
            SET initial_capital = %s,
                total_fund = %s,
                available_cash = %s,
                base_currency = %s,
                fee_enabled = %s,
                us_fee_rate = %s,
                kr_buy_fee_rate = %s,
                kr_sell_fee_rate = %s,
                kr_sell_tax_rate = %s,
                crypto_fee_rate = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                next_initial,
                next_total_fund,
                next_available_cash,
                next_currency,
                next_fee_enabled,
                rates["us_fee_rate"],
                rates["kr_buy_fee_rate"],
                rates["kr_sell_fee_rate"],
                rates["kr_sell_tax_rate"],
                rates["crypto_fee_rate"],
                now,
                config_id,
            ),
        )
        if commit:
            connection.commit()
        return self.get_by_id(config_id)

    def upsert_default(
        self,
        initial_capital: float,
        base_currency: str = "KRW",
        fee_enabled: bool = True,
        fee_rates: Optional[Dict[str, Any]] = None,
        reset_fund_to_initial: bool = True,
        commit: bool = True,
        conn=None,
    ) -> Dict[str, Any]:
        existing = self.get_latest()
        if existing:
            updated = self.update_settings(
                existing["id"],
                initial_capital=initial_capital,
                base_currency=base_currency,
                fee_enabled=fee_enabled,
                fee_rates=fee_rates,
                reset_fund_to_initial=reset_fund_to_initial,
                commit=commit,
                conn=conn,
            )
            if not updated:
                raise RuntimeError("Failed to update portfolio config")
            return updated

        config_id = self.create(
            initial_capital=initial_capital,
            base_currency=base_currency,
            fee_enabled=fee_enabled,
            fee_rates=fee_rates,
            commit=commit,
            conn=conn,
        )
        created = self.get_by_id(config_id)
        if not created:
            raise RuntimeError("Failed to create portfolio config")
        return created

    def update_fund(
        self,
        config_id: int,
        total_fund: float,
        available_cash: float,
        commit: bool = True,
        conn=None,
    ) -> None:
        now = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE portfolio_configs
            SET total_fund = %s,
                available_cash = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                float(total_fund),
                max(float(available_cash), 0.0),
                now,
                config_id,
            ),
        )
        if commit:
            connection.commit()

    def pause(self, config_id: int, commit: bool = True, conn=None) -> None:
        now = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE portfolio_configs
            SET status = 'paused', updated_at = %s
            WHERE id = %s
            """,
            (now, config_id),
        )
        if commit:
            connection.commit()

    def resume(self, config_id: int, commit: bool = True, conn=None) -> None:
        now = datetime.now().isoformat()
        connection = conn or self.db.get_connection()
        connection.execute(
            """
            UPDATE portfolio_configs
            SET status = 'active', updated_at = %s
            WHERE id = %s
            """,
            (now, config_id),
        )
        if commit:
            connection.commit()
