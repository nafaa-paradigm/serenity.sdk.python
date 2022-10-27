import itertools

from typing import AnyStr, Dict, List
from uuid import UUID

import pandas as pd

from serenity_sdk.types.common import SectorPath
from serenity_sdk.types.refdata import AssetMaster
from serenity_sdk.types.factors import RiskAttributionResult, Risk


class FactorRiskTables:
    """
    Helper class that formats RiskAttributionResult objects as Pandas DataFrame objects
    to ease tabular display in Jupyter notebooks.
    """

    def __init__(self, result: RiskAttributionResult):
        self.result = result

    def to_total_risk_data_frame(self) -> pd.DataFrame:
        """
        Summarizes the portfolio's factor, specific and total risk in both volatility and variance.

        :return: a DataFrame with factorRisk, specificRisk and totalRisk columns corresponding to
            the portion of the risk explained by the model, the portfion of the risk that
            is idiosyncratic to the assets in that portfolio, and the overall risk. Index
            corresponds to both volatility and variance.
        """
        rows = [
            {
                'measure': 'volatility',
                'factorRisk': self.result.portfolio_volatility.factor_risk,
                'specificRisk': self.result.portfolio_volatility.specific_risk,
                'totalRisk': self.result.portfolio_volatility.total_risk
            },
            {
                'measure': 'variance',
                'factorRisk': self.result.portfolio_variance.factor_risk,
                'specificRisk': self.result.portfolio_variance.specific_risk,
                'totalRisk': self.result.portfolio_variance.total_risk
            }
        ]
        df = pd.DataFrame(rows)
        df.set_index('measure', inplace=True)
        return df

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
        asset_info_df = FactorRiskTables._to_asset_info_df(self.result.absolute_risk_by_asset.keys(), asset_master)
        abs_risk_df = FactorRiskTables._to_by_asset_df(self.result.absolute_risk_by_asset, 'absolute')
        rel_risk_df = FactorRiskTables._to_by_asset_df(self.result.relative_risk_by_asset, 'relative')
        marginal_risk_df = FactorRiskTables._to_by_asset_df(self.result.marginal_risk_by_asset, 'marginal')
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
        abs_risk_df = FactorRiskTables._to_by_sector_df(self.result.absolute_risk_by_sector, 'absolute')
        rel_risk_df = FactorRiskTables._to_by_sector_df(self.result.relative_risk_by_sector, 'relative')
        df = pd.merge(abs_risk_df, rel_risk_df, left_index=True, right_index=True)
        df.sort_index(inplace=True)
        return df

    def to_sector_factor_risk_data_frame(self) -> pd.DataFrame:
        """
        Creates a DataFrame with a flattened version of the all the by-sector, by-factor risk data; depending
        on whether it is based on old-style parentSector / Sector vs. full sector levels, you
        will get back a multi-level index with two or three index columns, with various intermediate
        level in the sector hierarchy populated. This is really better visualized as a treetable, and
        the Serenity front-end provides that view.

        - sectorLevel1
        - sectorLevel2
        - sectorLevel3
        - factor
        - absoluteRisk
        - relativeRisk
        - marginalRisk
        - factorExposure
        - factorExposureBaseCcy
        """
        index_cols = []
        rows = []
        for sector_factor_exposure in itertools.chain.from_iterable(self.result.sector_factor_exposures.values()):
            cols = {
                'factor': sector_factor_exposure.factor,
                'absoluteRisk': sector_factor_exposure.absolute_risk,
                'relativeRisk': sector_factor_exposure.relative_risk,
                'marginalRisk': sector_factor_exposure.marginal_risk,
                'factorExposure': sector_factor_exposure.factor_exposure.factor_exposure,
                'factorExposureBaseCcy': sector_factor_exposure.factor_exposure.factor_exposure_base_ccy
            }
            index_cols = FactorRiskTables._append_sector_level_cols(sector_factor_exposure.sector_path, cols, rows)
        df = pd.DataFrame(rows)
        df.set_index(index_cols, inplace=True)
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
        items = self.result.portfolio_risk_by_factor.items()
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

    @staticmethod
    def _to_by_sector_df(sector_risks: Dict[SectorPath, Risk], prefix: str):
        index_cols = []
        rows = []
        items = sector_risks.items()
        for sector_path, risk in items:
            cols = {
                f'{prefix}FactorRisk': risk.factor_risk,
                f'{prefix}SpecificRisk': risk.specific_risk,
                f'{prefix}TotalRisk': risk.total_risk
            }
            index_cols = FactorRiskTables._append_sector_level_cols(sector_path, cols, rows)
        df = pd.DataFrame(rows)
        df.set_index(index_cols, inplace=True)
        return df

    @staticmethod
    def _to_by_sector_and_factor_df(risks: Dict[SectorPath, Dict[AnyStr, Risk]], prefix: str):
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
                index_cols = FactorRiskTables._append_sector_level_cols(sector_path, cols, rows)
                index_cols.append('factor')
        df = pd.DataFrame(rows)
        df.set_index(index_cols, inplace=True)
        return df

    @staticmethod
    def _to_asset_info_df(asset_ids: List[UUID], asset_master: AssetMaster):
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

    @staticmethod
    def _to_by_asset_df(asset_risks: Dict[UUID, Risk], prefix: str):
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
