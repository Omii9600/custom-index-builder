# Custom Index Builder (Price Return)

A small web app that builds a **custom equity index** from a universe of 30 dummy stocks and calculates its **Price Return Index** over time.

The user picks stocks, a weighting method and a date range, clicks **Generate index**, and gets:

- the index level series (base 100 by default), charted against a benchmark
- summary metrics: cumulative return, annualised return and volatility, Sharpe ratio, max drawdown, best and worst day
- every validation error or data decision the app made, in plain language
- a constituents table showing each stock's weight and **how many percentage points it contributed** to the index return
- the sector mix, and a CSV download of the index series

### What goes beyond the brief

| Feature | Why it matters |
|---|---|
| **4 weighting methods**, including **capped float market-cap** | Capping is how real index providers stop one stock dominating an index. |
| **Benchmark comparison** (equal-weight whole universe) | Answers the question "did my stock selection actually help?" |
| **Return attribution** that adds up exactly | Shows *which* stocks drove the result, not just the total. |
| **Deliberately messy dummy data** | Proves the missing-data rules work on real cases, not just in theory. |
| **Unit tests** (standard library, no extra installs) | The core formula is checked against a hand calculation. |

---

## How to run

Requires Python 3.9+.

```bash
git clone <your-repo-url>
cd custom-index-builder
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in a browser.

The dummy data is already in `data/`. If it's missing, `app.py` regenerates it automatically, or run `python data/generate_data.py` yourself.

Run the tests:

```bash
python -m unittest discover tests -v
```

---

## Architecture

```
 Browser (HTML + CSS + JavaScript + Chart.js)
        |  GET /api/universe        -> stock list, date range, methods
        |  POST /api/generate (JSON)-> index result or validation errors
        v
 app.py  (Flask: routing only, no maths)
        |
        v
 index_builder/   (pure Python, knows nothing about the web)
   builder.py       IndexBuilder         runs the pipeline in order
   data_loader.py   DataLoader           reads + checks CSVs, caches prices
   validation.py    RequestValidator     checks the user's input
                    MissingDataHandler   applies the missing-data policy
                    ValidationReport     collects errors and warnings
   weighting.py     WeightingScheme (abstract) + 4 schemes
   calculator.py    PriceReturnIndex     the three required formulas
   metrics.py       PerformanceMetrics   summary statistics
        |
        v
 data/stocks.csv, data/prices.csv
