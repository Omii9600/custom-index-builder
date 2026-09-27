"""Summary statistics for an index level series."""
import numpy as np
import pandas as pd


class PerformanceMetrics:
    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, levels: pd.Series):
        self._levels = levels
        self._returns = levels.pct_change().dropna()

    def cumulative_return(self):
        return self._levels.iloc[-1] / self._levels.iloc[0] - 1

    def annualised_return(self):
        years = len(self._returns) / self.TRADING_DAYS_PER_YEAR
        return (1 + self.cumulative_return()) ** (1 / years) - 1

    def annualised_volatility(self):
        return self._returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

    def sharpe_ratio(self):
        """Risk-free rate assumed to be 0 for simplicity."""
        vol = self.annualised_volatility()
        return self.annualised_return() / vol if vol > 0 else float("nan")

    def max_drawdown(self):
        """Largest peak-to-trough fall, e.g. -0.15 = the index once fell 15% from a high."""
        return (self._levels / self._levels.cummax() - 1).min()

    @staticmethod
    def _clean(value):
        """JSON has no NaN. A metric that can't be calculated (e.g. volatility from a
        single daily return) is sent as None, which the page shows as "-"."""
        value = float(value)
        return value if np.isfinite(value) else None

    def summary(self):
        best, worst = self._returns.idxmax(), self._returns.idxmin()
        return {
            "start_level": float(self._levels.iloc[0]),
            "end_level": float(self._levels.iloc[-1]),
            "cumulative_return": self._clean(self.cumulative_return()),
            "annualised_return": self._clean(self.annualised_return()),
            "annualised_volatility": self._clean(self.annualised_volatility()),
            "sharpe_ratio": self._clean(self.sharpe_ratio()),
            "max_drawdown": self._clean(self.max_drawdown()),
            "best_day": {"date": f"{best:%Y-%m-%d}", "return": float(self._returns[best])},
            "worst_day": {"date": f"{worst:%Y-%m-%d}", "return": float(self._returns[worst])},
            "trading_days": int(len(self._levels)),
        }
