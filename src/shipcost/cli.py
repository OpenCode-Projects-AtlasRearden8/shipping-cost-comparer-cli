"""Command line interface. Every command is local: files in, files out."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

from importlib.resources import as_file, files

from . import __version__
from .formatting import fmt_days, fmt_money, fmt_num, table
from .margin import margin
from .models import Rate, Shipment
from .pricing import DIM_DIVISOR_DEFAULT, billed_weight, options_for, parse_dims
from .store import RateStore, StoreError, parse_csv_text


def _sample_table_text() -> str:
    resource = files("shipcost") / "examples" / "sample_rate_table.csv"
    with as_file(resource) as path:
        return Path(path).read_text(encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shipcost",
        description=(
            "Reseller shipping cost comparer. Import your carrier's published rate "
            "tables as CSV (or paste them), compare options with insurance and "
            "handling-time columns, fold the landed cost into resale margins, and "
            "print a ready-to-brain cheat card. Local CSV storage only - no scraping, no accounts."
        ),
    )
    parser.add_argument("--version", action="version", version=f"shipcost {__version__}")
    parser.add_argument(
        "--data-dir",
        default=None,
        metavar="DIR",
        help="folder for local CSV storage (default: ./data, or $SHIPCOST_DATA_DIR)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_import = sub.add_parser(
        "import",
        help="import a carrier rate table from a CSV file or paste it",
        description="Import published rate rows into your local rates.csv. Re-importing the same rows is safe: duplicates are skipped.",
    )
    src = p_import.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", metavar="CSV", help="path to a rate table CSV ('-' reads stdin)")
    src.add_argument("--paste", action="store_true", help="paste the table; end with Ctrl-D (Ctrl-Z then Enter on Windows)")
    p_import.add_argument("--carrier", default=None, help="carrier name to fill in when rows do not include one (also overrides per-row carriers)")
    p_import.add_argument("--replace", action="store_true", help="replace the entire rates file instead of adding to it")

    p_rates = sub.add_parser("rates", help="list the rate rows you have stored")
    p_rates.add_argument("--carrier", default=None, help="show one carrier only")
    p_rates.add_argument("--zone", default=None, help="show one zone only")

    sub.add_parser("zones", help="list zones in your rates file")
    sub.add_parser("where", help="show where your data lives")

    p_compare = sub.add_parser(
        "compare",
        help="compare shipping options for one package",
        description="Picks the smallest published weight break that covers the billed weight, adds insurance and extras, and ranks by landed cost.",
    )
    p_compare.add_argument("--weight", type=float, required=True, metavar="LB", help="actual package weight in pounds")
    p_compare.add_argument("--dims", default=None, metavar="LxWxH", help="package size in inches, like 12x9x4")
    p_compare.add_argument("--divisor", type=float, default=DIM_DIVISOR_DEFAULT, metavar="N", help=f"dimensional-weight divisor (default {DIM_DIVISOR_DEFAULT:g})")
    p_compare.add_argument("--zone", required=True, default=None, help="zone to price, as written in your rate table (like 5)")
    p_compare.add_argument("--value", type=float, default=0.0, metavar="USD", help="declared value for insurance")
    p_compare.add_argument("--extras", type=float, default=0.0, metavar="USD", help="per-piece extras to roll in (mailer, tape, label)")
    p_compare.add_argument("--top", type=int, default=8, metavar="N", help="how many options to show (default 8)")
    p_compare.add_argument("--card", action="store_true", help="also print a ready-to-brain cheat card")
    p_compare.add_argument("--sell", type=float, default=None, metavar="USD", help="planned sale price; adds a Profit column")
    p_compare.add_argument("--item-cost", type=float, default=0.0, metavar="USD", dest="item_cost", help="what you paid for the item (used with --sell)")
    p_compare.add_argument("--packaging", type=float, default=0.0, metavar="USD", help="packaging cost (used with --sell)")
    p_compare.add_argument("--fee-pct", type=float, default=0.0, metavar="PCT", dest="fee_pct", help="marketplace fee percent of the sale price (used with --sell)")

    p_margin = sub.add_parser("margin", help="resale margin calculator")
    p_margin.add_argument("--sell", type=float, required=True, metavar="USD", help="sale price")
    p_margin.add_argument("--ship", type=float, default=0.0, metavar="USD", help="landed ship cost (from compare)")
    p_margin.add_argument("--item-cost", type=float, default=0.0, metavar="USD", dest="item_cost", help="what you paid for the item")
    p_margin.add_argument("--packaging", type=float, default=0.0, metavar="USD", help="packaging cost")
    p_margin.add_argument("--fee-pct", type=float, default=0.0, metavar="PCT", dest="fee_pct", help="marketplace fee percent of sale price")

    p_card = sub.add_parser("card", help="print an empty cheat card to fill in by hand")
    p_card.add_argument("--weight", default=None, metavar="LB", help="optional: prefill weight")

    sub.add_parser("demo", help="install the bundled sample rate table so you can try everything")

    p_clear = sub.add_parser("clear", help="delete your local rates.csv (asks to confirm)")
    p_clear.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    return parser


def _hand_cell(rate: Rate) -> str:
    return fmt_days(rate.hand_min_days, rate.hand_max_days)


def cmd_import(args, store: RateStore) -> int:
    if args.paste:
        print("Paste your rate table CSV, then press Ctrl-D (Ctrl-Z then Enter on Windows) to finish:", file=sys.stderr)
        text = sys.stdin.read()
        source = "pasted table"
    else:
        if args.file == "-":
            text = sys.stdin.read()
            source = "stdin table"
        else:
            text = Path(args.file).read_text(encoding="utf-8-sig")
            source = str(args.file)
    rates, warnings = parse_csv_text(text, source=source, default_carrier=args.carrier)
    if args.carrier:
        rates = [
            Rate(
                carrier=args.carrier,
                service=r.service,
                zone=r.zone,
                weight_lb=r.weight_lb,
                base_price=r.base_price,
                insurance_per_100=r.insurance_per_100,
                hand_min_days=r.hand_min_days,
                hand_max_days=r.hand_max_days,
            )
            for r in rates
        ]
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if not rates:
        print(f"error: nothing importable found in {source}", file=sys.stderr)
        return 2
    added, skipped = store.add(rates, replace=args.replace)
    print(f"Imported from {source}")
    print(f"  added   {added} rate row(s)" + (" (replaced everything)" if args.replace else ""))
    print(f"  skipped {skipped} duplicate row(s)")
    print("Next: shipcost rates | shipcost zones | shipcost compare --weight 2 --zone 5 --value 45")
    return 0


def cmd_rates(args, store: RateStore) -> int:
    rates = store.load()
    if not rates:
        print("No rate rows yet. Try: shipcost demo   or   shipcost import --file your_rates.csv")
        return 1
    shown = rates
    if args.carrier:
        shown = [r for r in shown if r.carrier.strip().lower() == args.carrier.strip().lower()]
    if args.zone:
        shown = [r for r in shown if r.zone.strip().lower() == args.zone.strip().lower()]
    if not shown:
        print("No rows match those filters. Try: shipcost zones")
        return 0
    rows = [
        [
            r.carrier,
            r.service,
            r.zone,
            f"{fmt_num(r.weight_lb)} lb",
            fmt_money(r.base_price),
            fmt_money(r.insurance_per_100) if r.insurance_per_100 else "-",
            _hand_cell(r),
        ]
        for r in shown
    ]
    print(table(["Carrier", "Service", "Zone", "Up to", "Base", "Ins/$100", "Handling"], rows, "lllrrrl"))
    print(f"{len(shown)} of {len(rates)} row(s). Ins/$100 = fee added per $100 of declared value.")
    return 0


def cmd_zones(args, store: RateStore) -> int:
    rates = store.load()
    if not rates:
        print("No rate rows yet. Try: shipcost demo")
        return 1
    zones: dict = {}
    for r in rates:
        zones[r.zone] = zones.get(r.zone, 0) + 1

    def zone_sort_key(z: str):
        try:
            return (0, float(z), "")
        except ValueError:
            return (1, 0.0, z)

    print("Zones in your rates file:")
    for z in sorted(zones, key=zone_sort_key):
        print(f"  {z}  ({zones[z]} row(s))")
    return 0


def cmd_where(args, store: RateStore) -> int:
    exists = "exists" if store.rates_path.exists() else "not created yet"
    print(f"data dir   : {store.data_dir}")
    print(f"rates file : {store.rates_path} ({exists})")
    print("Everything stays in that folder. No network, no scraping, no accounts.")
    return 0


def cmd_compare(args, store: RateStore) -> int:
    rates = store.load()
    if not rates:
        print("No rates stored yet. Try: shipcost demo   or   shipcost import --file your_rates.csv", file=sys.stderr)
        return 1
    dims = parse_dims(args.dims) if args.dims else None
    for value, label in ((args.weight, "--weight"), (args.value, "--value"), (args.extras, "--extras")):
        if value < 0:
            print(f"error: {label} cannot be negative", file=sys.stderr)
            return 2
    if args.sell is not None and args.sell < 0:
        print("error: --sell cannot be negative", file=sys.stderr)
        return 2
    try:
        billed = billed_weight(args.weight, dims, args.divisor)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    shipment = Shipment(
        weight_lb=args.weight,
        dims=dims,
        divisor=args.divisor,
        zone=args.zone,
        declared_value=args.value,
        extras=args.extras,
    )
    opts = options_for(rates, shipment, top=args.top)
    if not opts:
        print(
            f"No rows in your rates file cover zone '{args.zone}' at {fmt_num(billed)} lb billed. "
            "Check the zone and weight. Try: shipcost zones",
            file=sys.stderr,
        )
        return 1
    print(f"Package: {fmt_num(args.weight)} lb actual | {fmt_num(billed)} lb billed", end="")
    if dims:
        print(f" | dims {args.dims} in (divisor {fmt_num(args.divisor)})", end="")
    print()
    print(f"Zone '{shipment.zone}' | declared {fmt_money(shipment.declared_value)} | extras {fmt_money(shipment.extras)}")
    if args.sell is not None:
        print(
            f"Sale plan: sell {fmt_money(args.sell)} | item {fmt_money(args.item_cost)} | "
            f"packaging {fmt_money(args.packaging)} | fees {args.fee_pct:g}%"
        )
    print()
    headers = ["#", "Carrier", "Service", "Break", "Landed", "Ins", "Handling"]
    align = "rllrrrl"
    rows = []
    for i, o in enumerate(opts, start=1):
        row = [
            str(i),
            o.rate.carrier,
            o.rate.service,
            f"{fmt_num(o.rate.weight_lb)} lb",
            fmt_money(o.landed),
            fmt_money(o.insurance) if o.insurance else "-",
            _hand_cell(o.rate),
        ]
        if args.sell is not None:
            profit = margin(
                sell=args.sell,
                item_cost=args.item_cost,
                ship=o.landed,
                packaging=args.packaging,
                fee_pct=args.fee_pct,
            ).profit
            row.append(fmt_money(profit))
        rows.append(row)
    if args.sell is not None:
        headers.append("Profit")
        align += "r"
    print(table(headers, rows, align))
    print("Landed = published base + insurance (per $100 of declared value) + extras.")
    if args.card:
        print()
        print(_cheat_card(shipment, opts, args, billed))
    return 0


def _cheat_card(shipment: Shipment, opts, args, billed: float) -> str:
    lines: List[str] = []
    width = 78
    lines.append("=" * width)
    lines.append(" SHIP DAY CHEAT CARD".center(width))
    lines.append("=" * width)
    lines.append(f"date     : {date.today().isoformat()}")
    if shipment.dims:
        lines.append(f"package  : {fmt_num(shipment.weight_lb)} lb actual | {fmt_num(billed)} lb billed | dims {args.dims} in")
    else:
        lines.append(f"package  : {fmt_num(shipment.weight_lb)} lb actual | {fmt_num(billed)} lb billed")
    lines.append(f"zone     : {shipment.zone}   declared: {fmt_money(shipment.declared_value)}   extras: {fmt_money(shipment.extras)}")
    lines.append("")
    lines.append("top picks (landed = base + insurance + extras):")
    for i, o in enumerate(opts[:5], start=1):
        name = f"{o.rate.carrier} {o.rate.service}"
        lines.append(f" [{i}] {name[:44]:<44} {fmt_money(o.landed):>9}   handling {_hand_cell(o.rate)}")
    best = opts[0]
    lines.append("")
    lines.append("margin plan (fill in what is missing, or run shipcost margin):")
    if args.sell is not None:
        m = margin(
            sell=args.sell,
            item_cost=args.item_cost,
            ship=best.landed,
            packaging=args.packaging,
            fee_pct=args.fee_pct,
        )
        lines.append(f"    sold for: {fmt_money(m.sell)}   landed (best): {fmt_money(m.ship)}")
        lines.append(f"    profit  : {fmt_money(m.profit)}   margin: {_pct(m.margin_pct)}   ROI: {_pct(m.roi_pct)}")
    else:
        lines.append(f"    sold for: $_______   landed (best): {fmt_money(best.landed)}")
        lines.append("    profit  : $_______   margin: ____%   ROI: ____%")
    lines.append("")
    lines.append("notes: " + "_" * 50)
    lines.append("")
    lines.append("From your local rate tables - nothing was scraped. Re-check prices after carrier updates.")
    lines.append("=" * width)
    return "\n".join(lines)


def _pct(value: Optional[float]) -> str:
    return f"{value * 100:.1f}%" if value is not None else "-"


def cmd_margin(args, store: RateStore) -> int:
    for value, label in ((args.sell, "--sell"), (args.ship, "--ship"), (args.item_cost, "--item-cost"), (args.packaging, "--packaging")):
        if value < 0:
            print(f"error: {label} cannot be negative", file=sys.stderr)
            return 2
    if not 0 <= args.fee_pct < 100:
        print("error: --fee-pct must be between 0 and 99.99", file=sys.stderr)
        return 2
    m = margin(sell=args.sell, item_cost=args.item_cost, ship=args.ship, packaging=args.packaging, fee_pct=args.fee_pct)
    print("Resale margin check")
    print(f"  sale price       {fmt_money(m.sell)}")
    print(f"  item cost        {fmt_money(m.item_cost)}")
    print(f"  packaging        {fmt_money(m.packaging)}")
    print(f"  landed ship cost {fmt_money(m.ship)}")
    print(f"  marketplace fees {fmt_money(m.fee_dollars)}  ({m.fee_pct:g}% of sale)")
    print(f"  total costs      {fmt_money(m.costs)}")
    print(f"  profit           {fmt_money(m.profit)}")
    print(f"  margin of sale   {_pct(m.margin_pct)}")
    print(f"  ROI on costs     {_pct(m.roi_pct)}")
    if m.breakeven_sell is not None:
        print(f"  break-even sale  {fmt_money(m.breakeven_sell)}")
    return 0


def cmd_card(args, store: RateStore) -> int:
    width = 78
    print("=" * width)
    print(" SHIP DAY CHEAT CARD (blank - fill in with a pen)".center(width))
    print("=" * width)
    print(f"date     : {date.today().isoformat()}")
    weight_note = f" {args.weight} lb" if args.weight else "  ____ lb"
    print(f"package  :{weight_note} | billed ____ lb | dims ___x___x___ in")
    print("zone     : ____   declared: $______.____   extras: $______.____")
    print()
    print("top picks (landed = base + insurance + extras):")
    print(" [1] " + "_" * 30 + "     $______.____   handling ____ days")
    print(" [2] " + "_" * 30 + "     $______.____   handling ____ days")
    print(" [3] " + "_" * 30 + "     $______.____   handling ____ days")
    print()
    print("margin plan:")
    print("    sold for: $______.____   landed (best pick): $______.____")
    print("    item cost: $______.____   packaging: $______.____   fees: ____%")
    print("    profit: $______.____   margin: ____%   ROI: ____%")
    print()
    print("notes: " + "_" * 50)
    print()
    print("tip: cheapest landed is not always fastest. match handling time to your")
    print("buyer promise, then keep the top pick on the card for quick reruns.")
    print("=" * width)
    return 0


def cmd_demo(args, store: RateStore) -> int:
    text = _sample_table_text()
    rates, warnings = parse_csv_text(text, source="bundled sample table")
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    added, skipped = store.add(rates)
    print(f"Demo rates installed: added {added} row(s), skipped {skipped} duplicate(s).")
    print("Sample carriers are fictional. For real pricing, import your carrier's published table.")
    print()
    print("Try it:")
    print("  shipcost rates")
    print("  shipcost compare --weight 2 --dims 12x9x4 --zone 5 --value 45 --sell 46 --item-cost 12 --fee-pct 13.25 --card")
    print()
    print("When you are done exploring: shipcost clear   then import your real table.")
    return 0


def cmd_clear(args, store: RateStore) -> int:
    if not args.yes and store.rates_path.exists():
        answer = input(f"Delete {store.rates_path}? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Cancelled. Your rates file is untouched.")
            return 0
    removed = store.clear()
    if removed:
        print("Rates file deleted. Your other files were not touched.")
    else:
        print("Nothing to clear - no rates file found.")
    return 0


HANDLERS = {
    "import": cmd_import,
    "rates": cmd_rates,
    "zones": cmd_zones,
    "where": cmd_where,
    "compare": cmd_compare,
    "margin": cmd_margin,
    "card": cmd_card,
    "demo": cmd_demo,
    "clear": cmd_clear,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = RateStore(data_dir=Path(args.data_dir).expanduser() if args.data_dir else None)
    try:
        return HANDLERS[args.cmd](args, store)
    except (StoreError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def run() -> int:
    try:
        return main()
    except KeyboardInterrupt:
        print("\nInterrupted - your local files are safe.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(run())
