from enum import Enum
from dataclasses import dataclass
from datetime import date
from typing import Any, AnyStr, Dict, List
from uuid import UUID


STD_DATE_FMT = '%Y-%m-%d'


class Portfolio:
    """
    Simple value object that can be used as an input for risk attribution, VaR calculations
    and other client functions that require a portfolio as input. In general a user provides
    the desired portfolio composition in their chosen symbology and then the AssetMoster object
    can be used to do cross-referencing between multiple symbologies and Serenity's internal
    asset ID: UUID values. This lets users work with easy-to-understand portfolio definitions
    while making it a one-liner to translate for Serenity.
    """
    def __init__(self, assets: Dict[UUID, float]):
        self.assets = assets

    def get_assets(self) -> Dict[UUID, float]:
        """
        Gets the underlying map of asset ID to qty.
        """
        return self.assets

    def to_asset_positions(self) -> List[Dict[AnyStr, Any]]:
        """
        Internal helper that converts a Portfolio to the preferred format for risk attribution,
        VaR compution, VaR backtest, etc.
        """
        return [{'assetId': str(asset_id), 'quantity': qty} for (asset_id, qty) in self.assets.items()]


class MarkTime(Enum):
    """
    Snapshot time to use for daily close price purposes; as crypto is a 24x7 market users can
    choose their preferred closing time for marking books. Note that UTC will not be supported
    until the next release.
    """

    NY_EOD = 'NY_EOD'
    LN_EOD = 'LN_EOD'
    HK_EOD = 'HK_EOD'
    UTC = 'UTC'


class CashTreatment(Enum):
    """
    How should the portfolio valuator treat stablecoins? Like cash, or tokens? If CashTreatment
    is FIAT_PEGGED_STABLECOINS, it will group together USD and USD-pegged stablecoins as "cash."
    """
    FIAT_PEGGED_STABLECOINS = 'FIAT_PEGGED_STABLECOINS'
    FIAT_ONLY = 'FIAT_ONLY'


@dataclass
class CalculationContext:
    """
    Parameter object that groups together the common inputs for risk calculations. Everything
    gets defaulted, so you need only populate any overrides.
    """
    as_of_date: date = None
    model_config_id: UUID = None
    mark_time: MarkTime = MarkTime.NY_EOD
    base_currency_id: UUID = None


@dataclass
class PricingContext:
    """
    Parameter object that groups together the common inputs for valuation. Everything
    gets defaulted, so you need only populate any overrides.
    """
    as_of_date: date = None
    mark_time: MarkTime = MarkTime.NY_EOD
    cash_treatment: CashTreatment = CashTreatment.FIAT_ONLY
    base_currency_id: UUID = None
