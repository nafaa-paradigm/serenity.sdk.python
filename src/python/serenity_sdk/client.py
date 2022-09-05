import json
import os.path
import requests

from abc import ABC
from datetime import date
from enum import Enum
from typing import Any, Dict, List
from uuid import UUID

from serenity_sdk.auth import create_auth_headers, get_credential_user_app
from serenity_sdk.types import ModelMetadata

SERENITY_API_VERSION = 'v1'
AS_OF_DATE_FMT = '%Y-%m-%d'


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

    @staticmethod
    def _create_std_params(as_of_date: date) -> Dict[str, str]:
        """
        Internal helper that generates params dict based on common parameters for Model API.
        """
        if as_of_date is None:
            return {}
        else:
            return {'asOfDate': as_of_date.strftime(AS_OF_DATE_FMT)}


class RefdataApi(SerenityApi):
    """
    The refdata API group covers access to the Serenity Asset Master and other supporting
    reference data needed for constructing portfolios and running risk models.
    """
    def __init__(self, client: SerenityClient):
        super().__init__(client, 'refdata')

    def load_asset_master(self, as_of_date: date = None):
        """
        Bulk load operation that loads the whole asset master into memory so it can be
        used to help build portfolios bassed on inputs in different symbologies, and
        so it can be queried without hitting the server multiple times. Reference data
        is always as of a date, as it can change over time, but if a date is not provided
        the system will default to the latest date.
        """
        pass

    def get_asset_types(self, as_of_date: date = None) -> List[str]:
        """
        Gets the list of supported asset types in the system, e.g. TOKEN.
        """
        pass

    def get_symbol_authorities(self, as_of_date: date = None) -> List[str]:
        """
        Gets the list of supported symbol authorities, e.g. KAIKO, DAR or COINGECKO.
        """
        pass

    def get_sector_taxonomy_ids(self, as_of_date: date = None) -> Dict[str, UUID]:
        """
        Gets a mapping from a short key like DACS or DATS to the sectory taxonomy ID (UUID).
        This will be required in the 20220917 release if you wish to override the sector
        taxonomy in use for risk attribution. Currently information only.
        """
        pass


class RiskApi(SerenityApi):
    """
    The risk API group covers risk attribution, VaR and (in a future release) scenario analysis.
    """
    def __init__(self, client: SerenityClient):
        super().__init__(client, 'risk')

    def load_factor_model_outputs(self):
        """
        Helper method that encapsulates multiple API calls to get the factor mmodel outputs
        for a given date: matrices; factor returns; factor exposures; and other pre-computed 
        values from the factor risk model.

        This is a very heavy operation but only has to be called once for a given day and model.
        With the 20220917 upgrade you will need to specify a model configuration ID from Model API.
        """
        pass

    def compute_risk_attrib(self):
        """
        Given a portfolio, breaks down the volatility and variance of the portfolio in various
        slices, e.g. by asset, by sector & asset, by sector & factor, and by factor. These different
        pivots of the risk can help you identify areas of risk concentration. All risk calculations
        are always as of a given date, which among other things determines precomputed model values
        that will be applied, e.g. for a factor risk model, as-of date determines the factor loadings.
        """
        pass

    def compute_var(self):
        """
        Uses a chosen model to compute Value at Risk (VaR) for a portfolio. In the coming release
        this operation will be upgraded to integrate with the Model API and will let you identify
        the model to use by an ID looked up in the model catalog.
        """
        pass

    def compute_var_backtest(self):
        """
        Performs a VaR backtest, a run of the VaR model for a given portfolio over a time period.
        The goal of the backtest to identify days where the losses exceeded the model prediction,
        i.e. days with VaR breaches. Too many such breaches can lower confidence in the VaR model,
        so it is an important test of the model's predictive power.
        """
        pass


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

    def load_model_metadata(self, as_of_date: date = None) -> ModelMetadata:
        """
        Helper method that preloads all the model metadata into memory for easy access.
        """
        model_classes = self.get_model_classes(as_of_date)
        models = self.get_models(as_of_date)
        model_configs = self.get_model_configurations(as_of_date)
        return ModelMetadata(model_classes, models, model_configs)

    def get_model_classes(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/modelclasses', params=params)['modelClasses']

    def get_models(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/models', params=params)['models']

    def get_model_configurations(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/modelconfigurations', params=params)['modelConfigurationSummaries']


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
