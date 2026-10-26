# ShipCost — reseller shipping cost comparer

Compare your **published carrier rate tables** side by side, add insurance and
handling time to the picture, fold the landed ship cost straight into your
resale margin, and print a one-page cheat card your future self can actually use
at the shipping station.

**Zero scraping, zero accounts, zero cloud.** You provide the rate tables as CSV
(download them from your carrier, copy them from a PDF, or paste them in) and
everything stays in a local `data/` folder on your own machine. ShipCost never
touches the network.

> This is a companion to the reseller handbook and *resale-lot-builder* — the
> handbook explains the strategy, resale-lot-builder picks the lots, and
> ShipCost handles "but how much does it actually cost to mail?" (More at
> <https://dylanasdale.github.io>.)

Built by **Asdale Dynamics, LLC**. MIT licensed — see `LICENSE`.

---

## Why this exists

Carrier checkout pages are slow, logged-in-only, and buried. Published rate
tables move every year. Resellers meanwhile need fast answers to three
questions:

1. Which service is cheapest for *this* package, *after* insurance?
2. How many days does it take — because a $3 saving is not worth an angry buyer?
3. What does that landed cost do to my profit at this sale price?

ShipCost answers all three from your own tables, in under a second, with no
internet required.

## Quick start

```bash
pip install .
shipcost demo                                          # load the fictional sample table
shipcost rates                                         # peek at what got installed
shipcost clear                                         # wipe the sample again
```

No `pip` available? Run straight from the source folder:

```bash
PYTHONPATH=src python3 -m shipcost demo
```

System Python refuses installs (PEP 668)? Use a venv:

```bash
python3 -m venv .venv && .venv/bin/pip install . && .venv/bin/shipcost demo
```

## Importing your real rate tables

### The CSV format

ShipCost reads flat rate rows — each row is one published price:

| column              | required | meaning                                                                   |
| ------------------- | -------- | ------------------------------------------------------------------------- |
| `carrier`           | yes      | e.g. `Sample Parcel Co.` (can be added wholesale with `--carrier`)         |
| `service`           | yes      | e.g. `Ground Mouse`                                                       |
| `zone`              | yes      | as written in the table, e.g. `3` or `5-9` or `Local`                      |
| `weight_lb`         | yes      | the **weight-break ceiling**: this price covers packages *up to* this      |
| `base_price`        | yes      | published price for that break                                            |
| `insurance_per_100` | no       | fee charged **per $100** (or part) of declared value; blank/0 = none       |
| `hand_min_days`     | no       | handling/shipping time, low end                                           |
| `hand_max_days`     | no       | handling/shipping time, high end                                          |

Money values may include `$` and thousands commas. Optional columns may be left
off the file entirely (blank-friendly is the whole point). A complete blank
template lives in `src/shipcost/examples/rate_table_template.csv`, and a full
fictional sample table (two carriers, zones `Local,1,2,3,5,8`, weight breaks
`1,2,3,5,10` lb) is bundled at `src/shipcost/examples/sample_rate_table.csv` —
regenerate or tweak it with `python3 scripts/make_sample_rate_table.py`.

> The bundled sample tables use clearly-fictional carriers and prices so nobody
> mistakes them for real quotes. Always import your carrier's *current*
> published table before deciding how to ship.

### Import commands

```bash
shipcost import --file usps_ground_advantage_2026.csv
shipcost import --file ups_commercial_rates.csv     # repeatable, rows dedupe-safe
shipcost import --file regional_ground.csv --replace # wipe-and-reload when a table changes
```

Paste instead of download — the rate table from a carrier's rate card PDF can go
straight in:

```bash
shipcost import --paste                              # paste rows, end with Ctrl-D (Windows: Ctrl-Z then Enter)
shipcost import --paste --carrier "Mail Express Co." # fill missing carrier names in one go
```

Handy inventory of what you have:

```bash
shipcost rates [--carrier NAME] [--zone 5]
shipcost zones
shipcost where          # shows your data dir and file
```

## Comparing options

```bash
shipcost compare --weight 2 --zone 5 --value 45
```

With a 2 lb box going to zone 5 and $45 declared value, the bundled sample
produces:

```
Package: 2 lb actual | 2 lb billed
Zone '5' | declared $45.00 | extras $0.00

#  Carrier              Service       Break  Landed  Ins    Handling
-  -------------------  ------------  -----  ------  -----  --------
1  Sample Parcel Co.    Ground Value   2 lb  $11.05  $1.05  3-6 days
2  Sample Express Inc.  Priority Air   2 lb  $20.65  $1.35  1-2 days
Landed = published base + insurance (per $100 of declared value) + extras.
```

Add the dimensions and ShipCost bills dimensional weight (max of actual vs
`L*W*H / divisor`, default divisor 139 — pass `--divisor 166` when a table says
so):

```bash
shipcost compare --weight 2 --dims 12x9x4 --zone 5 --value 45 --extras 0.50
```

```
Package: 2 lb actual | 3.11 lb billed | dims 12x9x4 in (divisor 139)
Zone '5' | declared $45.00 | extras $0.50

#  Carrier              Service       Break  Landed  Ins    Handling
-  -------------------  ------------  -----  ------  -----  --------
1  Sample Parcel Co.    Ground Value   5 lb  $13.75  $1.05  3-6 days
2  Sample Express Inc.  Priority Air   5 lb  $24.85  $1.35  1-2 days
Landed = published base + insurance (per $100 of declared value) + extras.
```

- **Landed** = published base + insurance + extras (mailer, tape, label).
- **Insurance** = `ceil(declared value / 100) × insurance_per_100` — part of a
  hundred still counts, matching how published insurance schedules charge.
- **Handling** comes straight from your CSV (`hand_min_days`/`hand_max_days`),
  so the slow-but-cheap vs fast-but-pricey tradeoff is visible.
- Sorting: cheapest landed first; ties go to the faster handling time.

## Folding in your resale margin

Option A — do it in one shot; the compare table gains a `Profit` column:

```bash
shipcost compare --weight 2 --zone 5 --value 45 \
  --sell 46 --item-cost 12 --fee-pct 13.25
```

Option B — the standalone calculator (its own brain-friendly layout):

```bash
shipcost margin --sell 60 --ship 9.42 --item-cost 18 --packaging 0.50 --fee-pct 13.25
```

```
Resale margin check
  sale price       $60.00
  item cost        $18.00
  packaging        $0.50
  landed ship cost $9.42
  marketplace fees $7.95  (13.25% of sale)
  total costs      $27.92
  profit           $24.13
  margin of sale   40.2%
  ROI on costs     86.4%
  break-even sale  $32.18
```

Formulas used (so you can double-check against your own marketplace math):

- fees = sell × fee_pct / 100
- profit = sell − item_cost − packaging − landed_ship − fees
- margin% = profit / sell  ·  ROI% = profit / (item_cost + packaging + landed_ship)
- break-even sale = (item_cost + packaging + landed_ship) / (1 − fee_pct/100)

`--fee-pct` is for whatever percentage comes off the top of the sale (marketplace
commission, payment processing, taxes you owe on the sale). Leave it off and it
acts like 0.

## The cheat card

*For the low-energy days: the card holds the decisions so your head does not
have to.*

```bash
shipcost compare --weight 2 --dims 12x9x4 --zone 5 --value 45 --sell 46 --item-cost 12 --fee-pct 13.25 --card
shipcost card                 # a blank card to print and fill in by hand
shipcost card --weight 2.4    # blank card with the weight prefilled
```

The card shows today's date, the package, the top picks with landed cost and
handling time, and a margin plan — with pen-fillable blanks (`$______.____`)
for whatever you have not decided yet. Tape it near the shipping scale.

## Local-only storage and privacy

- Everything lives in one file: `data/rates.csv` inside the folder where you
  run the tool (change with `--data-dir` or the `SHIPCOST_DATA_DIR` env var).
- The `data/` folder is in `.gitignore` — your rates are yours, and accidental
  commits are hard by design.
- Imports skip duplicate rows (safe to re-run), overwrite atomically, and any
  rates-file corruption is rejected loudly rather than silently half-read.
- `shipcost clear --yes` removes only the rates file. Nothing else is touched.
- No telemetry, no network calls, no accounts, no scraping — there is literally
  no code path that could phone home.

## Troubleshooting

- **"missing required column(s)"** — the table header needs the columns listed
  above; rename yours to match, or add a `--carrier` for tables without a
  carrier column.
- **"row N: … extra value(s)"** — an unquoted comma inside a price (write
  `"1,234.50"` with quotes, or drop the comma entirely).
- **"nothing importable"** — every row was rejected; check the warnings printed
  above the error for the row numbers.
- **A compare finds nothing** — check `shipcost zones` for the exact zone
  spelling in your table, and remember the whole package weight must fit under
  a published break: a 2.05 lb package looks for the `3` lb break.
- **Weird dim weights** — the divisor defaults to 139; switch with `--divisor`.

## Development

```bash
python3 -m pytest            # full test suite (unit + CLI end-to-end)
pip install -e .             # editable install, adds the `shipcost` command
```

Layout is boring on purpose: `src/shipcost/` holds `store.py` (CSV I/O),
`pricing.py` (billed weight, insurance, ranking), `margin.py`,
`formatting.py`, and `cli.py`. Tests live in `tests/`. Python 3.9+ standard
library only.

## Companions

- **The reseller handbook** — strategy for sourcing and pricing lots.
- **resale-lot-builder** — turn a pile of finds into lots worth buying.
- **dylanasdale.github.io** — AI explained like a friend would.

## Credits

Made by **Asdale Dynamics, LLC** — plain-English AI guides, books, and practical
tools for beginners and small businesses. © 2026 Asdale Dynamics, LLC, MIT
License (see `LICENSE`). For deciding how to ship your own packages; the sample
carriers in the bundled tables are fictional and not affiliated with any real
carrier.

*And no carriers were scraped in the making of this cheat card.*
