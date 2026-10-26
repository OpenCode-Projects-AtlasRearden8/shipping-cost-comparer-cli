"""Regenerate the bundled sample rate table. Numbers are fictional and stable."""
from __future__ import annotations

import csv
from pathlib import Path

HEADER = [
    "carrier",
    "service",
    "zone",
    "weight_lb",
    "base_price",
    "insurance_per_100",
    "hand_min_days",
    "hand_max_days",
]

GROUND = "Sample Parcel Co."
EXPRESS = "Sample Express Inc."

ZONES = ["Local", "1", "2", "3", "5", "8"]
WEIGHT_BREAKS = [1, 2, 3, 5, 10]

GROUND_ZONE_ADD = {"Local": -0.60, "1": 0.00, "2": 0.70, "3": 1.40, "5": 2.90, "8": 4.60}
EXPRESS_ZONE_ADD = {"Local": 0.00, "1": 0.30, "2": 1.20, "3": 2.40, "5": 3.90, "8": 5.40}

GROUND_STEPS = {1: 5.90, 2: 7.10, 3: 8.20, 5: 9.30, 10: 12.70}
EXPRESS_STEPS = {1: 12.90, 2: 15.40, 3: 17.00, 5: 19.10, 10: 22.60}

GROUND_HAND = {"Local": (2, 3), "1": (2, 4), "2": (3, 5), "3": (3, 6), "5": (3, 6), "8": (4, 7)}
EXPRESS_HAND = {"Local": (1, 2), "1": (1, 2), "2": (1, 2), "3": (1, 2), "5": (1, 2), "8": (2, 3)}

INSURANCE = {GROUND: 1.05, EXPRESS: 1.35}


def build_rows():
    rows = []
    for zone in ZONES:
        for weight in WEIGHT_BREAKS:
            rows.append(
                [
                    GROUND,
                    "Ground Value",
                    zone,
                    weight,
                    round(GROUND_STEPS[weight] + GROUND_ZONE_ADD[zone], 2),
                    INSURANCE[GROUND],
                    GROUND_HAND[zone][0],
                    GROUND_HAND[zone][1],
                ]
            )
            rows.append(
                [
                    EXPRESS,
                    "Priority Air",
                    zone,
                    weight,
                    round(EXPRESS_STEPS[weight] + EXPRESS_ZONE_ADD[zone], 2),
                    INSURANCE[EXPRESS],
                    EXPRESS_HAND[zone][0],
                    EXPRESS_HAND[zone][1],
                ]
            )
    return rows


def main():
    rows = build_rows()
    out = Path(__file__).resolve().parents[1] / "src" / "shipcost" / "examples"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "sample_rate_table.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main()
