# Custom Index Builder

A small web app that lets you build your own stock market index from a list of 30 made-up companies, and see how that index would have performed over time.

You pick the companies, decide how much each one should count, choose a time period, and press **Generate index**. The app then shows:

- a chart of your index over time, starting at 100, next to a benchmark
- how well it did: total return, yearly return, how bumpy the ride was, the worst fall
- which companies helped and which hurt, and by how much
- every problem it found in the data, and what it did about it

This README explains everything from the ground up. You don't need a finance or programming background to follow it. If you only have five minutes, read [Key ideas](#1-key-ideas-in-plain-english) and [The maths](#4-the-maths-step-by-step).

---

## Contents

1. [Key ideas in plain English](#1-key-ideas-in-plain-english)
2. [How to run the app](#2-how-to-run-the-app)
3. [How to use the app](#3-how-to-use-the-app)
4. [The maths, step by step](#4-the-maths-step-by-step)
5. [Weighting methods](#5-weighting-methods)
6. [Which stocks helped? (contribution)](#6-which-stocks-helped-contribution)
7. [Performance metrics](#7-performance-metrics)
8. [Missing data: what the app does and why](#8-missing-data-what-the-app-does-and-why)
9. [Input checks](#9-input-checks)
10. [The data files](#10-the-data-files)
11. [How the code is organised](#11-how-the-code-is-organised)
12. [Every file and function explained](#12-every-file-and-function-explained)
13. [How I used object-oriented programming](#13-how-i-used-object-oriented-programming)
14. [Testing](#14-testing)
15. [Git workflow](#15-git-workflow)
16. [Why I made these design choices](#16-why-i-made-these-design-choices)
17. [Limitations and what I'd improve next](#17-limitations-and-what-id-improve-next)

---

## 1. Key ideas in plain English

| Term | What it means |
|---|---|
| **Stock** | A small piece of ownership in a company. Its price goes up and down every day. |
| **Ticker** | A short code for a company, like `NOVA` for Nova Systems. |
| **Closing price** | The stock's price at the end of a trading day. This app only uses closing prices. |
| **Index** | A single number that tracks a group of stocks together. When people say "the market went up 1% today", they usually mean an index like the S&P 500 went up 1%. |
| **Base level** | The number the index starts at. I use 100, so if the index ends at 125 you can instantly see it grew 25%. |
| **Return** | How much something grew, as a percentage. Going from 100 to 110 is a 10% return. |
| **Weight** | How much each stock counts in the index. If NOVA has a 30% weight, 30% of the index's movement comes from NOVA. Weights always add up to 100%. |
| **Market capitalisation (market cap)** | The total value of a company on the stock market: number of shares × share price. |
| **Free float** | The shares that ordinary investors can actually buy. Shares locked up by founders or governments are excluded. Real index providers use free-float market cap. |
| **Price return index** | An index that only counts price changes. It ignores dividends (cash payments companies make to shareholders). |
| **Benchmark** | Something to compare against. Here, it's an index of the whole 30-stock universe with equal weights. |
| **Trading day** | A day the market is open. I treat Monday to Friday as trading days. A year has roughly 252 trading days. |

---

## 2. How to run the app

**You need:** Python 3.9 or newer. Check by typing `python --version` in a terminal.

```bash
# 1. Get the code
git clone <your-repo-url>
cd custom-index-builder

# 2. Create a private space for this project's libraries (optional but recommended)
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate

# 3. Install the three libraries it needs: Flask, pandas, NumPy
pip install -r requirements.txt

# 4. Start the app
python app.py
```

Now open **http://127.0.0.1:5000** in your web browser.

The data files are already in the `data/` folder. If they're ever deleted, the app recreates them the first time it starts. You can also recreate them yourself with `python data/generate_data.py`.

To run the automated tests:

```bash
python -m unittest discover tests -v
```

---

## 3. How to use the app

The left side of the screen has three numbered steps.

1. **Choose stocks.** Tick companies one by one, search by name, or click a sector name (for example "Technology") to select all five companies in that sector at once.
2. **Choose weighting.** Decide how much each stock counts (explained in [section 5](#5-weighting-methods)). If you pick "Custom weights", boxes appear for you to type a percentage for each stock, with a running total so you can see when you've reached 100%. "Split evenly" fills them in for you.
3. **Choose period.** Pick a start and end date between 1 January 2024 and 31 December 2025, and the base level (100 by default).

Press **Generate index**. Results appear on the right. If something is wrong with your choices, a red box explains exactly what to fix. If the app had to make a decision about missing data, a yellow box tells you what it did.

**Try this:** select VOLT, GLOW, PTRO and FRSH. These four have deliberate data problems, so you can see the app handle each one.

---

## 4. The maths, step by step

The whole calculation is three formulas, used in order. I'll explain each one, then walk through a full example.

### Formula 1: How much did each stock move today?

```
stock return today = today's price ÷ yesterday's price − 1
```

Written the way the project brief writes it:

```
r_i(t) = close_i(t) / close_i(t−1) − 1
```

- `i` means "stock number i" (any one of the stocks)
- `t` means "today", and `t−1` means "the trading day before"

**Example:** a stock closed at 100 yesterday and 110 today. 110 ÷ 100 − 1 = 0.10, which is **+10%**.

**Why subtract 1?** Dividing gives you "how many times bigger" (1.10 = 110% of yesterday). Subtracting 1 leaves just the change (10%).

### Formula 2: How much did the index move today?

```
index return today = (weight of stock 1 × return of stock 1)
                   + (weight of stock 2 × return of stock 2)
                   + ... for every stock
```

In the brief's notation (Σ, the Greek letter sigma, just means "add them all up"):

```
r_index(t) = Σ w_i × r_i(t)
```

**Example:** stock A is 50% of the index and rose 10%. Stock B is 50% and didn't move.
Index return = 0.5 × 10% + 0.5 × 0% = **+5%**.

This is a weighted average. A stock with a bigger weight has a bigger effect on the index.

### Formula 3: What is the index level today?

```
index level today = index level yesterday × (1 + index return today)
```

```
level(t) = level(t−1) × (1 + r_index(t)),     starting from level = 100
```

**Example:** the index was 100 yesterday and rose 5% today. 100 × 1.05 = **105**.

This is compounding: each day's growth builds on top of the previous day's level, just like interest in a savings account.

### Full worked example

Two stocks, 50% weight each, over four days.

| Day | Price A | Price B | Return A | Return B | Index return | Index level |
|---|---|---|---|---|---|---|
| 1 | 100.00 | 50 | – | – | – | **100.00** (start) |
| 2 | 110.00 | 50 | +10% | 0% | 0.5×10% + 0.5×0% = **+5%** | 100 × 1.05 = **105.00** |
| 3 | 99.00 | 55 | −10% | +10% | 0.5×(−10%) + 0.5×10% = **0%** | 105 × 1.00 = **105.00** |
| 4 | 104.94 | 55 | +6% | 0% | 0.5×6% + 0.5×0% = **+3%** | 105 × 1.03 = **108.15** |

The index ended at 108.15, so it grew **8.15%** over the period.

Notice day 3: A fell 10% and B rose 10%, and they cancelled out exactly. That's the whole point of an index: it shows the combined movement of a group.

This exact example is one of the automated tests, so the code is checked against these hand-calculated numbers.

### How the code does it

In `index_builder/calculator.py`, each formula is one line of pandas working on the whole table at once instead of looping day by day:

```python
stock_returns = prices / prices.shift(1) - 1                  # Formula 1
index_returns = (stock_returns * weights).sum(axis=1)         # Formula 2
levels        = base * (1 + index_returns).cumprod()          # Formula 3
```

- `prices.shift(1)` moves every price down one row, so each row lines up with the previous day's price.
- `cumprod()` means "cumulative product": it multiplies 1.05 × 1.00 × 1.03 ... day after day. That's the same as applying Formula 3 one day at a time.

---

## 5. Weighting methods

The weighting method decides how much each stock counts. Weights are set using prices on the **start date** and always add up to 100%.

### Equal weight

Every stock counts the same.

```
weight = 1 ÷ number of stocks
```

**Example:** 4 stocks → each gets 1 ÷ 4 = **25%**.

*When to use it:* when you want small companies to matter as much as big ones.

### Float market-cap weight

Bigger companies count more, in proportion to their size. This is how most well-known indices, including the S&P 500, work.

```
company size (float market cap) = free-float shares × share price on the start date
weight = this company's size ÷ total size of all selected companies
```

**Example:**

| Stock | Free-float shares | Price | Float market cap | Weight |
|---|---|---|---|---|
| A | 10 million | 100 | 1,000 million | 1,000 ÷ 2,500 = **40%** |
| B | 30 million | 50 | 1,500 million | 1,500 ÷ 2,500 = **60%** |
| **Total** | | | **2,500 million** | **100%** |

*When to use it:* when you want the index to reflect where the money actually is.

### Capped float market-cap weight

Same as market-cap weight, but no single stock is allowed to go above a limit you choose (for example 40%). Real index providers do this to stop one giant company from dominating an index.

**How the cap works:**

1. Work out normal market-cap weights.
2. Any stock above the cap is cut down to the cap.
3. The weight that was cut off is shared among the other stocks, in proportion to their size.
4. If sharing it pushes another stock above the cap, repeat until nobody is above it.

**Example** with a 40% cap:

| Stock | Market cap | Normal weight | After capping |
|---|---|---|---|
| A | 700 | 70% | cut to **40%** (30% freed up) |
| B | 200 | 20% | 20% + 20% = **40%** |
| C | 100 | 10% | 10% + 10% = **20%** |

The 30% taken from A is split between B and C in the ratio of their sizes, 200 : 100 (2 : 1). So B gets 20% and C gets 10%.

**A rule the app enforces:** the cap × number of stocks must be at least 100%. With 3 stocks and a 20% cap, the most the weights could add up to is 60%, which is impossible. The app explains this and asks you to raise the cap or add stocks.

### Custom weights

You type in each stock's percentage yourself.

The app checks that:
- every selected stock has a weight
- no weight is negative (this is a "long-only" index: you can own a stock, but not bet against it)
- the weights add up to 100% (a tiny rounding difference of up to 0.01% is allowed)

If a stock is later removed because of missing data, the others are scaled up so they still add to 100%. **Example:** you set A 50%, B 30%, C 20%, and A gets removed. B and C together are 50%, so B becomes 30 ÷ 50 = **60%** and C becomes 20 ÷ 50 = **40%**. They keep the same ratio to each other.

---

## 6. Which stocks helped? (contribution)

The total return tells you *how much* the index grew. Contribution tells you *why*: how many percentage points each stock added or took away.

```
points a stock added today = yesterday's index level × stock's weight × stock's return today
contribution = total points the stock added over the whole period ÷ base level
```

**Example** using the worked example from section 4:

| Day | Stock A points | Stock B points |
|---|---|---|
| 2 | 100 × 0.5 × 10% = +5.00 | 100 × 0.5 × 0% = 0 |
| 3 | 105 × 0.5 × (−10%) = −5.25 | 105 × 0.5 × 10% = +5.25 |
| 4 | 105 × 0.5 × 6% = +3.15 | 105 × 0.5 × 0% = 0 |
| **Total** | **+2.90 points → 2.90%** | **+5.25 points → 5.25%** |

2.90% + 5.25% = **8.15%**, exactly the index's total return. The contributions always add up exactly to the total; there's a test that checks this.

**An interesting detail:** stock A's price went from 100 to 104.94 (+4.94%), but at a 50% weight it contributed 2.90%, not 2.47% (half of 4.94). That's because A's fall on day 3 happened when the index was smaller, and its rise on day 4 happened when the index was bigger. Contribution depends on the *path* a stock took, not just where it started and ended. This is also why a stock with a negative total price return can sometimes show a small positive contribution.

---

## 7. Performance metrics

These appear in the "Performance" table, for both your index and the benchmark.

| Metric | What it tells you | Formula | Example |
|---|---|---|---|
| **Cumulative return** | Total growth over the whole period | end level ÷ start level − 1 | 100 → 108.15 = **8.15%** |
| **Annualised return** | The steady yearly growth rate that would give the same result | (1 + cumulative return) ^ (252 ÷ number of daily returns) − 1 | 20% over 2 years (504 days): 1.2 ^ 0.5 − 1 = **9.54% a year** |
| **Annualised volatility** | How bumpy the ride was. Higher means bigger daily swings. | standard deviation of daily returns × √252 | daily swings of about 1% → 1% × 15.87 = **15.87% a year** |
| **Sharpe ratio** | Return earned for each unit of risk taken. Higher is better. | annualised return ÷ annualised volatility | 9.54% ÷ 15.87% = **0.60** |
| **Max drawdown** | The worst fall from a high point to a later low point | lowest value of (level ÷ highest level so far − 1) | levels 100 → 120 → 90 → 110: fall from 120 to 90 = **−25%** |
| **Best / worst day** | The biggest single-day rise and fall | largest and smallest daily index return | |

**Plain-language notes:**

- **Why 252?** It's the usual number of trading days in a year. It converts daily numbers into yearly ones so periods of different lengths can be compared.
- **Why annualised return isn't just 20% ÷ 2 = 10%:** growth compounds. 9.54% a year for two years gives 1.0954 × 1.0954 = 1.20, which is 20%.
- **Why volatility uses √252 and not 252:** daily ups and downs partly cancel out over time, so risk grows with the square root of time, not in a straight line. This is standard practice.
- **Standard deviation** measures how spread out numbers are from their average. If daily returns are always close to their average, it's small; if they jump around, it's large.
- **Sharpe ratio** normally subtracts a "risk-free" return (for example, what a government bond pays). I assume it's 0% to keep things simple. This is noted in the limitations.

---

## 8. Missing data: what the app does and why

Real price data is never perfect. A company might list on the stock market partway through the period, trading might be paused for a few days, or a price might simply be blank. The app deals with each case using clear rules and **tells you every decision it made**.

A missing row and a blank price are treated the same way: both count as "no price for that day".

These rules are applied to each selected stock, looking only at the dates you picked:

| Situation | What the app does | Why |
|---|---|---|
| **No price on the start date** (for example, the company listed later) | Leaves the stock out | Formula 1 needs a starting price. You can't calculate a return from nothing. |
| **Gap of up to 5 trading days** | Fills the gap with the last known price | A short gap is usually a temporary glitch. Filling it means the stock shows 0% return on those days, then catches up when trading resumes. |
| **Gap longer than 5 trading days** | Leaves the stock out | Filling a long gap would pretend the price stood still for weeks, hiding real movement. |
| **Price of zero or below** | Leaves the stock out | You can't divide by zero in Formula 1, and real stock prices can't be negative. |
| **No usable stocks left, or fewer than 2 trading days** | Stops with an error | There's nothing to calculate. |

**Example of filling a gap ("forward-fill"):**

| Day | Price in data | Price used | Return |
|---|---|---|---|
| 1 | 50 | 50 | – |
| 2 | *missing* | 50 (copied from day 1) | 0% |
| 3 | *missing* | 50 (copied from day 1) | 0% |
| 4 | 53 | 53 | +6% |

The stock's total move (50 → 53) is still captured. It just shows up on day 4 instead of being spread over three days.

**Why 5 days?** It's long enough to cover a normal short break (a holiday week, a brief data outage) but short enough that filling it doesn't distort the result. It's a single constant (`MAX_FILL_DAYS`) in `validation.py`, so it's easy to change.

After a stock is removed, the remaining stocks' weights are recalculated so they still add up to 100%.

The benchmark follows the same rules. Its warnings are kept separate so they don't clutter your results.

---

## 9. Input checks

Before any maths happens, the app checks your choices. If anything is wrong, it stops and lists **every** problem at once, so you can fix them all in one go.

| Check | Example message |
|---|---|
| At least one stock selected | "Select at least one stock." |
| No stock selected twice | "A stock was selected more than once." |
| Every ticker exists | "Unknown ticker(s): XYZ." |
| Weighting method is valid | "Weighting method must be one of: ..." |
| Both dates given, in `YYYY-MM-DD` format | "Start and end dates must be valid dates (YYYY-MM-DD)." An ambiguous date like `01/02/2024` is refused rather than guessed. |
| Start is before end | "Start date must be before end date." |
| Dates are inside the available data | "Dates must be within the available data: 2024-01-01 to 2025-12-31." |
| Base level is a positive number | "Base level must be a positive number." |
| Cap is between 0 and 100% | "Weight cap must be a number between 0 and 100 (%)." |
| Cap is achievable | "A 20% cap is impossible with 3 stock(s) ..." |
| Every custom weight given | "Enter a weight for: NOVA." |
| Custom weights not negative | "Weights must be numbers of 0 or more ..." |
| Custom weights add to 100% | "Custom weights add up to 90.00%. They must add up to 100%." |

A stock with a 0% custom weight is allowed but triggers a warning, because it won't affect the index.

All checks run in Python on the server, not just in the browser. So even if someone skipped the web page and sent data straight to the server, the rules would still apply.

The data files are also checked when the app starts. It refuses to start if a required column is missing, a ticker appears twice, a date can't be read, a share count isn't a positive number, or the price file mentions a company that isn't in the stock list.

---

## 10. The data files

All data is made up. It's generated by `data/generate_data.py`.

### `data/stocks.csv`: the 30 companies

| Column | Meaning | Example |
|---|---|---|
| `ticker` | Short code, unique for each company | `NOVA` |
| `company_name` | Full name | `Nova Systems` |
| `sector` | Industry group (6 sectors, 5 companies each) | `Technology` |
| `free_float_shares_mn` | Shares available to the public, in millions. Used for market-cap weighting. | `224` |

### `data/prices.csv`: daily closing prices

| Column | Meaning | Example |
|---|---|---|
| `date` | Trading day, in `YYYY-MM-DD` format | `2024-01-02` |
| `ticker` | Which company | `NOVA` |
| `close_price` | Closing price that day. Can be blank. | `451.67` |

This is called "long format": one row per company per day (about 15,500 rows). When the app loads it, it reshapes it into a "wide" table with one row per day and one column per company, which makes the maths much easier.

### How the prices are made

Each price series is a **random walk**: every day, the price moves up or down by a small random amount.

- **Stocks move together, like real ones.** Every day there's a shared "market move" that affects all 30 stocks, plus a separate random move for each company.
- **Each sector behaves differently.** Technology grows fastest but swings the most. Consumer grows slowly but is steady.
- **Same data every time.** The random number generator uses a fixed "seed" (42), so anyone who runs the generator gets exactly the same numbers. This makes results reproducible.

### Problems I added on purpose

To prove the missing-data rules actually work, I built four realistic problems into the data:

| Company | Problem | What the app does |
|---|---|---|
| **VOLT** (Volt Storage) | Only starts trading on 1 July 2024 | Left out if your start date is before that |
| **GLOW** (Glow Cosmetics) | Missing prices on 12 and 13 March 2024 | Gap is filled, with a warning |
| **PTRO** (Petro Nova) | Trading paused for 8 days, 3 to 12 February 2025 | Left out if your period includes the pause |
| **FRSH** (Fresh Mart) | Blank price on 15 November 2024 | Gap is filled, with a warning |

---

## 11. How the code is organised

The app has three layers. Each layer only talks to the one next to it.

```
┌─────────────────────────────────────────────────┐
│  BROWSER  (what you see)                         │
│  templates/index.html  – page structure          │
│  static/style.css      – look and layout         │
│  static/app.js         – buttons, chart, tables  │
└───────────────────────┬─────────────────────────┘
                        │  sends your choices as JSON
                        │  receives results as JSON
┌───────────────────────▼─────────────────────────┐
│  WEB SERVER  (app.py, using Flask)               │
│  Receives requests and passes them on.           │
│  Contains no maths.                              │
└───────────────────────┬─────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────┐
│  CALCULATION ENGINE  (index_builder/ folder)     │
│  Pure Python. Knows nothing about websites.      │
│  Loading → checking → weights → index → metrics  │
└───────────────────────┬─────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────┐
│  DATA  (data/stocks.csv, data/prices.csv)        │
└─────────────────────────────────────────────────┘
```

**What happens when you press "Generate index":**

1. The browser collects your choices and sends them to the server.
2. The server passes them to `IndexBuilder`.
3. `RequestValidator` checks your choices. If anything is wrong, the errors go straight back to the browser.
4. `DataLoader` provides the prices for your stocks and dates.
5. `MissingDataHandler` applies the missing-data rules.
6. A weighting scheme works out each stock's weight.
7. `PriceReturnIndex` applies the three formulas.
8. `PerformanceMetrics` calculates the summary numbers. The same steps run for the benchmark.
9. Everything is sent back to the browser, which draws the chart and tables.

### Folder structure

```
custom-index-builder/
├── app.py                  Web server: 3 routes, no maths
├── requirements.txt        Libraries to install
├── data/
│   ├── generate_data.py    Creates the dummy data
│   ├── stocks.csv          30 companies
│   └── prices.csv          Daily prices
├── index_builder/          The calculation engine
│   ├── __init__.py         Lists what the package makes available
│   ├── builder.py          IndexBuilder: runs every step in order
│   ├── data_loader.py      DataLoader: reads and checks the CSV files
│   ├── validation.py       Checks your input and handles missing data
│   ├── weighting.py        The four weighting methods
│   ├── calculator.py       PriceReturnIndex: the three formulas
│   └── metrics.py          PerformanceMetrics: summary numbers
├── templates/
│   └── index.html          The web page
├── static/
│   ├── style.css           Styling
│   └── app.js              Browser-side behaviour
└── tests/
    └── test_index_builder.py   Automated tests
```

---

## 12. Every file and function explained

A quick note on naming: a name that starts with an underscore, like `_load_prices`, is **private**. It's only meant to be used inside its own class. Names without an underscore are the **public** parts other code is allowed to use.

### `data/generate_data.py`: creates the dummy data

| Function | What it does |
|---|---|
| `build_universe(rng)` | Creates the table of 30 companies. Gives each a random number of free-float shares between 50 and 2,000 million. |
| `build_prices(rng)` | Creates daily prices for every company using a random walk: a shared market move plus a company-specific move, with growth and swing size depending on the sector. |
| `inject_data_issues(prices)` | Deliberately breaks the data in four places (VOLT, GLOW, PTRO, FRSH) so the missing-data rules have something real to deal with. |
| `main()` | Runs the above with the fixed seed 42 and saves both CSV files. |

### `index_builder/data_loader.py`: reading the data

**`DataError`** is a custom error raised when a data file is missing or broken. It has its own name so it can't be confused with other kinds of error.

**`DataLoader`** reads the two CSV files once when the app starts, checks them, and keeps them in memory.

| Function | What it does |
|---|---|
| `__init__(data_dir)` | Runs when a `DataLoader` is created. Loads both files. |
| `_read_csv(path, required_columns)` | Opens a CSV file. Gives a clear error if the file is missing or a column is absent. |
| `_load_stocks(path)` | Loads the company list. Checks for duplicate tickers and that every share count is a positive number. |
| `_load_prices(path)` | Loads prices. Turns blank or unreadable prices into "missing". Checks dates are readable, there are no duplicate rows, and every ticker exists in the company list. Then reshapes the table to one row per day, one column per company. |
| `tickers` | The list of all 30 ticker codes. |
| `date_range` | The first and last date in the data. |
| `stock_info(ticker)` | Name, sector and share count for one company. |
| `universe()` | The whole company list, in a format that can be sent to the browser. |
| `prices_between(tickers, start, end)` | Prices for chosen companies between two dates. Returns a **copy**, so nothing outside can accidentally change the stored data. |
| `float_market_caps(prices_on_date)` | Company size = free-float shares × price, for each company. |

### `index_builder/validation.py`: checking everything

**`ValidationReport`** is a notebook that collects problems as they're found.

| Function | What it does |
|---|---|
| `error(message)` | Records a problem that must stop the calculation. |
| `warn(message)` | Records something the user should know about, without stopping. |
| `ok` | True if there are no errors. |
| `raise_if_errors()` | If any errors were recorded, stops everything and reports them all together. |
| `to_dict()` | Packages the errors and warnings to send to the browser. |

**`IndexValidationError`** is the error raised by `raise_if_errors()`. It carries the full report so the server can send every message back to the user.

**`IndexRequest`** is a tidy, checked version of what the user asked for: stocks, method, dates, base level, cap and custom weights. Once one exists, the rest of the code can trust its contents.

**`_is_number(value)`** returns True only for real, finite numbers. It rejects text, true/false, "infinity" and "not a number".

**`RequestValidator`** checks the user's choices.

| Function | What it does |
|---|---|
| `validate(payload, report)` | Runs every check below and returns an `IndexRequest`, or stops with all errors listed. |
| `_tickers(...)` | At least one stock, no duplicates, all real tickers. |
| `_dates(...)` | Dates are in `YYYY-MM-DD` format, start before end, and within the data. |
| `_cap(...)` | Cap is between 0 and 100, and cap × number of stocks is at least 100%. |
| `_custom_weights(...)` | Every stock has a weight, none negative, total is 100%. Warns about 0% weights. |

**`MissingDataHandler`** applies the missing-data rules from [section 8](#8-missing-data-what-the-app-does-and-why).

| Function | What it does |
|---|---|
| `clean(prices, report, label)` | Goes through each stock, removes the ones that break a rule, fills short gaps in the rest, and records a message for every decision. |
| `_exclusion_reason(series)` | For one stock, returns the reason it must be removed, or nothing if it's fine. |
| `_longest_gap(series)` | Finds the longest run of missing days in a row. It gives each gap a group number and counts the missing days in each group. |

### `index_builder/weighting.py`: the weighting methods

| Class / function | What it does |
|---|---|
| `WeightingError` | Error raised when weights can't be built (for example, an impossible cap). |
| `WeightingScheme` | The template every weighting method follows. It says each method must have a `compute` function that takes company sizes and returns weights adding up to 100%. It can't be used on its own. |
| `WeightingScheme._normalise(raw)` | Divides each number by the total so they add up to 1 (100%). Shared by all methods. |
| `EqualWeight.compute(...)` | Gives every stock 1 ÷ N. |
| `MarketCapWeight.compute(...)` | Gives each stock its size ÷ total size. |
| `CappedMarketCapWeight.compute(...)` | Starts with market-cap weights (reusing `MarketCapWeight`), then repeatedly caps and redistributes until no stock is above the cap. |
| `CustomWeight.compute(...)` | Uses the user's percentages, rescaled to 100% if any stock was removed. |
| `create_scheme(request)` | Looks at the method name the user chose ("equal", "custom", etc.) and creates the matching weighting object. |

### `index_builder/calculator.py`: the three formulas

**`PriceReturnIndex`** does the core calculation once when it's created, then lets other code read the results.

| Function | What it does |
|---|---|
| `__init__(prices, weights, base_level)` | Applies Formula 1 (stock returns) and Formula 2 (index returns), then builds the levels. |
| `_build_levels()` | Applies Formula 3. The first day has no return, so it's set to the base level. |
| `weights`, `stock_returns`, `index_returns`, `levels` | Read-only access to the results. Each returns a copy. |
| `contributions()` | Works out how much each stock added to the total return ([section 6](#6-which-stocks-helped-contribution)). |

### `index_builder/metrics.py`: summary numbers

**`PerformanceMetrics`** takes a series of index levels and calculates the numbers in [section 7](#7-performance-metrics).

| Function | What it does |
|---|---|
| `cumulative_return()` | Total growth over the period. |
| `annualised_return()` | Equivalent steady yearly growth. |
| `annualised_volatility()` | How bumpy the ride was, per year. |
| `sharpe_ratio()` | Return per unit of risk. Returns "not a number" if volatility is zero, to avoid dividing by zero. |
| `_clean(value)` | Turns any "not a number" result into an empty value, because the data format sent to the browser (JSON) has no way to write "not a number". |
| `max_drawdown()` | Worst fall from a high point. |
| `summary()` | All of the above, plus best and worst day, in one package for the browser. |

### `index_builder/builder.py`: running everything in order

**`IndexBuilder`** is the only part of the engine the web server talks to.

| Function | What it does |
|---|---|
| `build(payload)` | Runs the full process: check input → get prices → handle missing data → weights → index → metrics → benchmark. Returns one package with everything the page needs. |
| `_weights(scheme, prices, report)` | Works out company sizes on the start date and asks the chosen weighting scheme for weights. |
| `_benchmark(request)` | Builds an equal-weighted index of all usable stocks, over the same dates and base level, to compare against. |
| `_constituents(index, prices)` | Builds the table of stocks: weight, start and end price, price return and contribution, sorted by weight. |
| `_sector_weights(weights)` | Adds up weights by sector for the sector mix chart. |

### `app.py`: the web server

| Route | What it does |
|---|---|
| `GET /` | Sends the web page. |
| `GET /api/universe` | Sends the company list, available dates and weighting methods, so the page can build itself. |
| `POST /api/generate` | Receives the user's choices, runs `IndexBuilder`, and sends back the results. If the input was invalid, sends back the error messages with status code 400 (the standard code for "the request had a problem"). |

### `static/app.js`: the browser side

No calculations happen here. It only collects input and displays results, so all the maths lives in one place (Python).

| Function | What it does |
|---|---|
| `init()` | Asks the server for the company list and dates, then builds the page. |
| `bindEvents()` | Connects buttons, checkboxes and inputs to the functions below. |
| `renderStockList()` | Draws the list of companies, filtered by the search box. |
| `refreshSelection()` | Updates the "X of 30 selected" count and sector buttons after a change. |
| `selectedMethod()` | Returns which weighting method is ticked. |
| `renderMethodOptions()` | Shows the cap box or the custom weight boxes only when they're needed. |
| `renderCustomList()` | Draws one input box per selected stock for custom weights. |
| `renderCustomTotal()` | Shows the running total of custom weights: green at 100%, red otherwise. |
| `splitEvenly()` | Fills custom weights evenly. Puts any rounding remainder on the first stock so the total is exactly 100.00%. |
| `buildPayload()` | Packages the user's choices to send to the server. |
| `generate()` | Sends the choices, waits for the answer, and shows either results or errors. |
| `renderMessages(...)` | Shows the red error box and the yellow "data decisions" box. |
| `renderResult(r)` | Fills in the headline numbers and calls the four functions below. |
| `renderChart(r)` | Draws the line chart of your index against the benchmark. |
| `renderMetrics(...)` | Fills in the performance table. |
| `renderSectors(...)` | Draws the sector mix bar. |
| `renderConstituents(...)` | Fills in the stocks table with contribution bars. |
| `downloadCsv()` | Saves the index levels and daily returns as a CSV file. |

---

## 13. How I used object-oriented programming

Object-oriented programming (OOP) means organising code into **classes**. A class is a blueprint that bundles some data together with the functions that work on it. An **object** is one thing built from that blueprint.

I gave each job in the project its own class, so each part is small, has one purpose, and can be tested on its own.

| Principle | Plain meaning | Where it's used |
|---|---|---|
| **Classes and objects** | A blueprint, and a thing built from it | `DataLoader`, `RequestValidator`, `MissingDataHandler`, `PriceReturnIndex`, `PerformanceMetrics` and `IndexBuilder` each handle one job. |
| **Encapsulation** | Keep internal details hidden and only expose what others need | `DataLoader` keeps the raw data private (`_stocks`, `_prices`) and only hands out copies, so no other code can accidentally corrupt it. `PriceReturnIndex` calculates once and only lets others *read* the results. |
| **Abstraction** | Describe *what* something does without saying *how* | `WeightingScheme` just says "every weighting method must have a `compute` function". It doesn't say how weights are worked out. |
| **Inheritance** | A new class builds on an existing one | `CappedMarketCapWeight` is built on `MarketCapWeight`. It reuses the market-cap calculation (via `super()`) and only adds the capping step. No code is duplicated. |
| **Polymorphism** | Different objects respond to the same instruction in their own way | `IndexBuilder` calls `scheme.compute(...)` without knowing or caring which method it has. Equal, market-cap, capped and custom each respond in their own way. |
| **Factory** | One function decides which object to create | `create_scheme()` turns "equal" or "custom" into the right weighting object. |

**Why this helps in practice:** to add a new weighting method (for example, one that gives each sector equal weight), I'd write one new class with a `compute` function and add one line to `create_scheme()`. Nothing else in the project would need to change.

---

## 14. Testing

The tests live in `tests/test_index_builder.py` and use Python's built-in `unittest`, so nothing extra needs installing.

| Test | What it proves |
|---|---|
| `test_matches_hand_calculation` | The three formulas give exactly the numbers I worked out by hand. |
| `test_contributions_add_up_to_cumulative_return` | Stock contributions always add up to the total return, on 50 days of random data. |
| `test_every_scheme_sums_to_one` | All four weighting methods produce weights that add up to 100%. |
| `test_cap_is_respected_and_excess_redistributed` | The capping example in section 5 gives 40% / 40% / 20%. |
| `test_custom_weights_renormalised_when_stock_excluded` | Custom weights rescale correctly when a stock is removed. |
| `test_short_gap_filled_long_gap_and_late_listing_excluded` | The missing-data rules fill, remove and warn correctly. |
| `test_generates_index` | A full run on the real data works and starts at 100. |
| `test_rejects_bad_custom_weights` | Weights that don't add up to 100% are refused. |
| `test_rejects_reversed_dates` | A start date after the end date is refused. |
| `test_two_day_range_returns_valid_json` | With only one daily return, volatility can't be calculated. It is sent as "empty" (shown as "-"), never as NaN, which browsers can't read. |
| `test_rejects_ambiguous_date_format` | A date like `01/02/2024` is refused. |
| `test_rejects_impossible_cap` | A cap that can't work with the chosen stocks is refused. |

---

## 15. Git workflow

Git is a tool that records every change to the code, so you can see its history and work on new features without breaking what already works.

I built the project in small steps, each saved as a **commit** with a message saying what changed. For larger features I created a separate **branch** (a parallel copy of the code where I could work safely), then **merged** it back into `main` when it was finished.

| Branch | What was built there |
|---|---|
| `main` | Project setup, data generator, data loader, validation, and the pipeline that ties everything together |
| `feature/weighting-schemes` | The four weighting methods, the index calculator and the metrics |
| `feature/web-ui` | The Flask server and the web page |
| `feature/tests` | Automated tests |
| `docs/readme-rewrite` | This README |
| `fix/edge-cases` | Fixed two edge cases found while testing: a 2-day range and ambiguous date formats |

Merges use `--no-ff` so each merge is clearly visible in the history. To see it:

```bash
git log --oneline --graph --all
```

---

## 16. Why I made these design choices

**Flask for the web server.** The brief asked for a web interface and a Python backend. Flask is small and simple: the whole server is about 40 lines. The browser only collects input and draws results; all calculations happen in Python. So there's one source of truth for the maths, and the same engine could later power a different front end.

**Plain HTML, CSS and JavaScript for the page.** No build tools or frameworks to install. Anyone can open the files and read them. Chart.js draws the chart because it's small and widely used.

**The engine is a separate package with no web code.** `index_builder/` doesn't import Flask at all. It can be tested on its own, used in a Jupyter notebook, or moved behind a different web framework without changing a line.

**pandas for the data.** Prices are naturally a table (dates × companies). pandas lets each formula be written as one line that works on the whole table at once, which is shorter, faster and closer to the maths than writing loops.

**All checks happen on the server.** The page shows a live total for custom weights to be helpful, but the real rules are enforced in Python. The browser can't be trusted, because someone could send data to the server without using the page at all.

**Collect every error, then report them together.** Rather than stopping at the first problem, the validator lists all of them, so the user can fix everything in one go.

**Load data once at start-up.** 30 companies × about 520 days is tiny. Keeping it in memory makes every request instant.

**Show every data decision to the user.** An index is only trustworthy if you know what went into it. Hiding a filled gap or a removed stock would make the numbers look cleaner than they really are.

---

## 17. Limitations and what I'd improve next

**The formula rebalances every day.** Applying the same weights to every day's returns means the index effectively resets to its target weights every single day. Real indices don't do that. They hold a fixed number of shares, so weights drift as prices move, and they only reset at scheduled reviews (usually every quarter). Real providers calculate this with a **divisor**:

```
index level = total value of all holdings ÷ divisor
```

The divisor is adjusted at each rebalance so the index level doesn't jump just because the holdings changed. Adding this as a second calculation option, with quarterly rebalancing and a turnover figure, would be my first improvement.

**Other limitations:**

- **Price return only.** Dividends are ignored. A total return index would add them back, but that needs dividend data.
- **No corporate actions.** Events like stock splits (one share becomes two, halving the price) would look like a 50% crash. Real data would need prices adjusted for these.
- **Company size is measured once, on the start date.** Real indices update share counts at each review.
- **Monday to Friday is used as the trading calendar.** Public holidays aren't removed.
- **One currency only.**
- **The Sharpe ratio assumes a 0% risk-free rate.**
- **Data lives in CSV files in memory.** That's fine for 30 stocks. For thousands of stocks over many years, I'd move to a database or Parquet files and cache results.

**Other ideas if I had more time:**

- Save several custom indices and compare them side by side
- Add tracking error and information ratio (how closely, and how efficiently, the index follows the benchmark)
- Sector limits (for example, no sector above 30%)
- Run the tests automatically on every push with GitHub Actions
