import os.path

from serenity_sdk.config import ConnectionConfig, Environment, Region, load_local_config


def test_load_local_config_v1():
    config_dir = os.path.dirname(__file__)
    config = load_local_config('test_config_v1', config_dir=config_dir)

    assert config.schema_version == 1
    assert config.tenant_id == '...'
    assert config.client_id == '...'
    assert config.user_application_id == '...'
    assert config.user_application_secret == '...'
    assert config.url is None
    assert config.scope is None
    assert config.get_scopes()[0] == 'https://serenity-api.cloudwall.network/.default'
    assert config.get_url() == 'https://serenity-rest.cloudwall.network'


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


def test_get_scopes_v1_default():
    assert ConnectionConfig._get_scopes_v1()[0] == 'https://serenity-api.cloudwall.network/.default'


def test_get_scopes_v1_global():
    expected_scope = 'https://serenity-api-test.cloudwall.network/.default'
    assert ConnectionConfig._get_scopes_v1(Environment.TEST)[0] == expected_scope


def test_get_scopes_v1_no_defaults():
    assert ConnectionConfig._get_scopes_v1(Environment.DEV, Region.EASTUS_2)[0] == \
        'https://serenity-api-dev-eastus2.cloudwall.network/.default'
