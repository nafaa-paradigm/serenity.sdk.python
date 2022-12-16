from typing import Optional, List, Dict, Union
from datetime import datetime
import numpy as np
from uuid import uuid4
from serenity_types.pricing.derivatives.options.valuation import MarketDataOverride, OptionValuation
import serenity_types.pricing.derivatives.rates.yield_curve as yc
import serenity_types.pricing.derivatives.options.volsurface as vs


def _get_market_data_override(override: float, is_bump: bool):
    if is_bump:
        return MarketDataOverride(additive_bump=override)
    else:
        return MarketDataOverride(replacement=override)


def apply_option_valuation_overrides(
    base_optval: OptionValuation,
    spot_override: Optional[float] = None,
    spot_is_bump: Optional[bool] = True,
    vol_override: Optional[float] = None,
    vol_is_bump: Optional[bool] = True,
    strike_override: Optional[float] = None,
    expiry_override: Optional[datetime] = None,
):

    optval = base_optval.copy()
    optval.option_valuation_id = str(uuid4())
    if spot_override is not None:
        optval.spot_price_override = _get_market_data_override(spot_override, spot_is_bump)
    if vol_override is not None:
        optval.implied_vol_override = _get_market_data_override(vol_override, vol_is_bump)

    if strike_override is not None:
        optval.strike = strike_override
    if expiry_override is not None:
        optval.expiry = expiry_override

    return optval


def get_df(durations, rates):
    return [np.exp(-d*r) for d, r in zip(durations, rates)]


def construct_yield_curve(
        display_name: str,
        durations: List[float],
        rates: List[float],
        underlier_asst_id: str,
        curve_usage: yc.CurveUsage = yc.CurveUsage.DISCOUNTING):

    my_def = yc.YieldCurveDefinition(
        yield_curve_id=str(uuid4()),
        curve_usage=curve_usage,
        interpolation_method=yc.InterpolationMethod.FLAT_FWD,
        rate_source_type=yc.RateSourceType.FIXING,
        underlier_asset_id=underlier_asst_id,
        display_name=display_name)

    df = get_df(durations, rates)
    my_curve = yc.InterpolatedYieldCurve(
        definition=my_def,
        durations=durations,
        rates=rates,
        discount_factors=df)

    return my_curve


def construct_volatility_surface(
    display_name: str,
    vol_params: Dict[float, Union[float, Dict[str, float]]],
    underlier_asst_id: str
):
    """
    _summary_

    :param display_name: _description_
    :param vol_params: either svi params by time-to-expiries
                        or vols (no smiles in this case) by time-to-expiries
    :param underlier_asst_id: _description_
    :return: _description_
    """
    my_vs_def = vs.VolatilitySurfaceDefinition(
        vol_surface_id=str(uuid4()),
        vol_model=vs.VolModel.SVI,
        strike_type=vs.StrikeType.LOG_MONEYNESS,
        underlier_asset_id=underlier_asst_id,
        display_name=display_name)

    strikes = [-1, 0, 1]
    time_to_expiries = [0.5, 1]
    strikes_2d, time_to_expiries_2d = np.meshgrid(strikes, time_to_expiries)
    vols_2d = np.full_like(time_to_expiries_2d, 0.1)

    def _get_svi_param(tte, vol_param):
        if isinstance(vol_param, float) or isinstance(vol_param, int):
            return {'a': vol_param**2*tte, 'b': 0.0, 'rho': 0.0, 'm': 0.0, 's': 0.0}
        else:
            return vol_param

    svi_params = {tte: _get_svi_param(tte, vol_param) for
                  tte, vol_param in vol_params.items()}

    my_vs = vs.InterpolatedVolatilitySurface(
        definition=my_vs_def,
        strikes=list(strikes_2d.flatten()),
        time_to_expiries=list(time_to_expiries_2d.flatten()),
        vols=list(vols_2d.flatten()),
        input_params={},
        calibration_params=svi_params
    )

    return my_vs
