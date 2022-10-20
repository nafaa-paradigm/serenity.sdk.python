from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from uuid import UUID


class Risk:
    # forward declaration
    pass


@dataclass
class Risk:
    factor_risk: float
    specific_risk: float
    total_risk: float

    @staticmethod
    def parse(obj: Any) -> Risk:
        factor_risk = obj['factorRisk']
        specific_risk = obj['specificRisk']
        total_risk = obj['totalRisk']
        return Risk(factor_risk, specific_risk, total_risk)


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


class FactorExposureValue:
    # forward declaration
    pass


@dataclass
class FactorExposureValue:
    factor_exposure: float
    factor_exposure_base_ccy: float

    @staticmethod
    def parse(obj: Any) -> FactorExposureValue:
        factor_exposure = obj['factorExposure']
        factor_exposure_base_ccy = obj.get('factorExposureBaseCcy', 0)
        return FactorExposureValue(factor_exposure, factor_exposure_base_ccy)


class TotalFactorRisk:
    # forward declaration
    pass


@dataclass
class TotalFactorRisk:
    factor: str
    factor_exposure: FactorExposureValue
    absolute_risk_contribution: float
    relative_risk_contribution: float
    marginal_risk_contribution: float

    @staticmethod
    def parse(obj: Any) -> TotalFactorRisk:
        factor = obj['factor']
        absolute_contrib = obj['absoluteContribution']
        relative_contrib = obj['relativeContribution']
        marginal_contrib = obj['marginalContribution']

        # backward compatibility
        factor_exposure_obj = obj['factorExposure']
        if isinstance(factor_exposure_obj, dict):
            factor_exposure = FactorExposureValue.parse(factor_exposure_obj)
        else:
            factor_exposure = FactorExposureValue.parse(obj)

        return TotalFactorRisk(factor, factor_exposure, absolute_contrib, relative_contrib, marginal_contrib)


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

    def get_portfolio_risk_by_factor(self) -> Dict[str, TotalFactorRisk]:
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
        sector_factor_exposures_json = self.raw_json.get('sectorFactorExposure', [])
        self.sector_factor_exposures = {SectorPath(sector_exposure['sectorLevels']):
                                        {factor_exposure['factor']: FactorExposureValue.parse(factor_exposure)
                                         for factor_exposure in sector_exposure['factorExposure']}
                                        for sector_exposure in sector_factor_exposures_json}

    def _parse_raw_json_common(self):
        """
        Handles parsing elements unchanged between Smith and Ricardo.
        """
        self.portfolio_volatility = self._parse_total_risk('volatility')
        self.portfolio_variance = self._parse_total_risk('variance')

        self.portfolio_risk_by_factor = {risk_obj['factor']: TotalFactorRisk.parse(risk_obj)
                                         for risk_obj in self.raw_json['factorRisk']}

        self.marginal_risk_by_asset = {UUID(risk_obj['assetId']): Risk.parse(risk_obj)
                                       for risk_obj in self.raw_json['assetMarginalRisk']}

    def _parse_total_risk(self, risk_measure: str) -> Risk:
        obj = self.raw_json['totalRisk'][risk_measure]
        return Risk.parse(obj)

    def _parse_risk_contribution(self, risk_measure: str) -> Tuple:
        """
        Handle the Ricardo-style sector paths, which include every segment in the path.
        """
        contrib_obj = self.raw_json[risk_measure]
        risk_by_asset = {UUID(risk_obj['assetId']): Risk.parse(risk_obj)
                         for risk_obj in contrib_obj['byAsset']}
        risk_by_sector = {SectorPath(risk_obj['sectorLevels']): Risk.parse(risk_obj)
                          for risk_obj in contrib_obj['bySector']}
        risk_by_sector_and_factor = {}  # will be supported in Ricardo
        return (risk_by_asset, risk_by_sector, risk_by_sector_and_factor)
