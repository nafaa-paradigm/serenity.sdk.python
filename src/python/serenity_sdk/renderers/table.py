import itertools

from typing import AnyStr, Dict, List
from uuid import UUID

import pandas as pd
import pandas.io.formats.style as pdifs

from serenity_sdk.types.common import SectorPath
from serenity_sdk.types.refdata import AssetMaster
from serenity_sdk.types.factors import RiskAttributionResult, Risk
from serenity_sdk.types.var import VaRBacktestResult


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


class VaRBacktestTables:
    """
    Helper class that formats VaRBacktestResult objects as Pandas DataFrame objects
    to ease tabular display in Jupyter notebooks.
    """

    def __init__(self, result: VaRBacktestResult, bt_quantiles, breach_count_period=365):
        """
        Parses out the result to create multiple Pandas DataFrames.

        :param result: backtest result object
        :param bt_quantiles: quantiles used in the backtest
        :param breach_count_period: the period for breach analysis purposes
        """
        self.result = result
        self.bt_quantiles = bt_quantiles
        self.breach_count_period = breach_count_period

        directions = [-1 if q < 50 else +1 for q in bt_quantiles]
        self.baselines = VaRBacktestTables._extract_ts(result.results, lambda res: res.baseline)
        self.vars_abs_by_qs = pd.DataFrame(
            {q: VaRBacktestTables._extract_ts(result.results, lambda res: res.quantiles[i].var_absolute)
             for i, q in enumerate(bt_quantiles)})
        self.vars_rel_by_qs = pd.DataFrame(
            {q: VaRBacktestTables._extract_ts(result.results, lambda res: res.quantiles[i].var_relative)
             for i, q in enumerate(bt_quantiles)})

        # directly calculate the pnls
        self.pnls_abs = self.baselines.diff().shift(-1)
        self.pnls_rel = self.pnls_abs/self.baselines

        self.var_breaches = pd.DataFrame(
            {q: d * (self.vars_abs_by_qs[q] - (-self.pnls_abs)) < 0 for q, d in zip(bt_quantiles, directions)})
        self.rolling_breaches = self.var_breaches.rolling(window=breach_count_period).sum()

    def get_baselines(self):
        """
        :return: a Series mapping run_date to baseline PV for each day in the backtest.
        """
        return self.baselines

    def get_absolute_var_by_quantiles(self):
        """
        :return: a DataFrame with the absolute ($) VaR for each of the computed quantiles.
        """
        return self.vars_abs_by_qs

    def get_relative_var_by_quantiles(self):
        """
        :return: a DataFrame with the relative (%) VaR for each of the computed quantiles.
        """
        return self.vars_rel_by_qs

    def get_absolute_pnl(self):
        """
        :return: a Series mapping run_date to absolute ($) PnL for each day in the backtest.
        """
        return self.pnls_abs

    def get_relative_pnl(self):
        """
        :return: a Series mapping run_date to relative (%) PnL for each day in the backtest.
        """
        return self.pnls_rel

    def get_var_breaches(self):
        """
        :return: a DataFrame with the VaR breach dates and values for each breach in the backtest.
        """
        return self.var_breaches

    def get_rolling_breaches(self):
        """
        :return: a DataFrame with the rolling number of breaches across breach_count_period.
        """
        return self.rolling_breaches

    def get_breaches_summary(self, quantile: float = 99) -> pd.DataFrame:
        """
        :param quantile: the VaR quantile to report on in this summary
        :return: a DataFrame with each breach and the corresponding VaR and PnL
        """
        run_date_col = 'Run Date'
        base_line_col = 'Baseline ($)'
        var_col = f'{quantile}% VaR ($)'
        var_rel_col = f'{quantile}% VaR (Relative)'
        pnl_col = 'P&L'
        breach_col = 'Breach'
        backtest_df = pd.DataFrame({
            run_date_col: pd.to_datetime(self.baselines.index),
            base_line_col: self.baselines,
            var_col: self.vars_abs_by_qs[quantile],
            var_rel_col: self.vars_rel_by_qs[quantile],
            pnl_col: self.pnls_abs,
            breach_col: self.var_breaches[quantile]
        }).set_index(run_date_col)

        return backtest_df[backtest_df[breach_col]]

    @staticmethod
    def format_breaches_summary(breaches_df: pd.DataFrame) -> pdifs.Styler:
        """
        helper function to format breaches summary DataFrame

        :param breaches_df: a DataFrame produced by get_breaches_summary function
        """

        def loss_fmt(val): return f'${val:,.2f}' if val >= 0 else f'(${abs(val):,.2f})'
        def pct_fmt(val): return f'({abs(val):,.1%})' if val < 0 else f'{abs(val):,.1%}'
        def red_blue_formatter(val): return 'color: blue' if val > 0 else 'color: red'

        base_line_col, var_col, var_rel_col, pnl_col, _ = breaches_df.columns

        breaches_df_formatted = breaches_df.style.format({
            base_line_col: loss_fmt,
            var_col: loss_fmt,
            var_rel_col: pct_fmt,
            pnl_col: loss_fmt
        }).applymap(red_blue_formatter, subset=[pnl_col])

        return breaches_df_formatted

    @staticmethod
    def _extract_ts(arr, func_value, func_index=lambda res: res.run_date):
        return pd.Series({func_index(thing): func_value(thing) for thing in arr})
