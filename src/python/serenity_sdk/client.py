import json
import os.path
import requests

from abc import ABC
from enum import Enum
from typing import Any, Dict, List

from serenity_sdk.auth import create_auth_headers, get_credential_user_app
from serenity_sdk.types import ModelMetadata

SERENITY_API_VERSION = 'v1'


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


class SerenityClient:
    def __init__(self, config_json: Any, env: Environment = Environment.PRODUCTION, region: Region = Region.GLOBAL):
        scopes = SerenityClient._get_scopes(env, region)
        credential = get_credential_user_app(client_id=config_json['clientId'],
                                             client_secret=config_json['userApplicationSecret'],
                                             tenant_id=config_json['tenantId'])

        self.version = SERENITY_API_VERSION
        self.env = env
        self.region = region
        self.http_headers = create_auth_headers(credential, scopes, user_app_id=config_json['userApplicationId'])

    def call_api(self, api_group: str, api_path: str, params: Dict[str, str] = {}, body_json: Any = None) -> Any:
        """
        Low-level function that lets you call *any* Serenity REST API endpoint. For the call
        arguments you can pass a dictionary of request parameters or a JSON object, or both.
        In future versions of the SDK we will offer higher-level calls to ease usage.
        """
        host = SerenityClient._get_url('https://serenity-rest', self.env, self.region)

        api_base_url = f'{host}/{self.version}/{api_group}{api_path}'
        if body_json:
            response_json = requests.post(api_base_url, headers=self.http_headers,
                                          params=params, json=body_json).json()
        else:
            response_json = requests.get(api_base_url, headers=self.http_headers,
                                         params=params).json()

        return response_json

    @staticmethod
    def _get_scopes(env: Environment = Environment.PRODUCTION, region: Region = Region.GLOBAL) -> List[str]:
        """
        Helper function that returns the login scopes required to access the API given an environment
        and a region. In general you do not need to call this directly.
        """
        return [
            f"{SerenityClient._get_url('https://serenity-api', env, region)}/.default"
        ]

    @staticmethod
    def _get_url(host: str, env: Environment, region: Region):
        """
        Helper function that returns the url based on the Environment and Region provided.
        """
        if env.value:
            host = f'{host}-{env.value}'
        if region.value:
            host = f'{host}-{region.value}'
        host = f'{host}.cloudwall.network'
        return host


class SerenityApi(ABC):
    """
    Higher-level wrapper around a particular API endpoint like the Risk API or Model API. Subclasses
    add typed operations and various helper functions specific to that API group.
    """
    def __init__(self, client: SerenityClient, api_group: str):
        self.client = client
        self.api_group = api_group

    def _call_api(self, api_path: str, params: Dict[str, str] = {}, body_json: Any = None) -> Any:
        return self.client.call_api(self.api_group, api_path, params, body_json)


class RiskApi(SerenityApi):
    """
    """
    def __init__(self, client: SerenityClient):
        super().__init__(client, 'risk')


class RefdataApi(SerenityApi):
    """
    """
    def __init__(self, client: SerenityClient):
        super().__init__(client, 'refdata')


class ModelApi(SerenityApi):
    """
    Helper class for the Model Metadata API, which lets clients introspect model parameters
    and other information about available risk models. This endpoint is also required for
    looking up the appropriate Model Configuration ID in the forthcoming Risk API upgrade
    so you can specify which configuration you want to use for risk attribution, scenarios
    and other risk tools.
    """
    def __init__(self, client: SerenityClient):
        super().__init__(client, 'catalog')

    def load_model_metadata(self):
        model_classes = self.get_model_classes()
        models = self.get_models()
        model_configs = self.get_model_configurations()
        return ModelMetadata(model_classes, models, model_configs)

    def get_model_classes(self) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.
        """
        return self._call_api('/model/modelclasses')['modelClasses']

    def get_models(self) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.
        """
        return self._call_api('/model/models')['models']

    def get_model_configurations(self) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.
        """
        return self._call_api('/model/modelconfigurations')['modelConfigurationSummaries']


class SerenityApiProvider:
    """
    Simple entrypoint that gives you access to the full set of Serenity API's from a single class.
    """
    def __init__(self, client: SerenityClient):
        self.refdata_api = RefdataApi(client)
        self.risk_api = RiskApi(client)
        self.model_api = ModelApi(client)

    def refdata(self):
        return self.refdata_api

    def risk(self):
        return self.risk_api

    def model(self):
        return self.model_api


def load_local_config(config_id: str, config_dir: str = None) -> Any:
    """
    Helper function that lets you read a JSON config file with client ID and client secret from
    $HOME/.serenity/${config_id}.json on your local machine.
    """

    if not config_dir:
        home_dir = os.path.expanduser('~')
        config_dir = os.path.join(home_dir, '.serenity')
    config_path = os.path.join(config_dir, f'{config_id}.json')

    # load and parse
    config_file = open(config_path)
    config = json.load(config_file)

    # basic validation
    required_keys = ['schemaVersion', 'tenantId', 'clientId', 'userApplicationId', 'userApplicationSecret']
    if not all(key in config for key in required_keys):
        raise ValueError(f'{config_path} invalid. Required keys: {required_keys}; got: {list(config.keys())}')
    schema_version = config['schemaVersion']
    if schema_version != 1:
        raise ValueError(f'At this time only schemaVersion 1 supported; {config_path} is version {schema_version}')

    return config
