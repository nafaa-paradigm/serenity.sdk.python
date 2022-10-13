from collections import defaultdict
from enum import Enum
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, AnyStr, Dict, List, Tuple
from uuid import UUID

import pandas as pd


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
            asset_id = UUID(summary['assetId'])
            native_symbol = summary['nativeSymbol']
            asset_symbol = summary['assetSymbol']

            # add in aliases from various vendors
            for xref_symbol in summary['xrefSymbols']:
                authority = xref_symbol['authority']['name']
                symbol = xref_symbol['symbol']

                self.asset_id_map[asset_id][authority] = symbol
                self.asset_id_map[asset_id]['NATIVE'] = native_symbol
                self.asset_id_map[asset_id]['SERENITY'] = asset_symbol

                self.symbol_map[authority][symbol] = asset_id

            # add in pseudo-symbols for looking up blockchain-native and Serenity symbologies
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
            raise ValueError(f'Unknown asset_id: {str(asset_id)}')

        symbol = asset_id_symbols.get(symbology, None)
        if not symbol:
            raise ValueError(f'Unknown symbology {symbology} for asset_id: {str(asset_id)}')

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
    etc.. We strongly recommend using this to ease migrations when output formats change.
    """
    def __init__(self, raw_json: Any):
        self.raw_json = raw_json

        self.portfolio_variance = None
        self.portfolio_volatility = None

        self.portfolio_risk_by_factor = {}

        self.absolute_risk_by_asset = {}
        self.relative_risk_by_asset = {}
        self.marginal_risk_by_asset = {}

        self.absolute_risk_by_sector = {}
        self.relative_risk_by_sector = {}

        # internal only: we do not yet return the necessary bySector attribute
        # in any of the Risk Attribution API versions, and so taking out the
        # public method calls to get at this and produce DataFrames until ready.
        self.absolute_risk_by_sector_and_factor = {}
        self.relative_risk_by_sector_and_factor = {}
        self.asset_sectors = {}

        self.sector_factor_exposures = {}

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

    def get_asset_sectors(self) -> Dict[UUID, SectorPath]:
        """
        Gets a mapping from assetId to SectorPath. Not yet supported.
        """
        return self.asset_sectors

    def get_sector_factor_exposures(self) -> Dict[SectorPath, Dict[str, FactorExposureValue]]:
        """
        Gets a mapping from sector path to the factor exposure for that sector, by factor name.
        """
        return self.sector_factor_exposures

    def to_asset_risk_data_frame(self, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of all the by-asset risk data:

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
        asset_info_df = self._to_asset_info_df(self.absolute_risk_by_asset.keys(), asset_master)
        abs_risk_df = self._to_by_asset_df(self.absolute_risk_by_asset, 'absolute')
        rel_risk_df = self._to_by_asset_df(self.relative_risk_by_asset, 'relative')
        marginal_risk_df = self._to_by_asset_df(self.marginal_risk_by_asset, 'marginal')
        df = asset_info_df
        df = pd.merge(df, abs_risk_df, left_index=True, right_index=True)
        df = pd.merge(df, rel_risk_df, left_index=True, right_index=True)
        df = pd.merge(df, marginal_risk_df, left_index=True, right_index=True)
        df.sort_values(by='assetSerenitySymbol', inplace=True)
        return df

    def to_sector_risk_data_frame(self) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of the all the by-sector risk data; depending
        on whether it is based on old-style parentSector / Sector vs. full sector levels, you
        will get back a multi-level index with two or three index columns, with various intermediate
        level in the sector hierarchy populated. This is really better visualized as a treetable, and
        the Serenity front-end provides that view.

        - sectorLevel1
        - sectorLevel2
        - sectorLevel3
        - absoluteFactorRisk
        - absoluteSpecificRisk
        - absoluteTotalRisk
        - relativeFactorRisk
        - relativeSpecificRisk
        - relativeTotalRisk
        """
        abs_risk_df = self._to_by_sector_df(self.absolute_risk_by_sector, 'absolute')
        rel_risk_df = self._to_by_sector_df(self.relative_risk_by_sector, 'relative')
        df = pd.merge(abs_risk_df, rel_risk_df, left_index=True, right_index=True)
        df.sort_index(inplace=True)
        return df

    def to_factor_risk_data_frame(self) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of the all the by-factor risk data at the portfolio level:

        - factor
        - absoluteRiskContribution
        - relativeRiskContribution
        - marginalRiskContribution
        - factorExposureBaseCcy
        """
        rows = []
        items = self.portfolio_risk_by_factor.items()
        for factor_name, risk in items:
            rows.append({
                'factor': factor_name,
                'absoluteRiskContribution': risk.absolute_risk_contribution,
                'relativeRiskContribution': risk.relative_risk_contribution,
                'marginalRiskContribution': risk.marginal_risk_contribution,
                'factorExposureBaseCcy': risk.factor_exposure.factor_exposure_base_ccy
            })
        df = pd.DataFrame(rows)
        df.set_index('factor', inplace=True)
        return df

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
                                         for factor_exposure in sector_exposure['factorExposure']}
                                        for sector_exposure in self.raw_json['sectorFactorExposure']}

    def _parse_raw_json_common(self):
        """
        Handles parsing elements unchanged between Smith and Ricardo.
        """
        self.portfolio_volatility = self._parse_total_risk('volatility')
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

    def _to_by_sector_df(self, sector_risks: Dict[SectorPath, Risk], prefix: str):
        index_cols = []
        rows = []
        items = sector_risks.items()
        for sector_path, risk in items:
            cols = {
                f'{prefix}FactorRisk': risk.factor_risk,
                f'{prefix}SpecificRisk': risk.specific_risk,
                f'{prefix}TotalRisk': risk.total_risk
            }
            index_cols = RiskAttributionResult._append_sector_level_cols(sector_path, cols, rows)
        df = pd.DataFrame(rows)
        df.set_index(index_cols, inplace=True)
        return df

    def _to_by_sector_and_factor_df(self, risks: Dict[SectorPath, Dict[AnyStr, Risk]], prefix: str):
        index_cols = []
        rows = []
        for sector_path, factor_risk in risks.items():
            for factor, risk in factor_risk.items():
                cols = {
                    'factor': factor,
                    f'{prefix}FactorRisk': risk.factor_risk,
                    f'{prefix}SpecificRisk': risk.specific_risk,
                    f'{prefix}TotalRisk': risk.total_risk
                }
                index_cols = RiskAttributionResult._append_sector_level_cols(sector_path, cols, rows)
                index_cols.append('factor')
        df = pd.DataFrame(rows)
        df.set_index(index_cols, inplace=True)
        return df

    def _to_asset_info_df(self, asset_ids: List[UUID], asset_master: AssetMaster):
        rows = []
        for asset_id in asset_ids:
            native_sym = asset_master.get_symbol_by_id(asset_id, 'NATIVE')
            serenity_sym = asset_master.get_symbol_by_id(asset_id, symbology='SERENITY')
            rows.append({
                'assetId': str(asset_id),
                'assetNativeSymbol': native_sym,
                'assetSerenitySymbol': serenity_sym
            })
        df = pd.DataFrame(rows)
        df.set_index('assetId', inplace=True)
        return df

    def _to_by_asset_df(self, asset_risks: Dict[UUID, Risk], prefix: str):
        rows = []
        for asset_id, risk in asset_risks.items():
            cols = {
                'assetId': str(asset_id),
                f'{prefix}FactorRisk': risk.factor_risk,
                f'{prefix}SpecificRisk': risk.specific_risk,
                f'{prefix}TotalRisk': risk.total_risk
            }
            rows.append(cols)
        df = pd.DataFrame(rows)
        df.set_index('assetId', inplace=True)
        return df

    @staticmethod
    def _append_sector_level_cols(sector_path: SectorPath, cols: Dict[AnyStr, float], rows: List[Dict]) -> List[str]:
        index_cols = []
        ndx = 1
        for sector_level in sector_path.sector_levels:
            col_name = f'sectorLevel{ndx}'
            cols[col_name] = sector_level
            index_cols.append(col_name)
            ndx = ndx + 1
        rows.append(cols)
        return index_cols


class Quantile:
    # forward declaration
    pass


@dataclass
class Quantile:
    """
    Helper class that repersents a single VaR quantile, e.g. 90th percentile VaR.
    """
    quantile: float
    var_absolute: float
    var_relative: float

    @staticmethod
    def parse(raw_json: Any) -> Quantile:
        quantile = raw_json['quantile']
        var_absolute = raw_json['varAbsolute']
        var_relative = raw_json['varRelative']
        return Quantile(quantile, var_absolute, var_relative)


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
    var_level_absolute: float
    var_level_relative: float

    @staticmethod
    def parse(raw_json: Any) -> VaRBreach:
        breach_date = datetime.strptime(raw_json['breachDate'], STD_DATE_FMT)
        portfolio_loss_absolute = raw_json['portfolioLossAbsolute']
        portfolio_loss_relative = raw_json['portfolioLossRelative']
        var_level_absolute = raw_json['varLevelAbsolute']
        var_level_relative = raw_json['varLevelRelative']
        return VaRBreach(breach_date, portfolio_loss_absolute, portfolio_loss_relative,
                         var_level_absolute, var_level_relative)


class VaRResult:
    # forward declaration
    pass


@dataclass
class VaRResult:
    """
    Result class that helps users interpret the output of the VaR model, e.g. processing quantiles.
    """
    run_date: date
    baseline: float
    quantiles: List[Quantile]
    excluded_assets: List[UUID]

    @staticmethod
    def parse(raw_json: Any) -> VaRResult:
        run_date = datetime.strptime(raw_json['runDate'], STD_DATE_FMT)
        baseline = raw_json['baseline']
        quantiles = [Quantile.parse(quantile) for quantile in raw_json['quantiles']]
        excluded_assets = [UUID(asset_id) for asset_id in raw_json['excludedAssetIds']]
        return VaRResult(run_date, baseline, quantiles, excluded_assets)


class VaRBacktestResult:
    # forward declaration
    pass


@dataclass
class VaRBacktestResult:
    """
    Result class that helps users interpret the output of the VaR model backtester, e.g. processing breaches.
    """
    results: List[VaRResult]
    breaches: List[VaRBreach]

    @staticmethod
    def parse(raw_json: Any) -> VaRBacktestResult:
        results = [VaRResult.parse(result) for result in raw_json['results']]
        breaches = [VaRBreach.parse(breach) for breach in raw_json['breaches']]
        return VaRBacktestResult(results, breaches)


class PortfolioValue:
    # forward declaration
    pass


@dataclass
class PortfolioValue:
    net_holdings_value: float
    gross_holdings_value: float
    cash_position_value: float
    net_asset_value: float

    @staticmethod
    def parse(raw_json: Any) -> PortfolioValue:
        net_holdings_value = raw_json['netHoldingsValue']
        gross_holdings_value = raw_json['grossHoldingsValue']
        cash_position_value = raw_json['cashPositionValue']
        net_asset_value = raw_json['netAssetValue']
        return PortfolioValue(net_holdings_value, gross_holdings_value, cash_position_value, net_asset_value)


class PositionValue:
    # forward declaration
    pass


@dataclass
class PositionValue:
    value: float
    price: float
    quantity: float
    weight: float

    @staticmethod
    def parse(raw_json: Any) -> PositionValue:
        value = raw_json['value']
        price = raw_json['price']
        quantity = raw_json['qty']
        weight = raw_json['weight']
        return PositionValue(value, price, quantity, weight)


class PositionValues:
    # forward declaration
    pass


@dataclass
class PositionValues:
    close: PositionValue
    previous: PositionValue

    @staticmethod
    def parse(raw_json: Any) -> PositionValues:
        close = PositionValue.parse(raw_json['close'])
        previous = PositionValue.parse(raw_json['previous'])
        return PositionValues(close, previous)


class ValuationResult:
    # forward declaration
    pass


@dataclass
class ValuationResult:
    close: PortfolioValue
    previous: PortfolioValue
    positions: Dict[UUID, PositionValue]

    @staticmethod
    def parse(raw_json: Any) -> ValuationResult:
        close = PortfolioValue.parse(raw_json['close'])
        previous = PortfolioValue.parse(raw_json['previous'])
        positions = {
            UUID(asset_id): PositionValues.parse(position_values)
            for asset_id, position_values in raw_json['positions'].items()
        }
        return ValuationResult(close, previous, positions)


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
