"""Data layer: reads the CSV files once, validates their structure, and serves clean slices."""
from pathlib import Path

import pandas as pd


class DataError(Exception):
    """Raised when a data file is missing or structurally broken."""


class DataLoader:
    STOCK_COLUMNS = {"ticker", "company_name", "sector", "free_float_shares_mn"}
    PRICE_COLUMNS = {"date", "ticker", "close_price"}

    def __init__(self, data_dir):
        data_dir = Path(data_dir)
        self._stocks = self._load_stocks(data_dir / "stocks.csv")
        self._prices = self._load_prices(data_dir / "prices.csv")   # wide table: rows = dates, columns = tickers

    # ---------- loading (private: callers never touch raw files) ----------
    @staticmethod
    def _read_csv(path, required_columns):
        if not path.exists():
            raise DataError(f"Data file not found: {path.name}. Run: python data/generate_data.py")
        df = pd.read_csv(path)
        missing = required_columns - set(df.columns)
        if missing:
            raise DataError(f"{path.name} is missing column(s): {', '.join(sorted(missing))}")
        return df

    def _load_stocks(self, path):
        stocks = self._read_csv(path, self.STOCK_COLUMNS)
        if stocks["ticker"].duplicated().any():
            raise DataError("stocks.csv contains duplicate tickers")
        stocks["free_float_shares_mn"] = pd.to_numeric(stocks["free_float_shares_mn"], errors="coerce")
        if (stocks["free_float_shares_mn"].isna() | (stocks["free_float_shares_mn"] <= 0)).any():
            raise DataError("stocks.csv: free_float_shares_mn must be a positive number for every stock")
        return stocks.set_index("ticker")

    def _load_prices(self, path):
        prices = self._read_csv(path, self.PRICE_COLUMNS)
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
        prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")  # blanks/text -> NaN
        if prices["date"].isna().any():
            raise DataError("prices.csv contains unreadable dates")
        if prices.duplicated(["date", "ticker"]).any():
            raise DataError("prices.csv has more than one price for the same date and ticker")
        unknown = set(prices["ticker"]) - set(self._stocks.index)
        if unknown:
            raise DataError(f"prices.csv has tickers not in stocks.csv: {', '.join(sorted(unknown))}")
        # long -> wide. A missing row and a blank price both become NaN, so they are handled the same way.
        wide = prices.pivot(index="date", columns="ticker", values="close_price")
        return wide.reindex(columns=self._stocks.index).sort_index()

    # ---------- public, read-only access ----------
    @property
    def tickers(self):
        return list(self._stocks.index)

    @property
    def date_range(self):
        return self._prices.index.min(), self._prices.index.max()

    def stock_info(self, ticker):
        return self._stocks.loc[ticker]

    def universe(self):
        """Universe as a list of dicts (for the API)."""
        return self._stocks.reset_index().to_dict(orient="records")

    def prices_between(self, tickers, start, end):
        """Close prices for the given tickers between two dates (copy, so callers can't corrupt the cache)."""
        return self._prices.loc[start:end, list(tickers)].copy()

    def float_market_caps(self, prices_on_date):
        """Float market cap = free-float shares x price, for the tickers in `prices_on_date`."""
        shares = self._stocks.loc[prices_on_date.index, "free_float_shares_mn"]
        return shares * prices_on_date
