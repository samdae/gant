"""Performance of executed virtual trades, grouped by their settlement currency."""
from collections import defaultdict
from operator import itemgetter
from itertools import groupby
from math import isclose, isfinite

from tradingagents.storage.trade_repo import closed_position_return
from pydantic import BaseModel, computed_field


class Performance(BaseModel):
    active_positions: int = 0
    closed_positions: int = 0
    wins: int = 0
    losses: int = 0
    incomplete_positions: int = 0
    unpriced_positions: int = 0
    total_realized_pnl: float = 0.0
    realized_cost: float = 0.0
    total_unrealized_pnl: float | None = 0.0
    open_cost: float = 0.0

    @computed_field
    @property
    def total_realized_return_pct(self) -> float:
        return 100 * self.total_realized_pnl / self.realized_cost if self.realized_cost else 0.0

    @computed_field
    @property
    def total_unrealized_return_pct(self) -> float | None:
        if self.total_unrealized_pnl is None:
            return None
        return 100 * self.total_unrealized_pnl / self.open_cost if self.open_cost else 0.0

    @computed_field
    @property
    def total_pnl(self) -> float | None:
        if self.total_unrealized_pnl is None:
            return None
        return self.total_realized_pnl + self.total_unrealized_pnl

    @computed_field
    @property
    def total_return_pct(self) -> float | None:
        cost = self.realized_cost + self.open_cost
        if self.total_pnl is None:
            return None
        return 100 * self.total_pnl / cost if cost else 0.0


def calculate_performance(rows, prices):
    """Consume position/fill rows in (position_id, executed_at, trade_id) order.

    Use the moving-average cost at each sale. A missing closing fill or an
    administrative reset produces no proceeds. For a legacy oversell only the
    quantity with an observed purchase has a measurable gain/loss.
    """
    currencies = defaultdict(Performance)
    for _, grouped in groupby(rows, key=itemgetter("id")):
        fills = list(grouped)
        position = fills[0]
        stats = currencies[position["currency"]]
        on_hand = cost = 0.0
        incomplete = False
        for fill in fills:
            if fill["action"] not in ("BUY", "SELL"):
                continue
            qty, price = fill["fill_shares"], fill["price"]
            if not qty or not price or not isfinite(qty) or not isfinite(price) or min(qty, price) <= 0:
                incomplete = True
                continue
            if fill["fill_currency"] != position["currency"]:
                incomplete = True
                continue
            if fill["action"] == "BUY":
                on_hand += qty
                cost += qty * price
            else:
                matched = min(qty, on_hand)
                basis = matched * cost / on_hand if on_hand else 0.0
                stats.realized_cost += basis
                stats.total_realized_pnl += matched * price - basis
                incomplete |= qty - matched > 1e-8
                on_hand -= matched
                cost -= basis

        status = position["status"]
        if status == "closed":
            stats.closed_positions += 1
            lifecycle_return = closed_position_return(
                (dict(action=f["action"], price=f["price"], shares=f["fill_shares"], currency=f["fill_currency"])
                 for f in fills), position["currency"],
            )
            if lifecycle_return is None:
                incomplete = True
            else:
                stats.wins += int(lifecycle_return >= 0)
                stats.losses += int(lifecycle_return < 0)
        elif status == "active":
            stats.active_positions += 1
            shares = position["shares"]
            incomplete |= not isclose(on_hand, shares, abs_tol=1e-8)
            if shares > 0:
                price = prices.get(position["ticker"])
                basis = position["avg_cost"]
                if not basis or not isfinite(basis) or basis < 0 or not price or not isfinite(price) or price < 0:
                    stats.unpriced_positions += 1
                    stats.total_unrealized_pnl = None
                else:
                    stats.open_cost += basis * shares
                    if stats.total_unrealized_pnl is not None:
                        stats.total_unrealized_pnl += (price - basis) * shares
        stats.incomplete_positions += int(incomplete)
    return dict(currencies)
