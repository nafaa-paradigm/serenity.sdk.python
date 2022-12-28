import os.path

from serenity_sdk.client.config import Environment, Region, load_local_config


def test_load_local_config_v2_dev():
    config_dir = os.path.dirname(__file__)
    config = load_local_config('test_config_v2_dev', config_dir=config_dir)

    assert config.schema_version == 2
    assert config.tenant_id == 'athansor.cloudwall.network'
    assert config.client_id == '...'
    assert config.user_application_id == '...'
    assert config.user_application_secret == '...'
    assert config.url == 'https://serenity-rest.athansor.dev.cloudwall.network'
    assert config.scope == 'https://serenity-api-dev.athansor.cloudwall.network/.default'
    assert config.get_scopes()[0] == config.scope
    assert config.get_url() == config.url
    assert config.env == Environment.DEV
    assert config.region == Region.EASTUS


def test_load_local_config_v2_prod():
    config_dir = os.path.dirname(__file__)
    config = load_local_config('test_config_v2_prod', config_dir=config_dir)

    assert config.schema_version == 2
    assert config.tenant_id == 'pgi.cloudwall.network'
    assert config.client_id == '...'
    assert config.user_application_id == '...'
    assert config.user_application_secret == '...'
    assert config.url == 'https://serenity-rest.pgi.cloudwall.network'
    assert config.scope == 'https://serenity-api-pgi.cloudwall.network/.default'
    assert config.get_scopes()[0] == config.scope
    assert config.get_url() == config.url
    assert config.env == Environment.PRODUCTION
    assert config.region == Region.GLOBAL
