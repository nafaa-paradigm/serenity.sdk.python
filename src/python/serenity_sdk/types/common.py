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
        """
        :param assets: a mapping from asset ID to qty, where negative qty is taken as a short position
        """
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
    """
    Prices as of 4:30PM New York-local time
    """

    LN_EOD = 'LN_EOD'
    """
    Prices as of 4:30PM London-local time
    """

    HK_EOD = 'HK_EOD'
    """
    Prices as of 4:00PM Hong Kong-local time
    """

    UTC = 'UTC'
    """
    Prices as of UTC midnight
    """


class CashTreatment(Enum):
    """
    How should the portfolio valuator treat stablecoins? Like cash, or tokens? If CashTreatment
    is FIAT_PEGGED_STABLECOINS, it will group together USD and USD-pegged stablecoins as "cash."
    """
    FIAT_PEGGED_STABLECOINS = 'FIAT_PEGGED_STABLECOINS'
    """
    Treat fiat-pegged stablecoins like cash
    """

    FIAT_ONLY = 'FIAT_ONLY'
    """
    Only treat fiat currencies as cash
    """


@dataclass
class CalculationContext:
    """
    Parameter object that groups together the common inputs for risk calculations. Everything
    gets defaulted, so you need only populate any overrides.
    """
    as_of_date: date = None
    """
    The effective date for all data loaded from Serenity's bitemporal database
    """

    model_config_id: UUID = None
    """
    The factor risk or VaR model to use for calculations or when loading pre-computed matrices and other results
    """

    mark_time: MarkTime = MarkTime.NY_EOD
    """
    The mark time to use by convention for "close" in the 24x7 digital asset markets
    """

    base_currency_id: UUID = None
    """
    The currency to use to expresss the value of portfolios, positions and exposures; in current version only USD is
    supported but later on can be any asset
    """


@dataclass
class PricingContext:
    """
    Parameter object that groups together the common inputs for valuation. Everything
    gets defaulted, so you need only populate any overrides.
    """
    as_of_date: date = None
    """
    The effective date for all data loaded from Serenity's bitemporal database
    """

    mark_time: MarkTime = MarkTime.NY_EOD
    """
    The mark time to use by convention for "close" in the 24x7 digital asset markets
    """

    cash_treatment: CashTreatment = CashTreatment.FIAT_ONLY
    """
    How the valuation logic should define "cash position"
    """

    base_currency_id: UUID = None
    """
    The currency to use to expresss the value of portfolios, positions and exposures; in current version only USD is
    supported but later on can be any asset
    """


@dataclass
class SectorPath:
    sector_levels: List[str]

    def create_lookup_key(self, leaf_name: str):
        """
        Helper function that joins the path segments with a terminal
        node like an asset ID or a factor name. This gives you a unique
        key for building tables that are indexed by these tuples.
        """
        return f'{str(self)}/{leaf_name}'

    def __str__(self) -> str:
        return '/'.join(self.sector_levels)

    def __hash__(self) -> int:
        return hash(self.__str__())
