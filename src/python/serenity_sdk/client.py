import json
import os.path
import requests

from abc import ABC
from bidict import bidict
from datetime import date
from enum import Enum, auto
from typing import Any, AnyStr, Dict, List
from uuid import UUID

from serenity_sdk.auth import create_auth_headers, get_credential_user_app
from serenity_sdk.types import (AssetMaster, CalculationContext, FactorModelOutputs, ModelMetadata,
                                Portfolio, RiskAttributionResult, SectorTaxonomy, VaRBacktestResult,
                                VaRModel, VaRResult)

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


class CallType(Enum):
    """
    Types of REST calls supported.
    """
    DELETE = 'DELETE'
    GET = 'GET'
    PATCH = 'PATCH'
    POST = 'POST'
    PUT = 'PUT'


class CallingConvention(Enum):
    """
    Original API mixed parameters in the POST body and as request parameters;
    going forward everything is in a single JSON object passed in the body.
    """

    MIXED = auto()
    BODY_ONLY = auto()


class UnknownOperationError(Exception):
    """
    Error raised if there is a request for an API operation that is not known at all. Used
    to prevent unknown paths hitting the gataway unnecessarily.
    """
    def __init__(self, api_path: str, env: Environment):
        super().__init__(f'Unknown operation: {api_path} not mapped in {env}')


class UnsupportedOperationError(Exception):
    """
    Error raised if there is a request for an API operation that is not (yet) supported.
    """
    def __init__(self, api_path: str, env: Environment):
        super().__init__(f'Unsupported operation: {api_path} not mapped in {env}')


