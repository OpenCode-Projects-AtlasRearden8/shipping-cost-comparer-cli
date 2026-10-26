"""CSV storage for rate tables. Local files only, no network ever."""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .models import Rate

RATES_FILE = "rates.csv"

REQUIRED_COLUMNS = ("carrier", "service", "zone", "weight_lb", "base_price")
OPTIONAL_COLUMNS = ("insurance_per_100", "hand_min_days", "hand_max_days")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class StoreError(Exception):
    """User-facing storage problem."""


def default_data_dir() -> Path:
    env = os.environ.get("SHIPCOST_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.cwd() / "data"


def _clean_number(raw: Optional[str]) -> str:
    text = (raw or "").strip()
    return text.replace("$", "").replace(",", "")


def _to_float(raw: Optional[str], label: str, warnings: List[str], row_label: str) -> Optional[float]:
    text = _clean_number(raw)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        warnings.append(f"{row_label}: {label} is not a number ({text!r}), row skipped")
        return None


def _required_float(raw: Optional[str], label: str, warnings: List[str], row_label: str) -> Optional[float]:
    if _clean_number(raw) == "":
        warnings.append(f"{row_label}: missing {label}, row skipped")
        return None
    return _to_float(raw, label, warnings, row_label)


def parse_csv_text(
    text: str,
    source: str = "rate table",
    default_carrier: Optional[str] = None,
) -> Tuple[List[Rate], List[str]]:
    """Parse a carrier rate table. Returns (rates, warnings).

    Raises ValueError when the header is unusable. Warns (never crashes) for
    bad rows so a slightly messy paste still imports the good rows.
    """
    text = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError(f"{source} is empty (need a header row)")
    header = [h.strip().lower() for h in rows[0]]
    required = [c for c in REQUIRED_COLUMNS if not (c == "carrier" and default_carrier is not None)]
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(
            f"{source} is missing required column(s): {', '.join(missing)}. "
            f"Expected columns like: {', '.join(ALL_COLUMNS)}"
        )
    extra = [h for h in header if h not in ALL_COLUMNS]
    warnings: List[str] = []
    if extra:
        warnings.append(f"ignoring extra column(s): {', '.join(extra)}")
    idx = {name: i for i, name in enumerate(header)}
    rates: List[Rate] = []
    for n, values in enumerate(rows[1:], start=2):
        if not any((v or "").strip() for v in values):
            continue
        get = lambda col: values[idx[col]] if col in idx and idx[col] < len(values) else None
        if len(values) > len(header):
            warnings.append(f"row {n}: {len(values) - len(header)} extra value(s) compared to the header (check commas or quotes), row skipped")
            continue
        carrier = (get("carrier") or "").strip() or (default_carrier or "").strip()
        service = (get("service") or "").strip()
        zone = (get("zone") or "").strip()
        weight = _required_float(get("weight_lb"), "weight_lb", warnings, f"row {n}")
        price = _required_float(get("base_price"), "base_price", warnings, f"row {n}")
        if not carrier:
            warnings.append(f"row {n}: no carrier name (add a carrier column or use --carrier), row skipped")
            continue
        if weight is None or price is None:
            continue
        weight = max(0.0, weight)
        price = max(0.0, price)
        if not service or not zone:
            warnings.append(f"row {n}: missing service or zone, row skipped")
            continue
        if weight <= 0:
            warnings.append(f"row {n}: weight must be positive, row skipped")
            continue
        ins = _to_float(get("insurance_per_100"), "insurance_per_100", warnings, f"row {n}")
        hand_min = _to_float(get("hand_min_days"), "hand_min_days", warnings, f"row {n}")
        hand_max = _to_float(get("hand_max_days"), "hand_max_days", warnings, f"row {n}")
        if ins is None:
            ins = 0.0
        if ins < 0:
            ins = 0.0
        if hand_min is not None and hand_min < 0:
            hand_min = None
            warnings.append(f"row {n}: negative hand_min_days ignored")
        if hand_max is not None and hand_max < 0:
            hand_max = None
            warnings.append(f"row {n}: negative hand_max_days ignored")
        if hand_min is None and hand_max is not None:
            hand_min = hand_max
        if hand_max is None and hand_min is not None:
            hand_max = hand_min
        rates.append(
            Rate(
                carrier=carrier,
                service=service,
                zone=zone,
                weight_lb=weight,
                base_price=price,
                insurance_per_100=ins,
                hand_min_days=hand_min,
                hand_max_days=hand_max,
            )
        )
    return rates, warnings


class RateStore:
    """All rate rows live in one CSV file inside the data directory."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()

    @property
    def rates_path(self) -> Path:
        return self.data_dir / RATES_FILE

    def load(self) -> List[Rate]:
        if not self.rates_path.exists():
            return []
        text = self.rates_path.read_text(encoding="utf-8-sig")
        rates, warnings = parse_csv_text(text, source=str(self.rates_path))
        if warnings:
            raise StoreError(
                f"your rates file ({self.rates_path}) has problems:\n  "
                + "\n  ".join(warnings[:5])
                + "\nFix the file or run: shipcost import --replace ... / shipcost clear"
            )
        return rates

    def save(self, rates: Iterable[Rate]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        rows = sorted(
            rates,
            key=lambda r: (
                r.carrier.strip().lower(),
                r.service.strip().lower(),
                r.zone.strip().lower(),
                r.weight_lb,
                r.base_price,
            ),
        )
        tmp = self.rates_path.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(ALL_COLUMNS)
            for r in rows:
                writer.writerow(
                    [
                        r.carrier,
                        r.service,
                        r.zone,
                        r.weight_lb,
                        r.base_price,
                        r.insurance_per_100,
                        r.hand_min_days if r.hand_min_days is not None else "",
                        r.hand_max_days if r.hand_max_days is not None else "",
                    ]
                )
        tmp.replace(self.rates_path)

    def add(self, rates: Iterable[Rate], replace: bool = False) -> Tuple[int, int]:
        existing = [] if replace else self.load()
        seen = {r.dedupe_key for r in existing}
        merged = list(existing)
        added = skipped = 0
        for r in rates:
            key = r.dedupe_key
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            merged.append(r)
            added += 1
        self.save(merged)
        return added, skipped

    def clear(self) -> bool:
        if self.rates_path.exists():
            self.rates_path.unlink()
            return True
        return False
