from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, List
from uuid import UUID

from serenity_sdk.types.common import STD_DATE_FMT


class VaRQuantile:
    # forward declaration
    pass


@dataclass
class VaRQuantile:
    """
    Helper class that repersents a single VaR quantile, e.g. 90th percentile VaR.
    """
    quantile: float
    var_absolute: float
    var_relative: float

    @staticmethod
    def parse(raw_json: Any) -> VaRQuantile:
        quantile = raw_json['quantile']
        var_absolute = raw_json['varAbsolute']
        var_relative = raw_json['varRelative']
        return VaRQuantile(quantile, var_absolute, var_relative)


class VaRBreach:
    # forward declaration
    pass


@dataclass
class VaRBreach:
    """
    Helper class that represents a single VaR breach, a day when the portfolio losses exceeded the forecast.
    """
    breach_date: date
    portfolio_loss_absolute: float
    portfolio_loss_relative: float
    quantiles: List[VaRQuantile]

    @staticmethod
    def parse(raw_json: Any, backcompat: bool = True, backcompat_quantile: float = None) -> VaRBreach:
        breach_date = datetime.strptime(raw_json['breachDate'], STD_DATE_FMT)
        portfolio_loss_absolute = raw_json['portfolioLossAbsolute']
        portfolio_loss_relative = raw_json['portfolioLossRelative']
        if backcompat:
            var_absolute = raw_json['varLevelAbsolute']
            var_relative = raw_json['varLevelRelative']
            quantiles = [VaRQuantile(99, var_absolute, var_relative)]
        else:
            quantiles = [VaRQuantile.parse(quantile) for quantile in raw_json['quantiles']]
        return VaRBreach(breach_date, portfolio_loss_absolute, portfolio_loss_relative, quantiles)


class VaRAnalysisResult:
    # forward declaration
    pass


@dataclass
class VaRAnalysisResult:
    """
    Result class that helps users interpret the output of the VaR model, e.g. processing quantiles.
    """
    run_date: date
    baseline: float
    quantiles: List[VaRQuantile]
    excluded_assets: List[UUID]
    warnings: List[str]

    @staticmethod
    def parse(raw_json: Any, backcompat: bool = True) -> VaRAnalysisResult:
        run_date = datetime.strptime(raw_json['runDate'], STD_DATE_FMT)
        baseline = raw_json['baseline']
        quantiles = [VaRQuantile.parse(quantile) for quantile in raw_json['quantiles']]
        excluded_assets = [UUID(asset_id) for asset_id in raw_json['excludedAssetIds']]
        if backcompat:
            warnings = []
        else:
            warnings = raw_json.get('warnings', [])

        return VaRAnalysisResult(run_date, baseline, quantiles, excluded_assets, warnings)


class VaRBacktestResult:
    # forward declaration
    pass


@dataclass
class VaRBacktestResult:
    """
    Result class that helps users interpret the output of the VaR model backtester, e.g. processing breaches.
    """
    results: List[VaRAnalysisResult]
    breaches: List[VaRBreach]
    warnings: List[str]

    @staticmethod
    def parse(raw_json: Any, backcompat: bool = True, backcompat_quantile: float = None) -> VaRBacktestResult:
        results = [VaRAnalysisResult.parse(result, backcompat) for result in raw_json['results']]
        breaches = [VaRBreach.parse(breach, backcompat, backcompat_quantile) for breach in raw_json['breaches']]
        if backcompat:
            warnings = []
        else:
            warnings = raw_json['warnings']
        return VaRBacktestResult(results, breaches, warnings)
