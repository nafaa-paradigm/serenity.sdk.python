from collections import defaultdict
from enum import Enum
from dataclasses import dataclass
from datetime import date
from typing import Any, AnyStr, Dict, List, Tuple
from uuid import UUID

import pandas as pd


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


@dataclass
class Risk:
    factor_risk: float
    specific_risk: float
    total_risk: float


@dataclass
class SectorPath:
    sector_levels: List[str]

    def __str__(self) -> str:
        return '/'.join(self.sector_levels)

    def __hash__(self) -> int:
        return hash(self.__str__())


@dataclass
class FactorExposureValue:
    factor_exposure: float
    factor_exposure_base_ccy: float


@dataclass
class FactorRisk:
    factor: str
    factor_exposure: FactorExposureValue
    absolute_risk_contribution: float
    relative_risk_contribution: float
    marginal_risk_contribution: float


class RiskAttributionResult:
    """
    Result class that helps users interpret the fairly complex structured output from
    risk attribution, specifically helping break down the various pivots by asset, sector,
    etc.. IMPORTANT: there will be a breaking change in the next release which will
    change how we represent sector hierarchies on output. If you switch to using this object
    for parsing results in your notebook, the corresponding SDK upgrade will take care of
    this migration for you, so we strongly recommend replacing explicit parsing of the
    sector output with use of this object prior to that release.

    If you wish to handle newer-format data, pass backcompat_mode=False. This default will
    change after the 1 October 2022 release to allow seamless transition.
    """
    def __init__(self, raw_json: Any, backcompat_mode: bool = True):
        self.raw_json = raw_json

        self.portfolio_variance = None
        self.portfolio_volatility = None

        self.portfolio_risk_by_factor = {}

        self.absolute_risk_by_asset = {}
        self.relative_risk_by_asset = {}
        self.marginal_risk_by_asset = {}

        self.absolute_risk_by_sector = {}
        self.relative_risk_by_sector = {}

        self.absolute_risk_by_sector_and_factor = {}
        self.relative_risk_by_sector_and_factor = {}

        self.asset_sectors = {}

        self.sector_factor_exposures = {}

        if backcompat_mode:
            self._parse_raw_json_backcompat()
        else:
            self._parse_raw_json()

    def get_portfolio_volatility(self) -> Risk:
        """
        Extracts the top-level risk expressed in volatility.
        """
        return self.portfolio_volatility

    def get_portfolio_variance(self) -> Risk:
        """
        Extracts the top-level risk expressed in variance.
        """
        return self.portfolio_variance

    def get_portfolio_risk_by_factor(self) -> Dict[str, FactorRisk]:
        """
        Extracts the per-factor risks as a simple map.
        """
        return self.portfolio_risk_by_factor

    def get_absolute_risk_by_asset(self) -> Dict[UUID, Risk]:
        """
        Extracts the per-asset absolute risk values as a simple map.
        """
        return self.absolute_risk_by_asset

    def get_relative_risk_by_asset(self) -> Dict[UUID, Risk]:
        """
        Extracts the per-asset relative risk values as a simple map.
        """
        return self.relative_risk_by_asset

    def get_marginal_risk_by_asset(self) -> Dict[UUID, Risk]:
        """
        Extracts the per-asset asset marginal risk values as a simple map.
        """
        return self.marginal_risk_by_asset

    def get_absolute_risk_by_sector(self) -> Dict[SectorPath, Risk]:
        """
        Extracts the per-sector absolute risk values as a simple map;
        note that every path (e.g. sectorLevel1, sectorLevel1/sectorLevel2, etc.)
        is represented in the map, so you can pull risks at any level in the tree.
        """
        return self.absolute_risk_by_sector

    def get_relative_risk_by_sector(self) -> Dict[SectorPath, Risk]:
        """
        Extracts the per-sector relative risk values as a simple map;
        note that every path (e.g. sectorLevel1, sectorLevel1/sectorLevel2, etc.)
        is represented in the map, so you can pull risks at any level in the tree.
        """
        return self.relative_risk_by_sector

    def get_absolute_risk_by_sector_and_factor(self) -> Dict[SectorPath, Dict[AnyStr, Risk]]:
        """
        Extracts the per-sector absolute risk values as a two-level map from SectorPath to factor name to Risk;
        note only the full sectorLevel1/sectorLevel2/sectorLevel3 is populated for SectorPath.
        """
        return self.absolute_risk_by_sector_and_factor

    def get_relative_risk_by_sector_and_factor(self) -> Dict[SectorPath, Risk]:
        """
        Extracts the per-sector relative risk values as a two-level map from SectorPath to factor name to Risk;
        note only the full sectorLevel1/sectorLevel2/sectorLevel3 is populated for SectorPath.
        """
        return self.relative_risk_by_sector_and_factor

    def get_asset_sectors(self) -> Dict[UUID, SectorPath]:
        """
        Gets a mapping from assetId to SectorPath.
        """
        return self.asset_sectors

    def get_sector_factor_exposures(self) -> Dict[SectorPath, Dict[str, FactorExposureValue]]:
        """
        Gets a mapping from sector path to the factor exposure for that sector, by factor name.
        """
        return self.sector_factor_exposures

    def to_asset_risk_data_frame(self, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of all the by-asset risk data, with
        the asset's sector path provided for reference; note that if you want sector aggregate
        risks you need to use to_factor_sector_risk_data_frame() as this content is available
        at multiple levels in the hierarchy whilst this representation is strictly leaf level:

        - sectorLevel1
        - sectorLevel2
        - sectorLevel3
        - assetId
        - assetNativeSymbol
        - assetSerenitySymbol
        - absoluteFactorRisk
        - absoluteSpecificRisk
        - absoluteTotalRisk
        - relativeFactorRisk
        - relativeSpecificRisk
        - relativeTotalRisk
        - marginalFactorRisk
        - marginalSpecificRisk
        - marginalTotalRisk
        """
        return pd.DataFrame.empty

    def to_sector_risk_data_frame(self, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of the all the by-sector risk data:

        - sectorLevel1
        - sectorLevel2
        - sectorLevel3
        - absoluteFactorRisk
        - absoluteSpecificRisk
        - absoluteTotalRisk
        - relativeFactorRisk
        - relativeSpecificRisk
        - relativeTotalRisk
        - factorExposure
        - factorExposureBaseCcy
        """
        return pd.DataFrame.empty

    def to_factor_sector_risk_data_frame(self, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of the all the by-sector, by-factor risk data:

        - sectorLevel1
        - sectorLevel2
        - sectorLevel3
        - factor
        - absoluteFactorRisk
        - absoluteSpecificRisk
        - absoluteTotalRisk
        - relativeFactorRisk
        - relativeSpecificRisk
        - relativeTotalRisk
        - factorExposureBaseCcy
        """
        return pd.DataFrame.empty

    def to_factor_risk_data_frame(self, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of the all the by-factor risk data at the portfolio level:

        - factor
        - absoluteRiskContribution
        - relativeRiskContribution
        - marginalRiskContribution
        - factorExposureBaseCcy
        """
        return pd.DataFrame.empty

    def get_raw_output(self) -> Any:
        """
        Gets the full JSON object returned from the risk attribution API.
        """
        return self.raw_json

    def _parse_raw_json(self):
        """
        Handles parsing output from Risk Attribution [V2] - Ricardo
        """
        self._parse_raw_json_common()

        # the sector breakdown changed between Smith and Ricardo -- this needs different handling
        self.absolute_risk_by_asset, self.absolute_risk_by_sector, self.absolute_risk_by_sector_and_factor = \
            self._parse_risk_contribution('absoluteContributionRisk')
        self.relative_risk_by_asset, self.relative_risk_by_sector, self.relative_risk_by_sector_and_factor = \
            self._parse_risk_contribution('relativeContributionRisk')

        # handle path-based sector breakdown for exposures; yes, I know the double dictionary comprehension is bonkers
        self.sector_factor_exposures = {SectorPath(sector_exposure['sectorLevels']):
                                        {factor_exposure['factor']: self._parse_factor_exposure_object(factor_exposure)
                                         for factor_exposure in sector_exposure['factorRisk']}
                                        for sector_exposure in self.raw_json['sectorFactorExposure']}

    def _parse_raw_json_backcompat(self):
        """
        Handles parsing output from Risk Attribution [V1] - Smith
        """
        # take care of common fields first
        self._parse_raw_json_common()

        # the sector breakdown changed between Smith and Ricardo -- this needs different handling
        self.absolute_risk_by_asset, self.absolute_risk_by_sector, self.absolute_risk_by_sector_and_factor = \
            self._parse_risk_contribution_backcompat('absoluteContributionRisk')
        self.relative_risk_by_asset, self.relative_risk_by_sector, self.relative_risk_by_sector_and_factor = \
            self._parse_risk_contribution_backcompat('relativeContributionRisk')

        # factor exposure breakdown by sector in Smith only supports the sector and parent tuple
        self.sector_factor_exposures = {SectorPath([sector_exposure['parentSector'], sector_exposure['sector']]):
                                        {factor_exposure['factor']: self._parse_factor_exposure_object(factor_exposure)
                                         for factor_exposure in sector_exposure['factorRisk']}
                                        for sector_exposure in self.raw_json['sectorFactorExposure']}

    def _parse_raw_json_common(self):
        """
        Handles parsing elements unchanged between Smith and Ricardo.
        """
        self.portfolio_variance = self._parse_total_risk('volatility')
        self.portfolio_variance = self._parse_total_risk('variance')

        self.portfolio_risk_by_factor = {risk_obj['factor']: self._parse_factor_risk_object(risk_obj)
                                         for risk_obj in self.raw_json['factorRisk']}

        self.marginal_risk_by_asset = {UUID(risk_obj['assetId']): self._parse_risk_object(risk_obj)
                                       for risk_obj in self.raw_json['assetMarginalRisk']}

    def _parse_total_risk(self, risk_measure: str) -> Risk:
        obj = self.raw_json['totalRisk'][risk_measure]
        return self._parse_risk_object(obj)

    def _parse_risk_contribution(self, risk_measure: str) -> Tuple:
        """
        Handle the Ricardo-style sector paths, which include every segment in the path.
        """
        contrib_obj = self.raw_json[risk_measure]
        risk_by_asset = {UUID(risk_obj['assetId']): self._parse_risk_object(risk_obj)
                         for risk_obj in contrib_obj['byAsset']}
        risk_by_sector = {SectorPath(risk_obj['sectorLevels']): self._parse_risk_object(risk_obj)
                          for risk_obj in contrib_obj['bySector']}
        risk_by_sector_and_factor = {}  # will be supported in Ricardo
        return (risk_by_asset, risk_by_sector, risk_by_sector_and_factor)

    def _parse_risk_contribution_backcompat(self, risk_measure: str) -> Tuple:
        """
        Handle the Smith-style sector paths, which are parent sector and sector only.
        """
        contrib_obj = self.raw_json[risk_measure]
        risk_by_asset = {UUID(risk_obj['assetId']): self._parse_risk_object(risk_obj)
                         for risk_obj in contrib_obj['byAsset']}
        risk_by_sector = {SectorPath([risk_obj['parentSector'], risk_obj['sector']]): self._parse_risk_object(risk_obj)
                          for risk_obj in contrib_obj['bySector']}
        risk_by_sector_and_factor = {}  # not supported in Smith
        return (risk_by_asset, risk_by_sector, risk_by_sector_and_factor)

    def _parse_risk_object(self, obj: Any) -> Risk:
        factor_risk = obj['factorRisk']
        specific_risk = obj['specificRisk']
        total_risk = obj['totalRisk']
        return Risk(factor_risk, specific_risk, total_risk)

    def _parse_factor_risk_object(self, obj: Any) -> FactorRisk:
        factor = obj['factor']
        factor_exposure = self._parse_factor_exposure_object(obj)
        absolute_contrib = obj['absoluteContribution']
        relative_contrib = obj['relativeContribution']
        marginal_contrib = obj['marginalContribution']
        return FactorRisk(factor, factor_exposure, absolute_contrib, relative_contrib, marginal_contrib)

    def _parse_factor_exposure_object(self, obj: Any) -> FactorExposureValue:
        factor_exposure = obj['factorExposure']
        factor_exposure_base_ccy = obj.get('factorExposureBaseCcy', 0)
        return FactorExposureValue(factor_exposure, factor_exposure_base_ccy)


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
        self.model_config_map = {model_config['shortName']: UUID(model_config['modelConfigId'])
                                 for model_config in model_configs}

    def get_model_class_names(self) -> List[str]:
        """
        Enumerates the names of model classes, groupings of related models like Market Risk,
        Liquidity Risk or Value at Risk.
        """
        # allow for missing displayName until production upgraded
        return [model_class.get('displayName', model_class['shortName']) for model_class in self.model_classes]

    def get_model_names(self) -> List[str]:
        """
        Enumerates the names of all models; this corresponds to code implementations
        of different types of models.
        """
        # allow for missing displayName until production upgraded
        return [model.get('displayName', model['shortName']) for model in self.models]

    def get_model_configurations(self) -> Dict[AnyStr, AnyStr]:
        """
        Enumerates the names of all model configurations; this corresponds to specific
        parameterizations of models, e.g. short time horizon and long time horizon
        variations of a factor risk model are two different configurations.
        """

        # allow for missing displayName until production upgraded
        return {model_config['shortName']: model_config.get('displayName', None) for model_config in self.model_configs}

    def get_model_configuration_id(self, short_name: str) -> UUID:
        """
        Lookup function that gives you the UUID of a ModelConfiguration given
        its short name. Returns None if unknown.
        """
        model_config_id = self.model_config_map.get(short_name, None)
        if not model_config_id:
            raise ValueError(f'Unknown ModelConfiguration: {short_name}')
        return model_config_id
