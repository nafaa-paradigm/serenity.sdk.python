import os.path

from serenity_sdk.client import Environment, Region, SerenityClient, load_local_config


def test_load_local_config():
    config_dir = os.path.dirname(__file__)
    config = load_local_config('test_config', config_dir=config_dir)
    assert config['schemaVersion'] == 1


def test_get_scopes_default():
    assert SerenityClient._get_scopes()[0] == 'https://serenity-api.cloudwall.network/.default'


def test_get_scopes_global():
    assert SerenityClient._get_scopes(Environment.TEST)[0] == 'https://serenity-api-test.cloudwall.network/.default'


def test_get_scopes_no_defaults():
    assert SerenityClient._get_scopes(Environment.DEV, Region.EASTUS_2)[0] == \
        'https://serenity-api-dev-eastus2.cloudwall.network/.default'