```

**Pipeline for one request:** validate input → slice prices for the chosen stocks and dates → apply missing-data policy → compute weights → compute index → compute metrics and benchmark → return JSON.

### Why these choices

- **Flask + plain HTML/JS for the UI.** The brief asks for a web-based frontend and a Python backend. Flask gives a clean split: the browser only collects input and draws results; all calculations happen in Python. This makes the API easy to test and means the same backend could serve a different frontend later. Plain JavaScript keeps the project small with no build step. Chart.js draws the chart.
- **Backend is a separate package** (`index_builder/`). It has no Flask imports, so it can be tested, reused in a notebook, or moved behind a different framework without changes.
- **Server-side validation is the single source of truth.** The UI shows a live total for custom weights as a convenience, but every rule is enforced in Python, so the API is safe even if called directly.
- **Data is read once at start-up** and kept in memory as a wide table (rows = dates, columns = tickers). With 30 stocks × ~520 days this is tiny and makes every request fast.

### How OOP is used

| Principle | Where |
|---|---|
| **Classes / objects** | Each responsibility is one class: loading (`DataLoader`), validation (`RequestValidator`, `MissingDataHandler`), weights, calculation (`PriceReturnIndex`), metrics (`PerformanceMetrics`), orchestration (`IndexBuilder`). |
| **Encapsulation** | `DataLoader` keeps raw data private (`_stocks`, `_prices`) and returns copies, so no caller can corrupt the cache. `PriceReturnIndex` calculates once and exposes results through read-only properties. |
| **Abstraction** | `WeightingScheme` is an abstract base class: it defines *what* a scheme must do (`compute`) without saying *how*. |
| **Inheritance** | `CappedMarketCapWeight` extends `MarketCapWeight`: it reuses the market-cap calculation via `super()` and adds the cap on top. |
| **Polymorphism** | `IndexBuilder` calls `scheme.compute(...)` without knowing which scheme it has. Adding a new method (e.g. sector-neutral) means adding one class and one line in the factory; nothing else changes. |
| **Factory** | `create_scheme()` turns the method name from the UI into the right object. |

---

## Data format

### `data/stocks.csv` (30 rows)

| Column | Meaning |
|---|---|
| `ticker` | Unique stock code, e.g. `NOVA` |
| `company_name` | Display name |
| `sector` | One of 6 sectors (5 stocks each) |
| `free_float_shares_mn` | Shares available to the public, in millions. Used for market-cap weighting. |

### `data/prices.csv` (long format)

| Column | Meaning |
|---|---|
| `date` | Trading day, `YYYY-MM-DD` (Monday–Friday, 2024-01-01 to 2025-12-31) |
| `ticker` | Must exist in `stocks.csv` |
| `close_price` | Closing price. May be blank. |

Prices are generated by `data/generate_data.py` as a random walk with a shared "market" factor (so stocks move together, like real ones) and sector-specific growth and volatility. The random seed is fixed, so the data is identical on every machine.

### Data problems injected on purpose

| Stock | Problem | What the app does |
|---|---|---|
| **VOLT** | Listed on 2024-07-01 (no earlier prices) | Excluded if the range starts before its listing |
| **GLOW** | Missing 2 days (2024-03-12, 13) | Forward-filled, with a warning |
| **PTRO** | 8-day trading halt (2025-02-03 to 12) | Excluded if the range covers the halt |
| **FRSH** | Blank price on 2024-11-15 | Forward-filled, with a warning |

Checks when loading the files (the app refuses to start if these fail): required columns present, no duplicate tickers, no duplicate date/ticker rows, readable dates, positive share counts, every price ticker exists in the universe.

---

## Weighting methods

Weights are set **on the start date** of the chosen range and always add up to 100%.

| Method | Formula | Validation |
|---|---|---|
| **Equal** | `w_i = 1 / N` | — |
| **Float market-cap** | `w_i = cap_i / Σ cap_j`, where `cap_i = free_float_shares_i × price_i(start)` | Shares must be positive (checked on load) |
| **Capped float market-cap** | Market-cap weights; any stock above the cap is set to the cap and the excess is shared among the other stocks in proportion to their size. Repeated until no stock is above the cap. | Cap must be 0–100%, and `cap × N ≥ 100%` (e.g. a 20% cap needs at least 5 stocks) |
| **Custom** | User enters a % per stock | Every selected stock needs a weight; each must be ≥ 0 (long-only); total must be 100% (± 0.01) |

If a stock is excluded because of missing data, the remaining weights are recalculated so they still add up to 100%, and the user is told.

---

## Price return formula

Implemented exactly as specified, in `index_builder/calculator.py`:

```
Stock daily return:   r_i(t)     = close_i(t) / close_i(t-1) - 1
Index daily return:   r_index(t) = Σ w_i × r_i(t)
Index level:          level(t)   = level(t-1) × (1 + r_index(t)),   level(start) = base (100)
```

The level is computed with a cumulative product, which is the same as applying the last formula one day at a time.

**Worked example** (also a unit test): stocks A and B at 50% each. A: 100 → 110 → 99, B: 50 → 50 → 55.
Day 1: 0.5 × 10% + 0.5 × 0% = 5% → level 105. Day 2: 0.5 × (−10%) + 0.5 × 10% = 0% → level 105.

**Price return** means dividends are ignored; only price changes count.

### Contribution (attribution)

Each day the index gains `level(t-1) × w_i × r_i(t)` points from stock *i*. Summing a stock's points and dividing by the base gives its contribution. Across all stocks, the contributions add up **exactly** to the cumulative return (tested).

### Metrics

- Cumulative return = `level(end) / level(start) − 1`
- Annualised return = `(1 + cumulative)^(252 / days) − 1`
- Annualised volatility = daily-return standard deviation × √252
- Sharpe ratio = annualised return / annualised volatility (risk-free rate taken as 0)
- Max drawdown = the largest fall from a previous high

---

## Missing data handling

Missing rows and blank prices are treated the same way (both become empty values when prices are reshaped). Rules, applied to each selected stock within the chosen date range:

1. **No price on the start date** (e.g. listed later) → **exclude**. An index needs a starting price for every stock it holds.
2. **Gap of up to 5 trading days** → **forward-fill** the last known price. The stock's return is 0% on those days, and the move is caught up on the day trading resumes. The user is warned.
3. **Gap longer than 5 days** → **exclude**. Filling a long gap would hide real price movement.
4. **Zero or negative price** → **exclude**, as returns can't be calculated.
5. **No usable stocks left**, or fewer than 2 trading days → **error**, no index is built.

Every decision appears in the UI under "Data decisions made". The benchmark applies the same rules but its warnings are kept separate so they don't clutter the user's results.

### Input validation (returns HTTP 400 with reasons)

At least one stock; no duplicates or unknown tickers; a valid method; valid dates within the data range with start before end; positive base level; plus the weighting-specific checks above.

---

## Git workflow

Work was done in small commits on `main`, with three feature branches merged back using `--no-ff` so each merge is visible in the history:

- `feature/weighting-schemes`: weighting strategies, the index calculator and metrics
- `feature/web-ui`: Flask API and the browser interface
- `feature/tests`: unit tests

See the full history with `git log --oneline --graph --all`.

---

## Limitations and future improvements

- **Daily rebalancing is implied by the formula.** Applying fixed weights to every day's returns means weights are reset to target every day, which a real index doesn't do (weights drift with prices between rebalances). A natural next step is a buy-and-hold / periodic rebalance option (e.g. quarterly), with weights drifting in between. This also explains why a stock with a negative total price return can show a small positive contribution: its contribution depends on the path, not just the start and end price.
- **Price return only.** A total return index would reinvest dividends; that needs a dividends dataset.
- **No corporate actions.** Splits, mergers or spin-offs would need price adjustment factors.
- **Market-cap weights use the start-date price only.** Real indices refresh share counts and caps at each review.
- **In-memory CSV data.** Fine for 30 stocks; for thousands of stocks and years of history, move to a database (e.g. PostgreSQL or Parquet files) and cache results.
- **Single currency, no holiday calendar** (Monday–Friday is used as the trading calendar).
- **Sharpe ratio assumes a 0% risk-free rate.**
- **Scaling ideas:** save and compare several custom indices, add sector or turnover limits, run the calculation as a background job for large universes, and add CI (GitHub Actions) to run the tests on every push.
