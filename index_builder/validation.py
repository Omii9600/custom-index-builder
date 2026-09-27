"""Validation layer: checks user input and applies the missing-data policy.

Errors stop the calculation. Warnings let it continue but are shown to the user,
so every data decision the app makes is visible.
"""
import math
from dataclasses import dataclass, field

import pandas as pd

METHODS = {
    "equal": "Equal weight",
    "market_cap": "Float market-cap weight",
    "capped_market_cap": "Capped float market-cap weight",
    "custom": "Custom weights",
}


class ValidationReport:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)

    @property
    def ok(self):
        return not self.errors

    def raise_if_errors(self):
        if self.errors:
            raise IndexValidationError(self)

    def to_dict(self):
        return {"errors": self.errors, "warnings": self.warnings}


class IndexValidationError(Exception):
    def __init__(self, report):
        super().__init__("; ".join(report.errors))
        self.report = report


@dataclass
class IndexRequest:
    """A validated, typed version of what the user asked for."""
    tickers: list
    method: str
    start: pd.Timestamp
    end: pd.Timestamp
    base_level: float = 100.0
    cap_pct: float = None
    custom_weights_pct: dict = field(default_factory=dict)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class RequestValidator:
    WEIGHT_TOLERANCE_PCT = 0.01   # custom weights must add up to 100% +/- 0.01

    def __init__(self, loader):
        self._loader = loader

    def validate(self, payload, report):
        if not isinstance(payload, dict):
            report.error("Request body must be a JSON object.")
            report.raise_if_errors()

        tickers = self._tickers(payload.get("tickers"), report)
        method = payload.get("method")
        if method not in METHODS:
            report.error(f"Weighting method must be one of: {', '.join(METHODS)}.")
        start, end = self._dates(payload.get("start_date"), payload.get("end_date"), report)
        base_level = payload.get("base_level", 100)
        if not _is_number(base_level) or base_level <= 0:
            report.error("Base level must be a positive number.")

        cap = payload.get("cap_pct")
        if method == "capped_market_cap":
            cap = self._cap(cap, len(tickers), report)
        custom = payload.get("custom_weights") or {}
        if method == "custom":
            self._custom_weights(custom, tickers, report)

        report.raise_if_errors()
        return IndexRequest(tickers, method, start, end, float(base_level), cap, custom)

    # ---------- individual checks ----------
    def _tickers(self, tickers, report):
        if not isinstance(tickers, list) or not tickers:
            report.error("Select at least one stock.")
            return []
        if len(set(tickers)) != len(tickers):
            report.error("A stock was selected more than once.")
        unknown = [t for t in tickers if t not in self._loader.tickers]
        if unknown:
            report.error(f"Unknown ticker(s): {', '.join(map(str, unknown))}.")
        return tickers

    def _dates(self, start, end, report):
        try:
            start, end = pd.Timestamp(start), pd.Timestamp(end)
        except (TypeError, ValueError):
            report.error("Start and end dates must be valid dates (YYYY-MM-DD).")
            return None, None
        if pd.isna(start) or pd.isna(end):
            report.error("Choose both a start date and an end date.")
            return None, None
        first, last = self._loader.date_range
        if start >= end:
            report.error("Start date must be before end date.")
        if start < first or end > last:
            report.error(f"Dates must be within the available data: {first:%Y-%m-%d} to {last:%Y-%m-%d}.")
        return start, end

    @staticmethod
    def _cap(cap, n_stocks, report):
        if not _is_number(cap) or not 0 < cap <= 100:
            report.error("Weight cap must be a number between 0 and 100 (%).")
            return None
        if n_stocks and cap * n_stocks < 100:
            report.error(f"A {cap}% cap is impossible with {n_stocks} stock(s): "
                         f"weights could add up to at most {cap * n_stocks:.0f}%. Raise the cap or add stocks.")
        return float(cap)

    def _custom_weights(self, weights, tickers, report):
        if not isinstance(weights, dict):
            report.error("Custom weights must be a mapping of ticker to percent.")
            return
        missing = [t for t in tickers if t not in weights]
        extra = [t for t in weights if t not in tickers]
        if missing:
            report.error(f"Enter a weight for: {', '.join(missing)}.")
        if extra:
            report.error(f"Weights given for stocks that aren't selected: {', '.join(extra)}.")
        bad = [t for t, w in weights.items() if not _is_number(w) or w < 0]
        if bad:
            report.error(f"Weights must be numbers of 0 or more (long-only index). Check: {', '.join(bad)}.")
            return
        total = sum(weights.values())
        if abs(total - 100) > self.WEIGHT_TOLERANCE_PCT:
            report.error(f"Custom weights add up to {total:.2f}%. They must add up to 100%.")
        zero = [t for t, w in weights.items() if w == 0]
        if zero:
            report.warn(f"{', '.join(zero)} has a 0% weight and will not affect the index.")


class MissingDataHandler:
    """Missing-data policy (also documented in the README):

    1. No price on the first day of the range (e.g. listed later) -> exclude the stock.
       An index needs a starting price for every constituent.
    2. Gaps of up to MAX_FILL_DAYS trading days -> forward-fill the last known price
       (so that stock's return is 0% on those days) and warn.
    3. Longer gaps -> exclude the stock; filling them would hide real price moves.
    4. Zero or negative prices -> exclude the stock (returns can't be computed).
    """
    MAX_FILL_DAYS = 5

    def clean(self, prices, report, label="index"):
        keep = []
        for ticker in prices.columns:
            series = prices[ticker]
            reason = self._exclusion_reason(series)
            if reason:
                report.warn(f"{ticker} excluded from {label}: {reason}")
                continue
            n_missing = int(series.isna().sum())
            if n_missing:
                report.warn(f"{ticker}: {n_missing} missing day(s) forward-filled with the last known price "
                            f"(0% return on those days).")
            keep.append(ticker)

        if not keep:
            report.error("No selected stock has usable prices for this date range.")
        if len(prices.index) < 2:
            report.error("The date range must contain at least 2 trading days.")
        report.raise_if_errors()
        return prices[keep].ffill()

    def _exclusion_reason(self, series):
        if series.isna().all():
            return "no prices in the selected date range."
        if pd.isna(series.iloc[0]):
            first = series.first_valid_index()
            return f"no price on the start date (first price is on {first:%Y-%m-%d})."
        if (series.dropna() <= 0).any():
            return "contains zero or negative prices."
        longest = self._longest_gap(series)
        if longest > self.MAX_FILL_DAYS:
            return f"{longest}-day gap in prices is longer than the {self.MAX_FILL_DAYS}-day fill limit."
        return None

    @staticmethod
    def _longest_gap(series):
        missing = series.isna()
        run_id = (~missing).cumsum()            # each gap shares the id of the last valid price before it
        return int(missing.groupby(run_id).sum().max())
