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
    """
    The portion of the return distribution to consider when evaluating VaR, e.g. 99th percentile max loss
    """

    var_absolute: float
    """
    The forecast loss according to the VaR model for the given quantile, expressed in base currency
    """

    var_relative: float
    """
    The ratio of VaR Absolute and the portfolio’s value (PV), expressed as a percentage
    """

    @staticmethod
    def _parse(raw_json: Any) -> VaRQuantile:
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
    """
    The date on which the portfolio's loss exceeded ("breached") the prior day's VaR forecast loss at a given quantile
    """

    portfolio_loss_absolute: float
    """
    The portfolio loss on the breach date, expressed in base currency terms
    """

    portfolio_loss_relative: float
    """
    The ratio of the portfolio loss on the breach date vs. the portfolio value (PV), expressed in percentage
    """

    quantiles: List[VaRQuantile]
    """
    The quantiles whose VaR estimate was breached on this date
    """

    @staticmethod
    def _parse(raw_json: Any) -> VaRBreach:
        breach_date = datetime.strptime(raw_json['breachDate'], STD_DATE_FMT)
        portfolio_loss_absolute = raw_json['portfolioLossAbsolute']
        portfolio_loss_relative = raw_json['portfolioLossRelative']
        quantiles = [VaRQuantile._parse(quantile) for quantile in raw_json['quantiles']]
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
    """
    The date as-of which we ran the VaR calculation
    """

    baseline: float
    """
    The previous day’s value (PV) of the portfolio, computed using close prices with reference to the Mark Time
    """

    quantiles: List[VaRQuantile]
    """
    A list of the VaR calculation results for all requested quantiles
    """

    excluded_assets: List[UUID]
    """
    The ID's of any assets that were excluded from the VaR calculation, e.g. due to lack of data
    """

    warnings: List[str]
    """
    A list of warning messages from the VaR model
    """

    @staticmethod
    def _parse(raw_json: Any) -> VaRAnalysisResult:
        run_date = datetime.strptime(raw_json['runDate'], STD_DATE_FMT)
        baseline = raw_json['baseline']
        quantiles = [VaRQuantile._parse(quantile) for quantile in raw_json['quantiles']]
        excluded_assets = [UUID(asset_id) for asset_id in raw_json['excludedAssetIds']]
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
    """
    A list of all VaR calculation results for all datess
    """

    breaches: List[VaRBreach]
    """
    A list of all dates on which VaR for one or more requested quatiles was breached
    """

    warnings: List[str]
    """
    A list of warning messages from the VaR model
    """

    @staticmethod
    def _parse(raw_json: Any) -> VaRBacktestResult:
        results = [VaRAnalysisResult._parse(result) for result in raw_json['results']]
        breaches = [VaRBreach._parse(breach) for breach in raw_json['breaches']]
        warnings = raw_json['warnings']
        return VaRBacktestResult(results, breaches, warnings)
