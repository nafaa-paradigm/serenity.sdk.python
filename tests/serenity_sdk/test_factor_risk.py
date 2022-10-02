import json
import os

from serenity_sdk.types import RiskAttributionResult


def test_parse_risk_attrib_v1():
    raw_json = load_json('risk_attrib_result_v1.json')
    result = RiskAttributionResult(raw_json)

    assert len(result.get_absolute_risk_by_asset()) == 7
    assert len(result.get_absolute_risk_by_sector()) == 10
    assert len(result.get_relative_risk_by_asset()) == 7
    assert len(result.get_relative_risk_by_sector()) == 10
    assert len(result.get_marginal_risk_by_asset()) == 7


def test_parse_risk_attrib_v2():
    raw_json = load_json('risk_attrib_result_v2.json')
    result = RiskAttributionResult(raw_json, backcompat_mode=False)

    assert len(result.get_absolute_risk_by_asset()) == 7
    assert len(result.get_absolute_risk_by_sector()) == 10
    assert len(result.get_relative_risk_by_asset()) == 7
    assert len(result.get_relative_risk_by_sector()) == 10
    assert len(result.get_marginal_risk_by_asset()) == 7


def load_json(rel_path: str):
    json_path = os.path.join(os.path.dirname(__file__), rel_path)
    json_file = open(json_path)
    return json.load(json_file)
