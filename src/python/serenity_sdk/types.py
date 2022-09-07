from collections import defaultdict
from enum import Enum
from datetime import date
from typing import Any, AnyStr, Dict, List
from uuid import UUID


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


class CalculationContext:
    """
    Paramter object that groups together the common inputs for risk calculations. Everything
    gets defaulted, so you need only populate any overrides.
    """
    as_of_date: date = None
    model_config_id: UUID = None
    mark_time: MarkTime = MarkTime.NY_EOD
    base_currency_id: UUID = None


class SectorTaxonomy(Enum):
    """
    Transition enum until the next release is deployed, supporting lookup via API of
    sector taxonomy UUID's so you can use arbitrary taxonomies (including user-defined)
    """
    DACS = "DACS"
    DATS = "DATS"


class AssetMaster:
    """
    Result class that holds the contents of the Serenity asset catalog in memory,
    making it easier to query it and also to create Portfolio objects from it.
    """
    def __init__(self, asset_summaries: List[Any]):
        self.asset_summaries = asset_summaries

        # map UUID => authority => symbol
        self.asset_id_map = {summary['assetId']: {xref_symbol['authority']['name']: xref_symbol['symbol']
                             for xref_symbol in summary['xrefSymbols']} for summary in asset_summaries}

        # inverse map authority => symbol => UUID
        self.asset_id_map = defaultdict(dict)
        self.symbol_map = defaultdict(dict)
        for summary in asset_summaries:
            asset_id = summary['assetId']
            native_symbol = summary['nativeSymbol']
            asset_symbol = summary['assetSymbol']
            for xref_symbol in summary['xrefSymbols']:
                authority = xref_symbol['authority']['name']
                symbol = xref_symbol['symbol']

                self.asset_id_map[asset_id][authority] = symbol
                self.asset_id_map[asset_id]['NATIVE'] = native_symbol
                self.asset_id_map[asset_id]['SERENITY'] = asset_symbol

                self.symbol_map[authority][symbol] = asset_id
                self.symbol_map['NATIVE'][native_symbol] = asset_id
                self.symbol_map['SERENITY'][asset_symbol] = asset_id

    def create_portfolio(self, positions: Dict[AnyStr, float], symbology: str = 'NATIVE') -> Portfolio:
        """
        Mapping function that takes a set of raw positions in a given symbology and then converts them
        to Serenity's internal identifiers and creates a Portfolio that can then be used with our tools.
        Note there are two 'special' symbologies, NATiVE and SERENITY. NATIVE uses the native blockchain
        symbol and SERENITY uses Serenity's own native symbology, e.g. BTC and tok.btc.bitcoin
        respectively. The rest correspond to the API's list of symbol authorities, e.g. COINGECKO.
        """
        asset_positions = {self.get_asset_id_by_symbol(symbol, symbology): qty for (symbol, qty) in positions.items()}
        return Portfolio(asset_positions)

    def get_symbol_by_id(self, asset_id: UUID, symbology: str = 'NATIVE'):
        """
        Lookup helper that gets a particular symbol type for a given asset ID.
        """
        asset_id_symbols = self.asset_id_map.get(asset_id, None)
        if not asset_id_symbols:
            raise ValueError(f'Unknown asset_id: {asset_id}')

        symbol = asset_id_symbols.get(symbology, None)
        if not symbol:
            raise ValueError(f'Unknown symbology {symbology} for asset_id: {asset_id}')

        return symbol

    def get_asset_id_by_symbol(self, symbol: str, symbology: str = 'NATIVE'):
        """
        Lookup helper that looks up asset ID by symbol based on a given symbology.
        """
        symbology_symbols = self.symbol_map.get(symbology, None)
        if not symbology_symbols:
            raise ValueError(f'Unknown symbology {symbology} for symbol: {symbol}')

        asset_id = symbology_symbols.get(symbol, None)
        if not asset_id:
            raise ValueError(f'Unknown symbol {symbol} in symbology {symbology}')

        return asset_id


class FactorModelOutputs:
    """
    Result class that holds all the factor model outputs for a given day. This simplifies
    manipulation of the various API endpoints by fetching everything together and then
    making it available as an in-memory snapshot for display and analysis.
    """
    pass


class RiskAttributionResult:
    """
    Result class that helps users interpret the fairly complex structured output from
    risk attribution, specifically helping break down the various pivots by asset, sector,
    etc.. IMPORTANT: there will be a breaking change in the next release which will
    change how we represent sector hierarchies on output. If you switch to using this object
    for parsing results in your notebook, the corresponding SDK upgrade will take care of
    this migration for you, so we strongly recommend replacing explicit parsing of the
    sector output with use of this object prior to that release.
    """
    pass


class VaRModel(Enum):
    """
    Temporary workaround before the next release that lets you specify the VaR model type with an
    enum rather than via a modelConfigId UUID.
    """
    VAR_HISTORICAL = 'VAR_HISTORICAL'
    VAR_PARAMETRIC_NORMAL = 'VAR_PARAMETRIC_NORMAL'


class VaRResult:
    """
    Result class that helps users interpret the output of the VaR model, e.g. processing quartiles.
    """
    pass


class VaRBacktestResult:
    """
    Result class that helps users interpret the output of the VaR model backtester, e.g. processing breaches.
    """
    pass


class ModelMetadata:
    """
    Helper class that encapsulates all the model metadata. You can get at the underlying calls directly from the
    ModelApi client or you can just load everything in this class and use it to traverse the metadata tree.

    The most important call is probably get_model_configuration_id(), which lets you do a lookup of a
    ModelConfiguration ID by the short name. This is needed to specify model inputs for risk calcs.
    """
    def __init__(self, model_classes: List[Any],  models: List[Any], model_configs: List[Any]):
        self.model_classes = model_classes
        self.models = models
        self.model_configs = model_configs
        self.model_config_map = {model_config['shortName']: model_config['modelConfigId']
                                 for model_config in model_configs}

    def get_model_class_names(self) -> List[str]:
        """
        Enumerates the names of model classes, groupings of related models like Market Risk,
        Liquidity Risk or Value at Risk.
        """
        return [model_class['displayName'] for model_class in self.model_classes]

    def get_model_names(self) -> List[str]:
        """
        Enumerates the names of all models; this corresponds to code implementations
        of different types of models.
        """
        return [model['displayName'] for model in self.models]

    def get_model_configuration_names(self) -> List[str]:
        """
        Enumerates the naems of all model configurations; this corresponds to specific
        parameterizations of models, e.g. short time horizon and long time horizon
        variations of a factor risk model are two different configurations.
        """
        return [model_config['displayName'] for model_config in self.model_configs]

    def get_model_configuration_id(self, short_name: str) -> UUID:
        """
        Lookup function that gives you the UUID of a ModelConfiguration given
        its short name. Returns None if unknown.
        """
        model_config_id = self.model_config_map.get(short_name, None)
        if not model_config_id:
            raise ValueError(f'Unknown ModelConfiguration: {short_name}')
        return model_config_id
