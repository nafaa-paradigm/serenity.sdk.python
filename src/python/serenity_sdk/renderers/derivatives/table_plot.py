from typing import List, Dict
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from serenity_types.pricing.derivatives.rates.yield_curve import YieldCurveVersion
from serenity_types.pricing.derivatives.options.volsurface import VolatilitySurfaceVersion, StrikeType
from serenity_types.pricing.derivatives.options.valuation import OptionValuation, OptionValuationResult
from serenity_sdk.analytics.options import svi_vol
from .converters import convert_object_list_to_df


class YieldCurveTablePlot:
    """
    A helper object to show the contents of a yield curve version
    Used for demo purposes
    """

    def __init__(self, yc: YieldCurveVersion):

        self.yc = yc
        # convert raw data into df
        raw_pts = convert_object_list_to_df(yc.raw.points)
        raw_pts[['mark_price_spot', 'mark_price_future']] = raw_pts['mark_prices'].tolist()
        self.raw_pts: pd.DataFrame = raw_pts

        # convert interpolated data into df
        obj = self.yc.interpolated
        crv_df = pd.DataFrame({
            'duration': obj.durations,
            'rate': obj.rates,
            'discount_factor': obj.discount_factors
        })
        self.interpolated_curve = crv_df

    def plot(self, figsize=(14, 12)):
        """
        plot

        :param figsize: the size of the fig size across all subplots, defaults to (14, 12)
        :return: fig & axs
        """
        fig, axs = plt.subplots(3, 1, figsize=figsize)

        ax_fut = axs[0]
        ax_proj = axs[1]
        ax_log_df = axs[2]

        df = self.raw_pts
        x = df['duration'].to_numpy()
        y = df['mark_price_future'].to_numpy()
        ax_fut.plot(x, y, '.:', ms=12, label='mark future price')

        y = df['mark_price_spot'].to_numpy()
        ax_fut.plot(x, y, ':', label='mark price spot')

        ax_fut.set_ylabel('futures price')
        ax_fut.legend()

        # proj & log_df
        df = self.raw_pts
        x = df['duration'].to_numpy()
        y = df['rate'].to_numpy()
        d = df['discount_factor'].to_numpy()
        ax_proj.plot(x, y, '.:', ms=12, lw=2, label='raw')
        ax_log_df.plot(x, np.log(d), '.:', ms=12, lw=2, label='raw')

        df = self.interpolated_curve
        x = df['duration'].to_numpy()
        y = df['rate'].to_numpy()
        d = df['discount_factor'].to_numpy()
        ax_proj.plot(x, y, 'x-', ms=6, label='interpolated')
        ax_log_df.plot(x, np.log(d), 'x-', ms=6, label='interpolated')

        ax_proj.set_ylabel('implied projection rate')
        ax_log_df.set_ylabel('log(discount factor)')
        ax_proj.legend()
        ax_log_df.legend()
        ax_log_df.set_xlabel('time to expiries')

        ax_log_df.sharex(ax_fut)
        ax_proj.sharex(ax_fut)
        name = self.yc.interpolated.definition.display_name
        as_of_time = self.yc.as_of_time.strftime('%Y-%m-%d %H:%M:%S')
        ax_fut.set_title(f'{name} as of {as_of_time}')

        return fig, axs


class VolatilitySurfaceTablePlot:
    """
    A helper object to show the contents of a volatility surface version
    Used for demo purposes
    """

    def __init__(self, vs: VolatilitySurfaceVersion):

        self.vs = vs

        # extract data from raw
        rvs = vs.raw
        self.spot = rvs.spot_price
        self.strike_type = rvs.strike_type
        self.raw_pts = convert_object_list_to_df(rvs.vol_points)\
            .sort_values(['time_to_expiry', 'strike_value'])
        self.time_to_expiries = np.sort(self.raw_pts['time_to_expiry'].unique())

        # extract surface from interpolated
        obj = vs.interpolated
        self.interpolated_surface = pd.DataFrame(
            {
                'time_to_expiry': obj.time_to_expiries,
                'strike': obj.strikes,
                'vol': obj.vols
            }
        )

    def plot(self, figsize=(14, 4)):
        """
        plot vol smile for each expiry

        :param figsize: the fig size of the plot of each expiry, defaults to (14, 4)
        """
        for tte in self.time_to_expiries:
            self.__plot(tte, figsize=figsize)

    def __plot(self, tte: float, figsize):

        df = self.raw_pts[self.raw_pts['time_to_expiry'] == tte]
        # num
        fig, axs = plt.subplots(1, 1, figsize=figsize)
        ax = axs
        x = df['strike_value']
        y = df['iv']

        if self.strike_type == StrikeType.ABSOLUTE:
            k = np.log(x/self.spot)
        else:
            k = x

        params = self.vs.interpolated.calibration_params[tte]
        iv_fit = svi_vol(k, tte, *params.values())

        ax.plot(x, y, '.', ms=12, label='raw')
        ax.plot(x, iv_fit, '-', label='fit')
        ax.legend()

        if self.strike_type == StrikeType.ABSOLUTE:
            ax.set_xlabel('strike')
        else:
            ax.set_xlabel('log-moneyness')
        ax.set_ylabel('volatility')
        as_of_time = self.vs.as_of_time.strftime('%Y-%m-%d %H:%M:%S')
        name = self.vs.interpolated.definition.display_name
        ax.set_title(f'{name} as of {as_of_time} \n for expiry: {tte:.3f} yrs ({tte*365.25:.2f} dys)')


class OptionValuationResultTablePlot:
    def __init__(self, val_results: List[OptionValuationResult],
                 val_inputs: Dict[str, OptionValuation]):

        tag2id = {tag: ov.option_valuation_id for tag, ov in val_inputs.items()}
        id2tag = {v: k for k, v in tag2id.items()}

        self.results = val_results
        self.inputs = val_inputs

        res_tags = [id2tag[vr.option_valuation_id] for vr in val_results]
        results_table = convert_object_list_to_df(val_results).T
        results_table.columns = res_tags
        results_table = results_table[tag2id.keys()].copy()

        self.results_table = results_table
