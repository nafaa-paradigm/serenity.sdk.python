import json
import math
import os

from serenity_sdk.types.factors import RiskAttributionResult


def test_parse_risk_attrib_v2():
    raw_json = load_json('risk_attrib_result_v2.json')
    result = RiskAttributionResult(raw_json)

    # check parsing of portfolio risk values
    assert math.isclose(result.get_portfolio_volatility().factor_risk, 1.015, abs_tol=0.001)
    assert math.isclose(result.get_portfolio_variance().factor_risk, 1.030, abs_tol=0.001)

    assert math.isclose(result.get_portfolio_volatility().specific_risk, 0.356, abs_tol=0.001)
    assert math.isclose(result.get_portfolio_variance().specific_risk, 0.127, abs_tol=0.001)

    assert math.isclose(result.get_portfolio_volatility().total_risk, 1.076, abs_tol=0.001)
    assert math.isclose(result.get_portfolio_variance().total_risk, 1.157, abs_tol=0.001)

    # test the old sector factor exposure extraction
    assert len(result.get_sector_factor_exposures()) == 10


def test_parse_risk_attrib_v3():
    raw_json = load_json('risk_attrib_result_v3.json')
    result = RiskAttributionResult(raw_json)

    # this is just a smoke test that we don't blow up on V3; still
    # need to decide whether we find a way to handle V2/V3 in a single
    # API or just remove this old, broken method and provide only new
    assert len(result.get_sector_factor_exposures()) == 0


def load_json(rel_path: str):
    json_path = os.path.join(os.path.dirname(__file__), rel_path)
    json_file = open(json_path)
    return json.load(json_file)
