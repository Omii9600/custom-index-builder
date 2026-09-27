"""IndexBuilder: the single entry point the web layer talks to.

It runs the pipeline in order and knows nothing about HTTP:
    validate request -> slice prices -> handle missing data -> weights -> index -> metrics
"""
from .calculator import PriceReturnIndex
from .metrics import PerformanceMetrics
from .validation import MissingDataHandler, RequestValidator, ValidationReport
from .weighting import EqualWeight, WeightingError, create_scheme


class IndexBuilder:
    def __init__(self, loader):
        self._loader = loader
        self._validator = RequestValidator(loader)
        self._missing_data = MissingDataHandler()

    def build(self, payload: dict) -> dict:
        report = ValidationReport()
        request = self._validator.validate(payload, report)

        prices = self._loader.prices_between(request.tickers, request.start, request.end)
        prices = self._missing_data.clean(prices, report)

        scheme = create_scheme(request)
        weights = self._weights(scheme, prices, report)
        excluded = [t for t in request.tickers if t not in prices.columns]
        if excluded and request.method == "custom":
            report.warn("Custom weights of the remaining stocks were scaled up proportionally to add up to 100%.")

        index = PriceReturnIndex(prices, weights, request.base_level)
        benchmark = self._benchmark(request)

        return {
            "ok": True,
            "settings": {
                "method": scheme.label,
                "base_level": request.base_level,
                "start_date": f"{prices.index[0]:%Y-%m-%d}",
                "end_date": f"{prices.index[-1]:%Y-%m-%d}",
                "constituents": len(prices.columns),
                "excluded": excluded,
            },
            "dates": [f"{d:%Y-%m-%d}" for d in index.levels.index],
            "levels": index.levels.round(4).tolist(),
            "daily_returns": [None] + index.index_returns.round(8).tolist(),
            "metrics": PerformanceMetrics(index.levels).summary(),
            "benchmark": benchmark,
            "constituents": self._constituents(index, prices),
            "sectors": self._sector_weights(index.weights),
            **report.to_dict(),
        }

    # ---------- steps ----------
    def _weights(self, scheme, prices, report):
        market_caps = self._loader.float_market_caps(prices.iloc[0])   # float cap on the start date
        try:
            return scheme.compute(market_caps)
        except WeightingError as exc:
            report.error(str(exc))
            report.raise_if_errors()

    def _benchmark(self, request):
        """Equal-weighted index of the whole usable universe, same dates and base -> 'did my selection help?'"""
        report = ValidationReport()   # benchmark data issues are kept separate from the user's warnings
        prices = self._loader.prices_between(self._loader.tickers, request.start, request.end)
        prices = self._missing_data.clean(prices, report, label="benchmark")
        levels = PriceReturnIndex(prices, EqualWeight().compute(prices.iloc[0]), request.base_level).levels
        return {
            "label": f"Equal-weight universe ({len(prices.columns)} stocks)",
            "levels": levels.round(4).tolist(),
            "metrics": PerformanceMetrics(levels).summary(),
        }

    def _constituents(self, index, prices):
        contributions = index.contributions()
        rows = []
        for ticker in prices.columns:
            info = self._loader.stock_info(ticker)
            rows.append({
                "ticker": ticker,
                "company_name": info["company_name"],
                "sector": info["sector"],
                "weight": float(index.weights[ticker]),
                "start_price": float(prices[ticker].iloc[0]),
                "end_price": float(prices[ticker].iloc[-1]),
                "price_return": float(prices[ticker].iloc[-1] / prices[ticker].iloc[0] - 1),
                "contribution": float(contributions[ticker]),
            })
        return sorted(rows, key=lambda r: r["weight"], reverse=True)

    def _sector_weights(self, weights):
        sectors = weights.groupby(lambda t: self._loader.stock_info(t)["sector"]).sum()
        return {sector: float(w) for sector, w in sectors.sort_values(ascending=False).items()}
