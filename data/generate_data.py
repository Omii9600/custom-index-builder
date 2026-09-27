"""
Generates the dummy dataset used by the app.

    python data/generate_data.py

Outputs (deterministic, because the random seed is fixed):
    data/stocks.csv  -> 30-stock universe
    data/prices.csv  -> daily close prices, long format: date, ticker, close_price

A few data problems are injected ON PURPOSE so the validation logic has
something real to handle (see README -> "Missing data handling").
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START_DATE, END_DATE = "2024-01-01", "2025-12-31"
DATA_DIR = Path(__file__).resolve().parent

# sector -> (annual drift, annual volatility, [(ticker, company name), ...])
UNIVERSE = {
    "Technology":  (0.18, 0.32, [("NOVA", "Nova Systems"), ("QBIT", "Qubit Labs"), ("CLDX", "Cloudex Networks"),
                                 ("SYNP", "Synapse Software"), ("PIXL", "Pixel Forge")]),
    "Financials":  (0.10, 0.20, [("ARKB", "Ark Bank"), ("LEDG", "Ledger Capital"), ("SHLD", "Shield Insurance"),
                                 ("VALT", "Vault Payments"), ("CRST", "Crest Asset Management")]),
    "Healthcare":  (0.09, 0.22, [("CURA", "Cura Pharma"), ("GENX", "GenX Biotech"), ("MEDL", "Medline Devices"),
                                 ("VITA", "Vita Hospitals"), ("HELX", "Helix Diagnostics")]),
    "Energy":      (0.06, 0.28, [("SOLR", "Solar Grid"), ("PTRO", "Petro Nova"), ("WNDX", "Windex Power"),
                                 ("HYDR", "Hydra Utilities"), ("VOLT", "Volt Storage")]),
    "Consumer":    (0.08, 0.18, [("BRWS", "Brew & Co"), ("URBN", "Urban Threads"), ("FRSH", "Fresh Mart"),
                                 ("GLOW", "Glow Cosmetics"), ("TRVL", "Travelo")]),
    "Industrials": (0.07, 0.21, [("STLX", "Steelux"), ("CNST", "Constructa"), ("RAIL", "Railway Corp"),
                                 ("AERO", "Aero Dynamics"), ("FRGT", "Freight Logistics")]),
}


def build_universe(rng):
    rows = []
    for sector, (_, _, names) in UNIVERSE.items():
        for ticker, name in names:
            rows.append({
                "ticker": ticker,
                "company_name": name,
                "sector": sector,
                # free-float shares in millions; float market cap = shares x price
                "free_float_shares_mn": int(rng.integers(50, 2000)),
            })
    return pd.DataFrame(rows)


def build_prices(rng):
    dates = pd.bdate_range(START_DATE, END_DATE)          # Mon-Fri trading calendar
    market = rng.normal(0.0003, 0.009, len(dates))        # shared market move -> stocks are correlated
    frames = []
    for mu, sigma, names in UNIVERSE.values():
        for ticker, _ in names:
            daily_mu, daily_sigma = mu / 252, sigma / np.sqrt(252)
            idio = rng.normal(daily_mu - 0.5 * daily_sigma ** 2, daily_sigma * 0.8, len(dates))
            closes = rng.uniform(50, 2000) * np.exp(np.cumsum(market + idio))   # geometric random walk
            frames.append(pd.DataFrame({"date": dates, "ticker": ticker, "close_price": closes.round(2)}))
    return inject_data_issues(pd.concat(frames, ignore_index=True))


def inject_data_issues(prices):
    """Deliberate, realistic data problems (documented in the README)."""
    def rows(ticker, start, end=None):
        end = end or start
        return (prices["ticker"] == ticker) & (prices["date"] >= start) & (prices["date"] <= end)

    listed_late = (prices["ticker"] == "VOLT") & (prices["date"] < "2024-07-01")   # 1) IPO on 2024-07-01
    short_gap = rows("GLOW", "2024-03-12", "2024-03-13")                            # 2) 2-day gap
    long_halt = rows("PTRO", "2025-02-03", "2025-02-12")                            # 3) 8-day trading halt
    prices = prices[~(listed_late | short_gap | long_halt)].copy()
    prices.loc[rows("FRSH", "2024-11-15"), "close_price"] = np.nan                  # 4) blank price cell
    return prices


def main():
    rng = np.random.default_rng(SEED)
    stocks = build_universe(rng)
    prices = build_prices(rng)
    stocks.to_csv(DATA_DIR / "stocks.csv", index=False)
    prices.assign(date=prices["date"].dt.strftime("%Y-%m-%d")).to_csv(DATA_DIR / "prices.csv", index=False)
    print(f"Wrote {len(stocks)} stocks and {len(prices)} price rows to {DATA_DIR}")


if __name__ == "__main__":
    main()
