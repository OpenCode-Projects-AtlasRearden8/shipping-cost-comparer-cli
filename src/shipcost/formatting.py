"""Plain-text output helpers. No network, no fancy dependencies."""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence


def fmt_money(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"${value:,.2f}"


def fmt_num(value: Optional[float]) -> str:
    if value is None:
        return "-"
    text = f"{round(value, 2):g}"
    return text


def fmt_days(min_days: Optional[float], max_days: Optional[float]) -> str:
    if min_days is None and max_days is None:
        return "-"
    lo = min_days if min_days is not None else max_days
    hi = max_days if max_days is not None else min_days
    if lo == hi:
        unit = "day" if lo == 1 else "days"
        return f"{fmt_num(lo)} {unit}"
    return f"{fmt_num(lo)}-{fmt_num(hi)} days"


def table(headers: Sequence[str], rows: Iterable[Sequence[str]], align: Optional[str] = None) -> str:
    """align: optional string like 'llrrll' - one letter per column, l or r."""
    data = [list(headers)] + [[str(c) for c in row] for row in rows]
    widths = [max(len(row[i]) if i < len(row) else 0 for row in data) for i in range(len(headers))]
    lines = []
    for n, row in enumerate(data):
        cells = []
        for i, width in enumerate(widths):
            cell = row[i] if i < len(row) else ""
            is_left = n == 0 or not (align and i < len(align) and align[i] == "r")
            cells.append(cell.ljust(width) if is_left else cell.rjust(width))
        lines.append("  ".join(cells).rstrip())
        if n == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)
