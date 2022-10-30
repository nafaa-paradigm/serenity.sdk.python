import json
import math
import os

from serenity_sdk.types.factors import RiskAttributionResult
from serenity_sdk.renderers.table import FactorRiskTables


def test_factor_risk_tables_v3():
    raw_json = load_json('../risk_attrib_result_v3.json')
    result = RiskAttributionResult(raw_json)
    tables = FactorRiskTables(result)

    # test out total risk DataFrame generation
    total_risk_df = tables.to_total_risk_data_frame()
    assert math.isclose(total_risk_df.loc[['volatility']].factorRisk, 1.015, abs_tol=0.001)
    assert math.isclose(total_risk_df.loc[['variance']].factorRisk, 1.030, abs_tol=0.001)

    assert math.isclose(total_risk_df.loc[['volatility']].specificRisk, 0.356, abs_tol=0.001)
    assert math.isclose(total_risk_df.loc[['variance']].specificRisk, 0.127, abs_tol=0.001)

    assert math.isclose(total_risk_df.loc[['volatility']].totalRisk, 1.076, abs_tol=0.001)
    assert math.isclose(total_risk_df.loc[['variance']].totalRisk, 1.157, abs_tol=0.001)

    # test out factor breakdown
    factor_df = tables.to_factor_risk_data_frame()
    assert len(factor_df) == 5

    # test out sector breakdowns
    sector_df = tables.to_sector_risk_data_frame()
    assert len(sector_df) == 4

    sector_factor_df = tables.to_sector_factor_risk_data_frame()
    assert len(sector_factor_df == 4)


def load_json(rel_path: str):
    json_path = os.path.join(os.path.dirname(__file__), rel_path)
    json_file = open(json_path)
    return json.load(json_file)
