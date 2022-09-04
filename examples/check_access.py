#!/usr/bin/env python

import fire

from serenity_sdk.client import Environment, Region, SerenityClient, load_local_config


def main(config_id: str, env: str = 'PRODUCTION', region: str = 'GLOBAL'):
    config = load_local_config(config_id)
    client = SerenityClient(config, env=Environment[env], region=Region[region])

    # confirm access to Asset Master API to retrieve reference data
    _check_call_nonempty(client, 'refdata', '/asset/summaries', 'assetSummary', 'Refdata API')

    # confirm access to Risk API to retrieve pre-comuted data
    _check_call_nonempty(client, 'risk', '/factor/returns', 'factorReturns', 'Risk API')

    # confirm access to Model API to retrieve model metadata
    _check_call_nonempty(client, 'catalog', '/model/modelclasses', 'modelClasses', 'Model API')


def _check_call_nonempty(client: SerenityClient, domain: str, api_call: str, result_var: str, api_description: str):
    resp = client.call_api(domain, api_call)
    resp = resp.get(result_var, [])
    if len(resp) > 1:
        print(f'OK - {api_description}')
    else:
        print(f'ERR - bad response from {api_description}: {resp}')


if __name__ == '__main__':
    fire.Fire(main)
