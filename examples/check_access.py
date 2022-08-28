import fire

from serenity_sdk.client import Environment, Region, SerenityClient, load_local_config


def main(config_id: str):
    config = load_local_config(config_id)
    client = SerenityClient(config, env=Environment.DEV, region=Region.EASTUS_2)

    # confirm access to Asset Master API to retrieve reference data
    refdata_response = client.call_api('refdata', '/asset/summaries')
    asset_summaries = refdata_response.get('assetSummary', [])
    if len(asset_summaries) > 1:
        print('OK - Asset Master API')
    else:
        print(f'ERR - bad response from Asset Master API: {refdata_response}')

    # confirm access to Risk API to retrieve pre-comuted data
    factor_response = client.call_api('risk', '/factor/returns')
    factor_returns = factor_response.get('factorReturns', [])
    if len(factor_returns) > 1:
        print('OK - Risk API')
    else:
        print(f'ERR - bad response from Risk API: {factor_response}')


if __name__ == '__main__':
    fire.Fire(main)