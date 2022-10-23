import json
import os.path

from enum import Enum
from typing import Any, List


class Environment(Enum):
    """
    The operational environment (e.g. test vs. production) to use for connection purposes.
    """
    DEV = 'dev'
    """
    Serenity's development environment
    """

    TEST = 'test'
    """
    Serenity's UAT (QA) environment
    """

    PRODUCTION = ''
    """
    Serenity's production environment
    """


class Region(Enum):
    """
    The regional installation of Serenity to use for connection purposes. Not currently used.
    """
    GLOBAL = ''
    EASTUS = 'eastus'
    EASTUS_2 = 'eastus2'


class ConnectionConfig:
    """
    Internal class that handles interpreting the JSON config file generated
    by the Serenity UX API Management function. This class is for internal
    use and normally you should not need to instantiate it.

    .. seealso:: :func:`load_local_config`: utility function to load configs from local files
    """
    def __init__(self, config: Any, config_path: str):
        """
        Builds a connection configuration from a parsed JSON object.

        :param config: a parsed JSON object containing a Serenity API configuration
        :param config_path: for error messages -- the path from which the JSON was loaded
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

            # during transition only PRODUCTION still supports V1
            self.env = Environment.PRODUCTION
            self.region = Region.GLOBAL
        else:
            self.url = config['url']
            self.scope = config['scope']
            self.env = Environment[config['environment']]

            # with V2 we don't actually need Region, so default it for now
            self.region = Region.GLOBAL if self.env == Environment.PRODUCTION else Region.EASTUS

    def get_scopes(self) -> List[str]:
        """
        Gets all of the OAuth scopes used for acquiring the access token
        """
        if self.schema_version == 1:
            return self._get_scopes_v1()
        else:
            return [self.scope]

    def get_url(self) -> str:
        """
        Gets the client-specific URL to use for all API requests
        """
        if self.schema_version == 1:
            return self._get_url_v1('https://serenity-rest')
        else:
            return self.url

    def _get_scopes_v1(self) -> List[str]:
        """
        Helper function that returns the login scopes required to access the API given an environment
        and a region. In general you do not need to call this directly.
        """
        return [
            f"{self._get_url_v1('https://serenity-api')}/.default"
        ]

    def _get_url_v1(self, host: str) -> str:
        """
        Helper function that returns the url based on the Environment and Region provided.
        """
        if self.env.value:
            host = f'{host}-{self.env.value}'
        if self.region.value:
            host = f'{host}-{self.region.value}'
        host = f'{host}.cloudwall.network'
        return host

    @staticmethod
    def _validate_config_json(config: Any, config_path: str) -> int:
        """
        Validates a config JSON from Serenity and ensures it matches the schema

        :param config: raw config JSON object
        :param config_path: file path from which the JSON was loaded; for error messages
        :return: the schema version loaded (currently 1 or 2)
        """
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
