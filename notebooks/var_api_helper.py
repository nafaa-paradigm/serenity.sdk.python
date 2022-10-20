import pandas as pd

# Functions used to unpack the result object.


def extract_ts(arr, func_value, func_index=lambda res: res.run_date):
    return pd.Series({func_index(thing): func_value(thing) for thing in arr})


def convert_to_timeseries(result, bt_quantiles, breach_count_period=365):
    """
    unwrap the backtest results into a set of time series data

    :param result: backtest result object
    :param bt_quantiles: quantiles used in the backtest
    :param breach_count_period: the period for breach analysis purposes
    :return: baselines, vars_abs_by_qs, vars_rel_by_qs, pnls_abs, pnls_rel, var_breaches, rolling_breaches
    """

    directions = [-1 if q < 50 else +1 for q in bt_quantiles]
    baselines = extract_ts(result.results, lambda res: res.baseline)
    vars_abs_by_qs = pd.DataFrame(
        {q: extract_ts(result.results, lambda res: res.quantiles[i].var_absolute) for i, q in enumerate(bt_quantiles)})
    vars_rel_by_qs = pd.DataFrame(
        {q: extract_ts(result.results, lambda res: res.quantiles[i].var_relative) for i, q in enumerate(bt_quantiles)})
    pnls_abs = extract_ts(result.breaches, lambda res: res.portfolio_loss_absolute, lambda res: res.breach_date)
    pnls_rel = extract_ts(result.breaches, lambda res: res.portfolio_loss_relative, lambda res: res.breach_date)

    # TODO: In the version as of now, the breach data covers only those with breaches.
    # So, we re-index baselines & vars at the pnl indices.
    # In future, this behavior should be addressed. Once address, the following code block
    # can be removed.
    baselines = baselines.loc[pnls_abs.index]
    vars_abs_by_qs = vars_abs_by_qs.loc[pnls_abs.index]
    vars_rel_by_qs = vars_rel_by_qs.loc[pnls_abs.index]
    # up to here

    var_breaches = pd.DataFrame(
        {q: d * (vars_abs_by_qs[q] - (-pnls_abs)) < 0 for q, d in zip(bt_quantiles, directions)})
    rolling_breaches = var_breaches.rolling(window=breach_count_period).sum()

    return baselines, vars_abs_by_qs, vars_rel_by_qs, pnls_abs, pnls_rel, var_breaches, rolling_breaches