import itertools
import json
import os

from serenity_sdk.types.common import SectorPath
from serenity_sdk.types.factors import RiskAttributionResult


def test_parse_risk_attrib_v3():
    raw_json = load_json('risk_attrib_result_v3.json')
    result = RiskAttributionResult(raw_json)

    # this is just a smoke test that we don't blow up on V3; still
    # need to decide whether we find a way to handle V2/V3 in a single
    # API or just remove this old, broken method and provide only new
    sector_factor_exposures = result.get_sector_factor_exposures()
    assert len(sector_factor_exposures) == 4

    paths = sector_factor_exposures.keys()
    assert SectorPath(['Smart Contract Platform', 'Multi-Chain / Parachain', 'Multi-Chain / Parachain']) in paths
    assert SectorPath(['Currency', 'Transparent', 'Transparent DeFi Currency']) in paths
    for sector_factor_exposure in itertools.chain.from_iterable(sector_factor_exposures.values()):
        assert sector_factor_exposure.factor_exposure is not None
        assert sector_factor_exposure.absolute_risk is not None
        assert sector_factor_exposure.relative_risk is not None
        assert sector_factor_exposure.marginal_risk is not None


def load_json(rel_path: str):
    json_path = os.path.join(os.path.dirname(__file__), rel_path)
    json_file = open(json_path)
    return json.load(json_file)
