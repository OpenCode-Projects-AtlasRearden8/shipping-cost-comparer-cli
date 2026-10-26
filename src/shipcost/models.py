"""Data types shared across shipcost."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Rate:
    """One published price row: carrier/service/zone covered up to weight_lb."""

    carrier: str
    service: str
    zone: str
    weight_lb: float
    base_price: float
    insurance_per_100: float = 0.0
    hand_min_days: Optional[float] = None
    hand_max_days: Optional[float] = None

    @property
    def dedupe_key(self) -> tuple:
        return (
            self.carrier.strip().lower(),
            self.service.strip().lower(),
            self.zone.strip().lower(),
            round(self.weight_lb, 3),
            round(self.base_price, 3),
            round(self.insurance_per_100, 3),
            round(self.hand_min_days, 3) if self.hand_min_days is not None else None,
            round(self.hand_max_days, 3) if self.hand_max_days is not None else None,
        )


@dataclass(frozen=True)
class Shipment:
    """One package the user wants to price out."""

    weight_lb: float
    dims: Optional[Tuple[float, float, float]]
    divisor: float
    zone: str
    declared_value: float
    extras: float


@dataclass(frozen=True)
class Option:
    """A comparable shipping choice for a shipment."""

    rate: Rate
    billed_weight: float
    insurance: float
    landed: float
