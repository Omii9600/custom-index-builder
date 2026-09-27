"""The core maths. Implements exactly the three formulas from the brief:

    r_i(t)       = close_i(t) / close_i(t-1) - 1
    r_index(t)   = sum_i( w_i * r_i(t) )
    level(t)     = level(t-1) * (1 + r_index(t)),   level(start) = base

Because weights are applied to every day's returns, the weights are effectively
reset to target each day (daily rebalancing). See README -> Limitations.
"""
import pandas as pd


class PriceReturnIndex:
    def __init__(self, prices: pd.DataFrame, weights: pd.Series, base_level: float = 100.0):
        self._prices = prices
        self._weights = weights.reindex(prices.columns)
        self._base = base_level
        # Calculated once, then read through properties (encapsulation).
        self._stock_returns = prices / prices.shift(1) - 1
        self._index_returns = (self._stock_returns * self._weights).sum(axis=1, min_count=1)
        self._levels = self._build_levels()

    def _build_levels(self):
        growth = (1 + self._index_returns).fillna(1.0)     # first day has no return -> growth 1 -> base level
        return self._base * growth.cumprod()               # cumprod == level(t-1) * (1 + r_index(t)) applied day by day

    @property
    def weights(self):
        return self._weights.copy()

    @property
    def stock_returns(self):
        return self._stock_returns.iloc[1:].copy()

    @property
    def index_returns(self):
        return self._index_returns.iloc[1:].copy()

    @property
    def levels(self):
        return self._levels.copy()

    def contributions(self) -> pd.Series:
        """How much each stock added to the index's cumulative return.

        Each day the index gains level(t-1) * w_i * r_i(t) points from stock i.
        Summing those points and dividing by the base gives contributions that
        add up EXACTLY to the index's cumulative return.
        """
        previous_level = self._levels.shift(1)
        points = self._stock_returns.mul(self._weights, axis=1).mul(previous_level, axis=0)
        return points.sum() / self._base
