"""Billed weight, insurance, landed cost, and option ranking."""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from .models import Option, Rate, Shipment

DIM_DIVISOR_DEFAULT = 139.0
_BIG_DAYS = 9999.0


def parse_dims(text: str) -> Tuple[float, float, float]:
    parts = text.strip().lower().split("x")
    if len(parts) != 3:
        raise ValueError(f"dims must look like 12x9x4 (got {text!r})")
    try:
        l, w, h = (float(p.strip()) for p in parts)
    except ValueError:
        raise ValueError(f"dims must be three numbers like 12x9x4 (got {text!r})")
    if l <= 0 or w <= 0 or h <= 0:
        raise ValueError("dims must all be positive numbers")
    return (l, w, h)


def _ceil_cents(value: float) -> float:
    return math.ceil(value * 100.0 - 1e-9) / 100.0


def billed_weight(weight_lb: float, dims: Optional[Tuple[float, float, float]], divisor: float) -> float:
    """Carriers often bill the larger of actual and dimensional weight."""
    actual = max(0.0, weight_lb)
    billed = actual
    if dims:
        l, w, h = dims
        if divisor <= 0:
            raise ValueError("dim divisor must be positive (try 139 or 166)")
        dim = (l * w * h) / divisor
        billed = max(actual, dim)
    return _ceil_cents(billed)


def insurance_fee(rate: Rate, declared_value: float) -> float:
    """Published-style fee: charged per full or partial $100 of coverage."""
    if declared_value <= 0 or rate.insurance_per_100 <= 0:
        return 0.0
    units = math.ceil(declared_value / 100.0 - 1e-9)
    return round(units * rate.insurance_per_100, 2)


def _hand_days(rate: Rate) -> float:
    if rate.hand_max_days is not None:
        return rate.hand_max_days
    return _BIG_DAYS


def options_for(rates: Sequence[Rate], shipment: Shipment, top: int = 8) -> List[Option]:
    """Rank choices for one shipment: cheapest landed first, then fastest."""
    zone = shipment.zone.strip().lower()
    billed = billed_weight(shipment.weight_lb, shipment.dims, shipment.divisor)
    eligible = [
        r
        for r in rates
        if r.zone.strip().lower() == zone and r.weight_lb >= billed - 1e-9
    ]
    best: dict = {}
    for r in eligible:
        ins = insurance_fee(r, shipment.declared_value)
        landed = round(r.base_price + ins + shipment.extras, 2)
        opt = Option(rate=r, billed_weight=billed, insurance=ins, landed=landed)
        key = (r.carrier.strip().lower(), r.service.strip().lower())
        current = best.get(key)
        rank = (opt.landed, r.weight_lb, _hand_days(r), r.base_price)
        current_rank = (
            (current.landed, current.rate.weight_lb, _hand_days(current.rate), current.rate.base_price)
            if current is not None
            else None
        )
        if current_rank is None or rank < current_rank:
            best[key] = opt
    ranked = sorted(
        best.values(),
        key=lambda o: (o.landed, _hand_days(o.rate), o.rate.carrier.lower(), o.rate.service.lower()),
    )
    return ranked[: max(0, top)]
