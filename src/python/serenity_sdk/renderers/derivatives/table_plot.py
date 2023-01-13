from typing import List, Dict, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from serenity_types.pricing.derivatives.rates.yield_curve import YieldCurveVersion
from serenity_types.pricing.derivatives.options.volsurface import VolatilitySurfaceVersion, StrikeType
from serenity_types.pricing.derivatives.options.valuation import (
    OptionValuation,
    OptionValuationResult,
)
from .converters import convert_object_list_to_df
from .utils import svi_vol


class YieldCurveTablePlot:
    """
    A helper object to show the contents of a yield curve version
    Used for demo purposes
    """

    def __init__(self, yc: YieldCurveVersion):

        self.yc = yc
        # convert raw data into df
        raw_pts = convert_object_list_to_df(yc.raw.points)
        if raw_pts['mark_prices'].iloc[0] is None:
            self.with_mark_prices = False
        else:
            self.with_mark_prices = True
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

    def plot(self, figsize_x=14):
        """
        plot yield curves.
        (1) spot & future price term structures (futures-implied curves only)
        (2) rate term structure
        (3) discount factor term structure - in log-space
        :param figsize_x: _description_, defaults to 14
        """

        if self.with_mark_prices:
            return self.plot_with_mark_prices(figsize=(figsize_x, figsize_x*12/14))
        else:
            return self.plot_without_mark_prices(figsize=(figsize_x, figsize_x*8/14))

    def plot_without_mark_prices(self, figsize):
        """
        plot_without_mark_prices

        :param figsize: the size of the fig size across all subplots
        :return: fig & axs
        """
        fig, axs = plt.subplots(2, 1, figsize=figsize)

        ax_proj = axs[0]
        ax_log_df = axs[1]

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

        ax_proj.set_ylabel('rate')
        ax_log_df.set_ylabel('log(discount factor)')
        ax_proj.legend()
        ax_log_df.legend()
        ax_log_df.set_xlabel('time to expiries')

        ax_proj.grid()
        ax_log_df.grid()

        ax_log_df.sharex(ax_proj)
        name = self.yc.interpolated.definition.display_name
        as_of_time = self.yc.as_of_time.strftime('%Y-%m-%d %H:%M:%S')
        ax_proj.set_title(f'{name} as of {as_of_time}')

        return fig, axs

    def plot_with_mark_prices(self, figsize):
        """
        plot_with_mark_prices

        :param figsize: the size of the fig size across all subplots
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
        ax_fut.grid()

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

        ax_proj.grid()
        ax_log_df.grid()

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


def plot_valuation_results(res_df: pd.DataFrame, valuation_labels=None, xlabel='time', legend_loc=1):
    """
    Plot key valuation results over time

    :param res_df: result data frame
    :valuation_labels: label
    """

    if valuation_labels is None:
        valuation_labels = res_df.columns

    fig, axs = plt.subplots(2, 2, figsize=(10, 6), sharex=True)

    # present value
    ax = axs[0][0]
    ax.plot(valuation_labels, res_df.loc['pv'], '.-', label='PV')

    # spot price & forward price
    ax = axs[0][1]
    ax.plot(valuation_labels, res_df.loc['spot_price'], '.-', label='Spot')
    ax.plot(valuation_labels, res_df.loc['forward_price'], '.-', label='Forward Price')

    # rates
    ax = axs[1][0]
    ax.plot(valuation_labels, res_df.loc['projection_rate'], '.-', label='Projection Rate')
    ax.plot(valuation_labels, res_df.loc['discounting_rate'], '.-', label='Discounting Rate')

    # delta (ccy)
    ax = axs[1][1]
    plt.plot(valuation_labels, res_df.loc['delta_ccy'], '.-', label='delta (ccy)')

    for i in range(2):
        ax = axs[0][i]
        ax.tick_params(axis='x', which='both', bottom=False)
        ax = axs[1][i]
        ax.set_xlabel(xlabel)
        ax.tick_params(axis='x', labelrotation=90)

    for i in range(4):
        ax: plt.Axes = axs.flatten()[i]
        if legend_loc is None:
            ax.legend()
        else:
            ax.legend(loc=legend_loc)
        ax.ticklabel_format(useOffset=False, style='plain', axis='y')
        ax.grid()

    fig.tight_layout()
    plt.show()


def plot_bumped_pv(
        res_table: pd.DataFrame,
        qty: int,
        bumps: Dict[str, float],
        bumped_market_data_name: str,
        first_order_greek: str,
        second_order_greek: Optional[str] = None,
        base_column_id: Optional[str] = 'base',
        figsize: Optional[tuple] = (10, 6),
        **kwargs: dict):
    """
    plot present values over market data bumps

    :param res_table: data frame containing results
    :param qty: quantity
    :param bumps: dictionary of bumps (name, value) pairs
    :param bumped_market_data_name: name of the bumped market data (e.g. spot, vol)
    :param first_order_greek: name of the first-order Greek with respect to the market data bumped
    :param second_order_greek: name of the second-order Greek with respect to the market data bumped (optional)
    :param base_column_id: name of the base valuation from which the Greeks are taken, defaults to 'base'
    :param figsize: figure size, defaults to (10, 6)
    """

    result_base = res_table[base_column_id]
    result_bumps = res_table[[c for c in res_table.columns if c != base_column_id]]

    pv_base = result_base['pv']
    bump_vals = np.array(list(bumps.values()))

    base_1st = result_base[first_order_greek]
    pnl_approx = qty * base_1st * bump_vals
    if second_order_greek is not None:
        base_2nd = result_base[second_order_greek]
        pnl_approx_2 = pnl_approx + qty * (0.5 * base_2nd * bump_vals**2)

    plt.figure(figsize=figsize)
    reval_change = result_bumps.loc['pv'] - pv_base
    plt.plot(bump_vals, reval_change, '.-', ms=10, label='bump & pv change')
    plt.plot(bump_vals, pnl_approx, ':', label='1st-order approximation')
    if second_order_greek is not None:
        plt.plot(bump_vals, pnl_approx_2, ':', label='2nd-order approximation')
    plt.grid(), plt.legend(), plt.xlabel(f'bump ({bumped_market_data_name})'), plt.ylabel('pv change')

    show_dev_1st = kwargs.get('show_dev_1st', False)
    if show_dev_1st:
        plt.figure(figsize=figsize)
        plt.plot(bump_vals, reval_change - pnl_approx, ':', label='deviation from 1st-order approx')
        plt.grid(), plt.legend(), plt.xlabel(f'bump ({bumped_market_data_name})'), plt.ylabel('deviation')


def plot_volatility_surface_3d(
    vol_surface: VolatilitySurfaceVersion,
    width=800, height=800,
) -> go.Figure:

    # interpolated surface
    ivs = vol_surface.interpolated
    interpolated_df = pd.DataFrame(
        {
            'expiry': ivs.time_to_expiries,
            'strike': ivs.strikes,
            'vol': ivs.vols
        })
    interpolated_df = interpolated_df.groupby(['expiry', 'strike'])['vol'].mean().unstack()
    T, K, sigma = interpolated_df.index.values, interpolated_df.columns.values, interpolated_df.values.T

    raw_df = convert_object_list_to_df(vol_surface.raw.vol_points)
    T_raw, K_raw, sigma_raw = (raw_df[c] for c in ['time_to_expiry', 'strike_value', 'iv'])

    # 3D plot
    fig = go.Figure(data=[
        go.Surface(z=sigma, x=T, y=K, opacity=0.75, name='interpolated'),
        go.Scatter3d(x=T_raw, y=K_raw, z=sigma_raw, mode='markers',
                     marker=dict(size=2, color=np.log(T_raw)), name='raw')
    ])

    fig.update_layout(
        title='implied volatility',
        scene=dict(
            xaxis_title='x:expiry',
            yaxis_title='y:strike',
            zaxis_title='z:implied volatility'
        ),
        width=width, height=height, autosize=False,
        margin=dict(l=65, r=50, b=65, t=90))
    return fig
