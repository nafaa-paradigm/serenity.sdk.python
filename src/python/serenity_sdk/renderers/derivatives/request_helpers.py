from typing import Dict, Tuple, List
import pandas as pd
from serenity_sdk.client import SerenityApiProvider
from serenity_types.pricing.derivatives.options.valuation import (
    OptionValuation,
    OptionValuationRequest)

from .table_plot import OptionValuationResultTablePlot
from .converters import convert_object_dict_to_df

import logging
logging = logging.getLogger(__name__)


def run_compute_option_valuations(
        api: SerenityApiProvider,
        the_optvals=Dict[str, OptionValuation],
        as_of_time=None) -> pd.DataFrame:
    """
    # Function to run 'compute_option_valuations' and put the valuation results into a helper object to format outputs


    :param api: _description_
    :param the_optvals: _description_, defaults to Dict[str, OptionValuation]
    :param as_of_time: _description_, defaults to None
    :return: _description_
    """

    request = OptionValuationRequest(options=[v for v in the_optvals.values()])
    if as_of_time is not None:
        request.as_of_time = as_of_time

    val_results = api.pricer().compute_option_valuations(request)

    # use a helper object for output formatting
    ovr_tp = OptionValuationResultTablePlot(val_results, the_optvals)
    return ovr_tp.results_table


def run_multiple_option_valuation_requests(
        api: SerenityApiProvider,
        requests: Dict[str, OptionValuationRequest])\
        -> Tuple[pd.DataFrame, List[str], List[str]]:

    results = {}
    succeded = []
    failed = []
    for k, r in requests.items():
        try:
            if len(r.options) != 1:
                raise ValueError(f"Each valuation request must have exactly one option valuation. \
                    Please, check {k}.")
            results[k] = api.pricer().compute_option_valuations(r)
            succeded.append(k)
        except Exception:
            logging.warn(f"failed: {k}")
            failed.append(k)

    df = convert_object_dict_to_df({k: v[0] for k, v in results.items()})
    return df, succeded, failed
