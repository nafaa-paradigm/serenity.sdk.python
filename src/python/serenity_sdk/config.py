import json
import os.path

from enum import Enum
from typing import Any, List


class Environment(Enum):
    """
    The operational environment (e.g. test vs. production) to use for connection purposes.
    """
    DEV = 'dev'
    TEST = 'test'
    PRODUCTION = ''


class Region(Enum):
    """
    The regional installation of Serenity to use for connection purposes.
    """
    GLOBAL = ''
    EASTUS = 'eastus'
    EASTUS_2 = 'eastus2'


class ConnectionConfig:
    """
    Internal class that handles interpreting the JSON config file generated
    by the Serenity UX API Management function. This class is for internal
    use and normally you should not need to instantiate it.
    """
    def __init__(self, config: Any, config_path: str):
        """
        Builds a connection configuration from a parsed JSON object.

        :param config: a parsed JSON object containing a Serenity API configuration
        :param config_path: for error messages -- the path the JSON was loaded from
        """
        # basic validation, extract the schema version
        schema_version = ConnectionConfig._validate_config_json(config, config_path)

        # OK, we have a clean object, extract the core fields
        self.schema_version = schema_version
        self.tenant_id = config['tenantId']
        self.client_id = config['clientId']
        self.user_application_id = config['userApplicationId']
        self.user_application_secret = config['userApplicationSecret']

        # for V1, we need to construct the target URL from environment and region,
        # while for V2, we are given the target URL
        if schema_version == 1:
            self.url = None
            self.scope = None
        else:
            self.url = config['url']
            self.scope = config['scope']

    @staticmethod
    def _validate_config_json(config: Any, config_path: str) -> int:
        required_keys = ['schemaVersion', 'tenantId', 'clientId', 'userApplicationId', 'userApplicationSecret']
        required_extra_keys_v2 = ['url', 'scope']
        if not all(key in config for key in required_keys):
            raise ValueError(f'{config_path} invalid. Required keys: {required_keys}; got: {list(config.keys())}')
        schema_version = config['schemaVersion']
        if schema_version not in [1, 2]:
            raise ValueError(f'At this time only schemaVersion 1 or 2 supported; '
                             f'{config_path} is version {schema_version}')

        if schema_version == 2:
            if not all(key in config for key in required_extra_keys_v2):
                raise ValueError(f'{config_path} invalid. Missing V2 keys: {required_extra_keys_v2}; '
                                 f'got: {list(config.keys())}')

        return schema_version

    def get_scopes(self, env: Environment = Environment.PRODUCTION, region: Region = Region.GLOBAL) -> List[str]:
        if self.schema_version == 1:
            return ConnectionConfig._get_scopes_v1(env, region)
        else:
            return [self.scope]

    def get_url(self, env: Environment = Environment.PRODUCTION, region: Region = Region.GLOBAL) -> str:
        if self.schema_version == 1:
            return ConnectionConfig._get_url_v1('https://serenity-rest', env, region)
        else:
            return self.url

    @staticmethod
    def _get_scopes_v1(env: Environment = Environment.PRODUCTION, region: Region = Region.GLOBAL) -> List[str]:
        """
        Helper function that returns the login scopes required to access the API given an environment
        and a region. In general you do not need to call this directly.
        """
        return [
            f"{ConnectionConfig._get_url_v1('https://serenity-api', env, region)}/.default"
        ]

    @staticmethod
    def _get_url_v1(host: str, env: Environment, region: Region) -> str:
        """
        Helper function that returns the url based on the Environment and Region provided.
        """
        if env.value:
            host = f'{host}-{env.value}'
        if region.value:
            host = f'{host}-{region.value}'
        host = f'{host}.cloudwall.network'
        return host


def load_local_config(config_id: str, config_dir: str = None) -> ConnectionConfig:
    """
    Helper function that lets you read a JSON config file with client ID and client secret from
    `$HOME/.serenity/${config_id}.json` on your local machine.

    :param config_id: short name of a configuration to load from `$HOME/.serenity`
    :param config_dir: optional override to load from a directory other than `$HOME/,serenity`
    :return: a populated, validated `ConnectionConfig` object to use with `SerenityClient`
    """

    if not config_dir:
        home_dir = os.path.expanduser('~')
        config_dir = os.path.join(home_dir, '.serenity')
    config_path = os.path.join(config_dir, f'{config_id}.json')

    # load and parse
    config_file = open(config_path)
    config = json.load(config_file)

    return ConnectionConfig(config, config_path)
