import os.path

from serenity_sdk.client import load_local_config


def test_load_local_config():
    config_dir = os.path.dirname(__file__)
    config = load_local_config('test_config', config_dir=config_dir)
    assert config['schemaVersion'] == 1
