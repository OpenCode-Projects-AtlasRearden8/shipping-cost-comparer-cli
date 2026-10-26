"""Resale margin math: fold the landed ship cost into profit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MarginResult:
    sell: float
    item_cost: float
    packaging: float
    ship: float
    fee_pct: float
    fee_dollars: float
    costs: float
    profit: float
    margin_pct: Optional[float]
    roi_pct: Optional[float]
    breakeven_sell: Optional[float]


def margin(
    sell: float,
    item_cost: float = 0.0,
    ship: float = 0.0,
    packaging: float = 0.0,
    fee_pct: float = 0.0,
) -> MarginResult:
    """fee_pct applies to the sale price (marketplace cut, payment fees, taxes you pay on the sale)."""
    fee_dollars = sell * (fee_pct / 100.0)
    costs = item_cost + ship + packaging
    profit = sell - costs - fee_dollars
    margin_pct = profit / sell if sell > 0 else None
    if costs > 0:
        roi_pct = profit / costs
    else:
        roi_pct = None
    if fee_pct < 100.0:
        breakeven_sell = costs / (1.0 - fee_pct / 100.0)
    else:
        breakeven_sell = None
    return MarginResult(
        sell=round(sell, 2),
        item_cost=round(item_cost, 2),
        packaging=round(packaging, 2),
        ship=round(ship, 2),
        fee_pct=fee_pct,
        fee_dollars=round(fee_dollars, 2),
        costs=round(costs, 2),
        profit=round(profit, 2),
        margin_pct=margin_pct,
        roi_pct=roi_pct,
        breakeven_sell=breakeven_sell,
    )