class APIPathMapper:
    """
    Helper class for adapting from the original API path scheme to the new uniform
    scheme going live on 1 October 2022. One of the complications here is we want
    new-style SDK code to transparently work with the old backend, and old-style
    SDK calls to continue to work against all environments to ease transitions.
    """
    def __init__(self, env: Environment = Environment.PRODUCTION):
        # the full set of API paths that are known to the SDK;
        # not every environment and every version of the API supports
        # every path in this list
        self.env = env

        # to allow smooth transition from old to new, we have a set of
        # aliases that work in both directions: if an old path is
        # used and we are running against DEV, it translates to the new;
        # if a new path is used and we're running against PRODUCTION, it
        # translates to the old
        self.path_aliases = bidict({
            # re-map Risk API
            '/risk/market/factor/asset_covariance': '/risk/asset/covariance',
            '/risk/market/factor/attribution': '/risk/compute/attribution',
            '/risk/market/factor/correlation': '/risk/factor/correlation',
            '/risk/market/factor/covariance': '/risk/factor/covariance',
            '/risk/market/factor/exposures': '/risk/asset/factor/exposures',
            '/risk/market/factor/residual_covariance': '/risk/asset/residual/covariance',
            '/risk/market/factor/returns': '/risk/factor/returns',

            # re-map VaR API
            '/risk/var/compute': '/risk/compute/var',
            '/risk/var/backtest': '/risk/backtest/var',
        })
        self.env_override_map = {
            Environment.DEV: {'aliases': self.path_aliases.inverse, 'unsupported': {}},
            Environment.TEST: {'aliases': self.path_aliases.inverse, 'unsupported': {}},
            Environment.PRODUCTION: {'aliases': self.path_aliases,
                                     'unsupported': {'/valuation/portfolio/compute', '/risk/market/factor/indexcomps'}}
        }

        # next we have the path configurations, which are always based on the latest path;
        # you need to map from old to new to get the configuration
        self.path_configs = {
            # Refdata API
            '/refdata/asset/summaries': {'call_type': CallType.GET},
            '/refdata/asset/types': {'call_type': CallType.GET},
            '/refdata/symbol/authorities': {'call_type': CallType.GET},
            '/refdata/sector/taxonomies': {'call_type': CallType.GET},

            # Model metadata API
            '/catalog/model/modelclasses': {'call_type': CallType.GET},
            '/catalog/model/models': {'call_type': CallType.GET},
            '/catalog/model/modelconfigurations': {'call_type': CallType.GET},

            # Risk API
            '/risk/market/factor/asset_covariance': {'call_type': CallType.GET},
            '/risk/market/factor/attribution': {'call_type': CallType.POST},
            '/risk/market/factor/correlation': {'call_type': CallType.GET},
            '/risk/market/factor/covariance': {'call_type': CallType.GET},
            '/risk/market/factor/exposures': {'call_type': CallType.GET},
            '/risk/market/factor/indexcomps': {'call_type': CallType.GET},
            '/risk/market/factor/residual_covariance': {'call_type': CallType.GET},
            '/risk/market/factor/returns': {'call_type': CallType.GET},

            # VaR API
            '/risk/var/compute': {'call_type': CallType.POST},
            '/risk/var/backtest': {'call_type': CallType.POST},

            # Valuation API
            '/valuation/portfolio/compute': {'call_type': CallType.POST},
        }

        # finally, how we do POST currently can also vary by environment
        self.calling_conventions = {
            Environment.DEV: CallingConvention.BODY_ONLY,
            Environment.TEST: CallingConvention.BODY_ONLY,
            Environment.PRODUCTION: CallingConvention.MIXED
        }

    def get_call_type(self, latest_path: str) -> CallType:
        """
        For the given path (which may be a legacy path) get whether it is GET, POST, etc..
        """
        call_type = self._get_path_config(latest_path)['call_type']
        return call_type

    def get_default_calling_convention(self) -> CallingConvention:
        """
        Looks up the calling convention to use for all POST calls; at this time we
        are not going to get cute and allow per-path calling convention overrides.
        """
        return self.calling_conventions[self.env]

    def get_api_path(self, input_path: str):
        """
        Given the new API path, return the corresponding path currently supported in production.
        If there is no configuration for this path, this call raises UnsupportedOperationException.
        """
        # first make sure the path is supported
        assert self._get_path_config(input_path) is not None

        # translate the path, or if no aliasing, keep the input path
        api_path = self._get_env_path_aliases().get(input_path, input_path)

        # final check: if the translated api_path is listed as unsupported
        # for this environment, raise UnsupportedOperation
        if api_path in self.env_override_map[self.env]['unsupported']:
            raise UnsupportedOperationError(api_path, self.env)

        return api_path

    def _get_env_path_aliases(self) -> Dict[AnyStr, AnyStr]:
        return self.env_override_map[self.env]['aliases']

    def _get_path_config(self, api_path: str) -> Dict[AnyStr, Any]:
        # a bit tricky here: we always use new-style API paths to look up the path configuration
        # to avoid duplication, and so we need to translate any old => new first
        latest_path = self.path_aliases.inverse.get(api_path, api_path)

        # at this point we have the new-style API path, and so this is expected to
        # map to a valid configuration
        path_config = self.path_configs.get(latest_path, None)
        if not path_config:
            raise UnknownOperationError(latest_path, self.env)
        else:
            return path_config


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
        self.api_mapper = APIPathMapper(env)

    def call_api(self, api_group: str, api_path: str, params: Dict[str, str] = {}, body_json: Any = None) -> Any:
        """
        Low-level function that lets you call *any* Serenity REST API endpoint. For the call
        arguments you can pass a dictionary of request parameters or a JSON object, or both.
        In future versions of the SDK we will offer higher-level calls to ease usage.
        """
        host = SerenityClient._get_url('https://serenity-rest', self.env, self.region)

        full_api_path = f'/{api_group}{api_path}'
        full_api_path = self.api_mapper.get_api_path(full_api_path)
        api_base_url = f'{host}/{self.version}{full_api_path}'

        call_type = self.api_mapper.get_call_type(full_api_path)
        if call_type == CallType.POST:
            call_convention = self.api_mapper.get_default_calling_convention()
            if call_convention == CallingConvention.BODY_ONLY:
                # this is a hack required until the transition on 1 October 2022;
                # in MIXED mode only the portfolio parameter for a POST is in the
                # body; in BODY_ONLY they are a single JSON object
                body_json_new = dict(params)
                body_json_new['portfolio'] = body_json
                body_json = body_json_new
                params = {}

            response_json = requests.post(api_base_url, headers=self.http_headers,
                                          params=params, json=body_json).json()
        elif call_type == CallType.GET:
            response_json = requests.get(api_base_url, headers=self.http_headers,
                                         params=params).json()
        else:
            raise ValueError(f'{full_api_path} call type is {call_type}, which is not yet supported')

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

    def load_asset_master(self, as_of_date: date = None) -> AssetMaster:
        """
        Bulk load operation that loads the whole asset master into memory so it can be
        used to help build portfolios bassed on inputs in different symbologies, and
        so it can be queried without hitting the server multiple times. Reference data
        is always as of a date, as it can change over time, but if a date is not provided
        the system will default to the latest date.
        """
        asset_summaries = self.get_asset_summaries(as_of_date)
        return AssetMaster(asset_summaries)

    def get_asset_summaries(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of asset records in the asset master. In general you should prefer
        to use load_asset_master() instead, which will help parsing the JSON records,
        rather than this lower-level call.
        """
        params = self._create_std_params(as_of_date)
        resp = self._call_api('/asset/summaries', params)
        asset_summaries = resp['assetSummary']
        return asset_summaries

    def get_asset_types(self, as_of_date: date = None) -> Dict[AnyStr, AnyStr]:
        """
        Gets the list of supported asset types in the system, e.g. TOKEN, as
        a map from name to description.
        """
        params = self._create_std_params(as_of_date)
        resp = self._call_api('/asset/types', params)
        asset_types = resp['assetType']
        return {asset_type['name']: asset_type['description'] for asset_type in asset_types}

    def get_symbol_authorities(self, as_of_date: date = None) -> Dict[AnyStr, AnyStr]:
        """
        Gets the list of supported symbol authorities, e.g. KAIKO, DAR or COINGECKO,
        as a map from name to description.
        """
        params = self._create_std_params(as_of_date)
        resp = self._call_api('/symbol/authorities', params)
        authorities = resp['symbolAuthority']
        return {authority['name']: authority['description'] for authority in authorities}

    def get_sector_taxonomies(self, as_of_date: date = None) -> Dict[str, UUID]:
        """
        Gets a mapping from a short key like DACS or DATS to the sectory taxonomy ID (UUID).
        This will be required in the next release if you wish to override the sector
        taxonomy in use for risk attribution. Currently informational only.
        """
        params = self._create_std_params(as_of_date)
        resp = self._call_api('/sector/taxonomies', params)
        taxonomies = resp['sectorTaxonomy']
        return {taxonomy['name']: taxonomy['taxonomyId'] for taxonomy in taxonomies}


class RiskApi(SerenityApi):
    """
    The risk API group covers risk attribution, VaR and (in a future release) scenario analysis.
    """
    def __init__(self, client: SerenityClient):
        super().__init__(client, 'risk')

    def load_factor_model_outputs(self, ctx: CalculationContext) -> FactorModelOutputs:
        """
        Helper method that encapsulates multiple API calls to get the factor mmodel outputs
        for a given date: matrices; factor returns; factor exposures; and other pre-computed
        values from the factor risk model.

        This is a very heavy operation but only has to be called once for a given day and model.
        With the next release you will need to specify a model configuration ID from Model API.
        """
        pass

    def compute_risk_attrib(self, ctx: CalculationContext,
                            portfolio: Portfolio,
                            sector_taxonomy_id: UUID = None,
                            sector_taxonomy: SectorTaxonomy = None) -> RiskAttributionResult:
        """
        Given a portfolio, breaks down the volatility and variance of the portfolio in various
        slices, e.g. by asset, by sector & asset, by sector & factor, and by factor. These different
        pivots of the risk can help you identify areas of risk concentration. All risk calculations
        are always as of a given date, which among other things determines precomputed model values
        that will be applied, e.g. for a factor risk model, as-of date determines the factor loadings.

        Note that sector_taxonomy support will be dropped with the next release, once the refdata endpoint
        for looking up sector_taxonomy_id is available.
        """
        pass

    def compute_var(self, ctx: CalculationContext,
                    portfolio: Portfolio,
                    horizon_days: int = 1,
                    lookback_period: int = 1,
                    quantiles: List[float] = [95, 97.5, 99],
                    var_model: VaRModel = VaRModel.VAR_PARAMETRIC_NORMAL) -> VaRResult:
        """
        Uses a chosen model to compute Value at Risk (VaR) for a portfolio. In the coming release
        this operation will be upgraded to integrate with the Model API and will let you identify
        the model to use by an ID looked up in the model catalog. Note there is a workaround here:
        from the next release, the var_model parameter will be dropped, so until then it's best
        to take the default; the CalculationContext will be used after that release, which will
        allow many more model parameterizations on the backend.
        """
        pass

    def compute_var_backtest(self, ctx: CalculationContext,
                             portfolio: Portfolio,
                             start_date: date,
                             end_date: date,
                             lookback_period: int = 1,
                             quantile: float = 99) -> VaRBacktestResult:
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
