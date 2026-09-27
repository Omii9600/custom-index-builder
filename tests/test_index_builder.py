"""Run with:  python -m unittest discover tests -v"""
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from index_builder import DataLoader, IndexBuilder, IndexValidationError
from index_builder.calculator import PriceReturnIndex
from index_builder.validation import MissingDataHandler, ValidationReport
from index_builder.weighting import CappedMarketCapWeight, CustomWeight, EqualWeight, MarketCapWeight

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATES = pd.bdate_range("2024-01-01", periods=3)


class TestPriceReturnIndex(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # A: 100 -> 110 -> 99   (+10%, -10%)     B: 50 -> 50 -> 55   (0%, +10%)
        prices = pd.DataFrame({"A": [100, 110, 99], "B": [50, 50, 55]}, index=DATES, dtype=float)
        index = PriceReturnIndex(prices, pd.Series({"A": 0.5, "B": 0.5}), base_level=100)
        # day 1: 0.5*10% + 0.5*0% = 5%  -> 105
        # day 2: 0.5*-10% + 0.5*10% = 0% -> 105
        np.testing.assert_allclose(index.levels.values, [100, 105, 105])

    def test_contributions_add_up_to_cumulative_return(self):
        rng = np.random.default_rng(1)
        prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.02, (50, 3)), axis=0),
                              columns=["A", "B", "C"], index=pd.bdate_range("2024-01-01", periods=50))
        index = PriceReturnIndex(prices, pd.Series({"A": 0.2, "B": 0.3, "C": 0.5}))
        cumulative = index.levels.iloc[-1] / 100 - 1
        self.assertAlmostEqual(index.contributions().sum(), cumulative, places=10)


class TestWeighting(unittest.TestCase):
    caps = pd.Series({"A": 700.0, "B": 200.0, "C": 100.0})

    def test_every_scheme_sums_to_one(self):
        for scheme in [EqualWeight(), MarketCapWeight(), CappedMarketCapWeight(40),
                       CustomWeight({"A": 50, "B": 30, "C": 20})]:
            self.assertAlmostEqual(scheme.compute(self.caps).sum(), 1.0)

    def test_cap_is_respected_and_excess_redistributed(self):
        w = CappedMarketCapWeight(40).compute(self.caps)
        self.assertAlmostEqual(w["A"], 0.40)
        # the 30% excess goes to B and C in proportion 2:1
        self.assertAlmostEqual(w["B"], 0.40)
        self.assertAlmostEqual(w["C"], 0.20)

    def test_custom_weights_renormalised_when_stock_excluded(self):
        w = CustomWeight({"A": 50, "B": 30, "C": 20}).compute(self.caps.drop("A"))
        self.assertAlmostEqual(w["B"], 0.6)


class TestMissingData(unittest.TestCase):
    def test_short_gap_filled_long_gap_and_late_listing_excluded(self):
        idx = pd.bdate_range("2024-01-01", periods=10)
        prices = pd.DataFrame({
            "OK":    [10.0] * 10,
            "SHORT": [10, 11, np.nan, np.nan, 12, 12, 12, 12, 12, 12],
            "LONG":  [10] + [np.nan] * 7 + [10, 10],
            "LATE":  [np.nan, np.nan] + [10.0] * 8,
        }, index=idx, dtype=float)
        report = ValidationReport()
        clean = MissingDataHandler().clean(prices, report)
        self.assertEqual(list(clean.columns), ["OK", "SHORT"])
        self.assertEqual(clean["SHORT"].iloc[3], 11)       # forward-filled
        self.assertEqual(len(report.warnings), 3)


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = IndexBuilder(DataLoader(DATA_DIR))

    def payload(self, **overrides):
        base = {"tickers": ["NOVA", "ARKB", "CURA"], "method": "equal",
                "start_date": "2024-01-01", "end_date": "2025-12-31", "base_level": 100}
        return {**base, **overrides}

    def test_generates_index(self):
        result = self.builder.build(self.payload())
        self.assertTrue(result["ok"])
        self.assertEqual(result["levels"][0], 100)
        self.assertEqual(len(result["levels"]), len(result["dates"]))

    def test_rejects_bad_custom_weights(self):
        with self.assertRaises(IndexValidationError):
            self.builder.build(self.payload(method="custom", custom_weights={"NOVA": 50, "ARKB": 20, "CURA": 20}))

    def test_rejects_reversed_dates(self):
        with self.assertRaises(IndexValidationError):
            self.builder.build(self.payload(start_date="2025-01-01", end_date="2024-01-01"))

    def test_two_day_range_returns_valid_json(self):
        # One daily return -> volatility can't be calculated. It must come back as None, never NaN.
        result = self.builder.build(self.payload(start_date="2024-01-01", end_date="2024-01-02"))
        self.assertIsNone(result["metrics"]["annualised_volatility"])
        json.dumps(result, allow_nan=False)      # raises if any NaN slipped through

    def test_rejects_ambiguous_date_format(self):
        with self.assertRaises(IndexValidationError):
            self.builder.build(self.payload(start_date="01/02/2024"))

    def test_rejects_impossible_cap(self):
        with self.assertRaises(IndexValidationError):
            self.builder.build(self.payload(method="capped_market_cap", cap_pct=20))


if __name__ == "__main__":
    unittest.main()
