# STATUS — ShipCost (shipping cost comparer CLI)

Last updated: 2026-10-26

## What was built

`shipcost` — a local-only Python CLI for resellers that compares shipping costs
**with zero scraping**: you import your carriers' published rate tables as CSV
(file or pasted), and it turns them into fast side-by-side answers.

Features, as shipped:

- **`import`** — load published rate tables from a CSV file (`--file`) or pasted
  text (`--paste`), into one local CSV (`data/rates.csv`, overridable with
  `--data-dir` / `SHIPCOST_DATA_DIR`). Duplicate rows are skipped automatically;
  `--replace` wipes and reloads when a carrier publishes a new table; `--carrier`
  fills in carrier names for tables/pastes that lack a carrier column.
- **Forgiving parser** — accepts `$` and comma-formatted money, BOM headers,
  blank optional fields; rows with real problems are skipped with row-numbered
  warnings instead of crashing; the required-column error names what is missing.
- **`compare`** — for one package (actual weight, `--dims 12x9x4`, dimensional
  divisor, zone, declared value, per-piece extras) it picks the smallest
  published weight break that covers the **billed** weight
  (max of actual vs `L*W*H/divisor`, default 139), adds insurance
  (per full-or-partial $100 of declared value) and extras, and ranks **landed
  cost** with **insurance** and **handling-time** columns visible. Ties go to
  faster handling. `--sell`/`--item-cost`/`--fee-pct`/`--packaging` add a
  per-option **Profit** column.
- **`margin`** — resale calculator: fees off the top, total costs, profit,
  margin-of-sale %, ROI-on-costs %, and break-even sale price.
- **`card` / `compare --card`** — prints a ready-to-brain cheat card (package,
  zone, top picks with landed cost + handling, and a margin plan with
  pen-fillable blanks) sized for taping next to the shipping scale. A blank
  card (`shipcost card [-weight N]`) works without any rates installed.
- **`rates` / `zones` / `where` / `demo` / `clear`** — inspect, filter, show
  storage paths, install/remove the bundled fictional sample table.
- **Local-only storage and privacy** — one CSV file in a local folder; imports
  write atomically via a temp file; a corrupt rates file is rejected loudly on
  load. There is no network code path at all. `data/` is gitignored.
- Complements the reseller handbook and resale-lot-builder (credited in
  README).

Bundled data: `src/shipcost/examples/sample_rate_table.csv` (fictional
"Sample Parcel Co." / "Sample Express Inc.", zones Local/1/2/3/5/8, breaks
1/2/3/5/10 lb — 60 rows) and `rate_table_template.csv`; regenerable with
`scripts/make_sample_rate_table.py`.

## Layout

```
src/shipcost/   models, store (CSV), pricing, margin, formatting, cli
tests/          pytest suite: store, pricing, margin, CLI end-to-end
scripts/        sample-table generator
examples/       bundled inside src/shipcost/examples/ (package data)
```

## How to run

```bash
pip install .            # or: python3 -m venv .venv && .venv/bin/pip install .
shipcost demo            # try everything with the fictional sample table
shipcost import --file your_rates.csv      # bring your own published table
shipcost import --paste --carrier "Mail Express Co."
shipcost compare --weight 2 --dims 12x9x4 --zone 5 --value 45 --sell 46 --item-cost 12 --fee-pct 13.25 --card
shipcost margin --sell 60 --ship 9.42 --item-cost 18 --packaging 0.5 --fee-pct 13.25
shipcost card            # blank cheat card

# without installing:
PYTHONPATH=src python3 -m shipcost demo
```

## Verification results (all run on this machine, 2026-10-26)

- `python3 -m pytest` — **51 passed** (store 13, pricing 12, margin 6, CLI 20).
- Full CLI walkthrough executed for real (version, demo, rates, zones, where,
  compare with/without dims, compare + `--card` + sale plan, paste-import with
  `--carrier` override and skipped noisy row, Kwik Feet carrier filtered list,
  cross-carrier ranking incl. a pasted carrier beating a demo carrier, margin
  calculator, blank card, clear both with user-confirm and `--yes`).
- Verified the math independently: break "2 lb" covers 2 lb ($11.05 ground /
  $20.65 air in the sample); 12x9x4 in at divisor 139 bills 3.11 lb → 5 lb
  break ($13.75 landed incl. $1.05 insurance + $0.50 extras); margin example
  computes $24.13 profit, 40.2% margin, 86.4% ROI, $32.18 break-even.
- Packaging verified: `pip wheel .` builds `shipcost-0.1.0-py3-none-any.whl`
  including bundled example CSVs; a fresh `python3 -m venv` + `pip install .`
  works and the `shipcost` console script runs end-to-end from installed code.
- Error paths verified friendly (no tracebacks): bad header, missing file,
  empty table, negative weight, bad dims/divisor, unknown zone, empty store.
- Emoji/format sanity scan and a no-secrets scan of the tree: clean. No API
  keys, no personal data — the only names present are the fictional sample
  carriers.

## Known gaps / honest limits

- Rate tables are **step tables**: the whole package must fit under a published
  break — no interpolation between breaks (no per-pound pro-rating).
- Insurance is modeled as a flat fee per full-or-partial $100 of declared
  value; carriers that charge a minimum insurance fee or a free first $100 need
  those baked into their `insurance_per_100` (or left at 0 to skip insuring).
- One global dim divisor per compare run (139 default; pass `--divisor 166`).
  Per-carrier divisors are not modeled.
- Handling time is display + tie-break ranking only; it does not gate options
  (a slow cheap option is never hidden, just sorted by landed cost).
- Sample carriers/prices are fictional by design; real pricing depends on
  importing a current published table.
- No batch mode (compare many packages from one CSV at once), no HTML/PDF card
  export, no marketplace-specific fee presets — all plausible next steps.
- Dates on the card are the local system date.
