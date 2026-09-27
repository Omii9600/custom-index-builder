"""Weighting schemes (Strategy pattern).

Every scheme has the same method, `compute(market_caps)`, and returns weights that
sum to 1. The index calculator doesn't care which scheme it got - that's polymorphism.
"""
from abc import ABC, abstractmethod

import pandas as pd


class WeightingError(Exception):
    """Raised when weights can't be built for the stocks that survived validation."""


class WeightingScheme(ABC):
    label = "Base scheme"

    @abstractmethod
    def compute(self, market_caps: pd.Series) -> pd.Series:
        """market_caps: float market cap per ticker on the start date (index = tickers)."""

    @staticmethod
    def _normalise(raw: pd.Series) -> pd.Series:
        total = raw.sum()
        if total <= 0:
            raise WeightingError("Weights add up to zero, so no index can be built.")
        return raw / total


class EqualWeight(WeightingScheme):
    label = "Equal weight"

    def compute(self, market_caps):
        return pd.Series(1.0 / len(market_caps), index=market_caps.index)


class MarketCapWeight(WeightingScheme):
    label = "Float market-cap weight"

    def compute(self, market_caps):
        return self._normalise(market_caps.astype(float))


class CappedMarketCapWeight(MarketCapWeight):
    """Market-cap weights, but no stock may exceed `cap`. Inherits the market-cap logic
    and adds the cap on top. Excess weight is handed to uncapped stocks in proportion to
    their size, repeating until nobody is over the cap (standard index-provider approach)."""

    def __init__(self, cap_pct):
        self.cap = cap_pct / 100
        self.label = f"Float market-cap weight, capped at {cap_pct:g}%"

    def compute(self, market_caps):
        weights = super().compute(market_caps)
        if self.cap * len(weights) < 1 - 1e-12:
            raise WeightingError(f"A {self.cap:.0%} cap is impossible with {len(weights)} usable stock(s).")
        capped = pd.Series(False, index=weights.index)
        while (weights > self.cap + 1e-12).any():
            over = weights > self.cap
            capped |= over
            excess = (weights[over] - self.cap).sum()
            weights[over] = self.cap
            free = ~capped
            if not free.any():
                break
            weights[free] += excess * weights[free] / weights[free].sum()
        return weights


class CustomWeight(WeightingScheme):
    label = "Custom weights"

    def __init__(self, weights_pct: dict):
        self._weights = pd.Series(weights_pct, dtype=float)

    def compute(self, market_caps):
        # Only stocks that survived validation; re-normalised if any were excluded.
        return self._normalise(self._weights.reindex(market_caps.index).fillna(0.0))


def create_scheme(request) -> WeightingScheme:
    """Factory: turns the method name from the UI into the right object."""
    if request.method == "equal":
        return EqualWeight()
    if request.method == "market_cap":
        return MarketCapWeight()
    if request.method == "capped_market_cap":
        return CappedMarketCapWeight(request.cap_pct)
    if request.method == "custom":
        return CustomWeight(request.custom_weights_pct)
    raise ValueError(f"Unknown weighting method: {request.method}")
