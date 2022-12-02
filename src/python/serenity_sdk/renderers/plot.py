import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binom

from serenity_sdk.renderers.table import VaRBacktestTables


def create_traffic_light_report(var_tables: VaRBacktestTables, model_kind: str = 'Parametric'):
    kind = "Parametric"

    scale_unit, scale = 'mil', 1e-6

    # get the tables to plot
    baselines = var_tables.get_baselines()
    vars_abs_by_qs = var_tables.get_absolute_var_by_quantiles()
    pnls_abs = var_tables.get_absolute_pnl()
    var_breaches = var_tables.get_var_breaches()
    rolling_breaches = var_tables.get_rolling_breaches()

    # convert to pd.Timestamp to date time to ease plotting
    dt_index = pd.to_datetime(baselines.index)

    fig, axs = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [1, 2, 1]}, sharex=True)

    # Portfolio Value Profile
    ax0 = axs[0]
    ax0.set_title('Portfolio Value')
    ax0.set_ylabel(f"Value ($) in {scale_unit}")
    ax0.plot(dt_index, scale * baselines)
    ax0.xaxis.set_tick_params(labelbottom=True)

    # VaR & PnL profiles
    # Plot in P&L terms. So, VaR will be on the negative side.
    ax1 = axs[1]

    nvars_ws = - scale * vars_abs_by_qs
    pnls_abs_ws = scale * pnls_abs

    ax1.set_title(f"VaR Backtest ({kind})")
    ax1.set_ylabel(f"PnLs ($) in {scale_unit}")

    ax1.plot(dt_index, pnls_abs_ws, lw=0.5, color="purple", label="realised PnL")
    ax1.fill_between(dt_index, nvars_ws[99], nvars_ws[95], alpha=0.5, color="royalblue", label="95%-99%")
    ax1.fill_between(dt_index, nvars_ws[95], nvars_ws[5], alpha=0.5, color="lightsteelblue", label="05%-95%")
    ax1.fill_between(dt_index, nvars_ws[5], nvars_ws[1], alpha=0.5, color="royalblue", label="01%-05%")

    # sort bt_quantiles so that we plot the middle ones first
    qidx_plot_order = np.argsort(np.abs(np.array(var_tables.bt_quantiles) - 50))

    for q_idx in qidx_plot_order:
        q = var_tables.bt_quantiles[q_idx]
        q_breaches = var_breaches[q]
        color = 'r' if q in [1, 99] else 'orange'
        ax1.plot(dt_index[q_breaches], pnls_abs_ws[q_breaches], '.', color=color)

    ax1.plot()
    ax1.legend()
    ax1.xaxis.set_tick_params(labelbottom=True)

    # Now, traffic light
    ax2 = axs[2]
    ax2.set_title('Traffic Light Test')
    ax2.set_ylabel('Rolling Breach Counts')

    q_rolling = 99
    for q in [q_rolling]:
        line_style = '-' if q > 50 else '--'
        ax2.plot(dt_index, rolling_breaches[q], ls=line_style, color='purple', label=f'{q}% VaR')
    ax2.legend()

    x = np.arange(0, var_tables.breach_count_period)
    green_amber, amber_red = [np.min(x[1 - binom.cdf(x, var_tables.breach_count_period, 1.0-q_rolling/100.) < cf])
                              for cf in [0.05, 0.0001]]
    y_max = amber_red + (amber_red - green_amber)
    ax2.fill_between(dt_index, 0.0, green_amber + .4, color='g', alpha=0.1)
    ax2.fill_between(dt_index, green_amber + .8, amber_red + .4, color='y', alpha=0.1)
    ax2.fill_between(dt_index, amber_red + .8, y_max, color='r', alpha=0.1)
    ax2.set_ylim([0.0, y_max])

    plt.tight_layout()
    plt.show()
