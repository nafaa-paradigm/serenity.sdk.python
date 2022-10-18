import humps
import requests

import pandas as pd

from abc import ABC
from bidict import bidict
from datetime import date
from enum import Enum
from typing import Any, AnyStr, Dict, List
from uuid import UUID

from serenity_sdk.auth import create_auth_headers, get_credential_user_app
from serenity_sdk.config import ConnectionConfig, Environment
from serenity_sdk.types import (STD_DATE_FMT, AssetMaster, CalculationContext, FactorModelOutputs, ModelMetadata,
                                Portfolio, PricingContext, RiskAttributionResult, SectorTaxonomy,
                                ValuationResult, VaRAnalysisResult, VaRBacktestResult)

SERENITY_API_VERSION = 'v1'


class CallType(Enum):
    """
    Types of REST calls supported.
    """
    DELETE = 'DELETE'
    GET = 'GET'
    PATCH = 'PATCH'
    POST = 'POST'
    PUT = 'PUT'


class SerenityError(Exception):
    """
    Generic error when the API fails, e.g. due to body parsing error on POST
    """
    def __init__(self, detail: Any):
        super().__init__(f'Generic API error: {detail}')


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

        # now that the 20221001-Prod release is out, all three environments
        # have the same API paths, but we still have some client code out
        # there potentially using the old convention, so we are going to
        # set up an inverse mapping until everyone migrates that will translate
        # old API paths to new API paths
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
            Environment.PRODUCTION: {'aliases': self.path_aliases.inverse, 'unsupported': {}}
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

    def get_call_type(self, latest_path: str) -> CallType:
        """
        For the given path (which may be a legacy path) get whether it is GET, POST, etc..
        """
        call_type = self._get_path_config(latest_path)['call_type']
        return call_type

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
    def __init__(self, config: ConnectionConfig):
        scopes = config.get_scopes()
        credential = get_credential_user_app(config)

        self.version = SERENITY_API_VERSION
        self.config = config
        self.env = config.env
        self.region = config.region
        self.auth_headers = create_auth_headers(credential, scopes, user_app_id=config.user_application_id)
        self.api_mapper = APIPathMapper(self.env)

    def call_api(self, api_group: str, api_path: str, params: Dict[str, str] = {}, body_json: Any = None) -> Any:
        """
        Low-level function that lets you call *any* Serenity REST API endpoint. For the call
        arguments you can pass a dictionary of request parameters or a JSON object, or both.
        In future versions of the SDK we will offer higher-level calls to ease usage.
        """
        host = self.config.get_url()

        # first make sure we don't have a stale Bearer token, and get the auth HTTP headers
        self.auth_headers.ensure_not_expired()
        http_headers = self.auth_headers.get_http_headers()

        # execute the REST API call after constructing the full URL
        full_api_path = f'/{api_group}{api_path}'
        full_api_path = self.api_mapper.get_api_path(full_api_path)
        api_base_url = f'{host}/{self.version}{full_api_path}'

        call_type = self.api_mapper.get_call_type(full_api_path)
        if call_type == CallType.POST:
            if params:
                # this is a hack to help anyone with an "old-style" notebook
                # who is setting portfolio in the body and as_of_date and other
                # secondary parameters in request parameters: with this latest
                # version of the backend they get merged into a single JSON input
                body_json_new = {}
                for key, value in params.items():
                    body_json_new[humps.camelize(key)] = value
                body_json_new['portfolio'] = body_json
                body_json = body_json_new
                params = {}

            response_json = requests.post(api_base_url, headers=http_headers,
                                          params=params, json=body_json).json()
        elif call_type == CallType.GET:
            response_json = requests.get(api_base_url, headers=http_headers,
                                         params=params).json()
        else:
            raise ValueError(f'{full_api_path} call type is {call_type}, which is not yet supported')

        return SerenityClient._check_response(response_json)

    @staticmethod
    def _check_response(response_json: Any):
        if 'detail' in response_json:
            raise SerenityError(response_json['detail'])
        elif 'message' in response_json:
            raise SerenityError(response_json['message'])
        else:
            return response_json


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

    def _get_env(self) -> Environment:
        """
        Internal helper to get the current API environment (dev, test, production)

        :return: the currently-connected environment
        """
        return self.client.env

    @staticmethod
    def _create_std_params(as_of_date: date) -> Dict[str, str]:
        """
        Internal helper that generates params dict based on common parameters for Model API.
        """
        if as_of_date is None:
            return {}
        else:
            return {'asOfDate': as_of_date.strftime(STD_DATE_FMT)}


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
        body_json = {
            **self._create_std_params(ctx.as_of_date),
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'modelConfigId': str(ctx.model_config_id),
            'assetPositions': portfolio.to_asset_positions()
        }
        risk_attribution_json = self._call_api('/market/factor/attribution', {}, body_json)
        result = RiskAttributionResult(risk_attribution_json)
        return result

    def compute_var(self, ctx: CalculationContext,
                    portfolio: Portfolio,
                    horizon_days: int = 1,
                    lookback_period: int = 365,
                    quantiles: List[float] = [95, 97.5, 99],
                    var_model: str = 'VAR_PARAMETRIC_NORMAL') -> VaRAnalysisResult:
        """
        Uses a chosen model to compute Value at Risk (VaR) for a portfolio. Note: this API
        currently ignores CalculationContext.model_config_id, so if you want to use a
        different model you must set var_model to either 'VAR_PARAMETRIC_NORMAL' or
        'VAR_HISTORICAL' -- this will be fixed in the next production upgrade.
        """
        request = {
            **self._create_std_params(ctx.as_of_date),
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'markTime': ctx.mark_time.value,
            'horizonDays': horizon_days,
            'lookbackPeriod': lookback_period,
            **self._create_var_model_params(ctx.model_config_id, var_model, lookback_period, None, quantiles)
        }
        raw_json = self._call_api('/var/compute', {}, request)
        backcompat = self._get_env() == Environment.PRODUCTION
        result_json = raw_json if backcompat else raw_json['result']
        result = VaRAnalysisResult.parse(result_json, backcompat=backcompat)
        result.warnings = [] if backcompat else raw_json.get('warnings', [])
        return result

    def compute_var_backtest(self, ctx: CalculationContext,
                             portfolio: Portfolio,
                             start_date: date,
                             end_date: date,
                             lookback_period: int = 365,
                             quantiles: List[float] = [95, 97.5, 99],
                             quantile: float = 99,
                             var_model: str = 'VAR_PARAMETRIC_NORMAL') -> VaRBacktestResult:
        """
        Performs a VaR backtest, a run of the VaR model for a given portfolio over a time period.
        The goal of the backtest to identify days where the losses exceeded the model prediction,
        i.e. days with VaR breaches. Too many such breaches can lower confidence in the VaR model,
        so it is an important test of the model's predictive power. Note: this API
        currently ignores CalculationContext.model_config_id, so if you want to use a
        different model you must set var_model to either 'VAR_PARAMETRIC_NORMAL' or
        'VAR_HISTORICAL' -- this will be fixed in the next production upgrade.
        """
        request = {
            **self._create_std_params(ctx.as_of_date),
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'startDate': start_date.strftime(STD_DATE_FMT),
            'endDate': end_date.strftime(STD_DATE_FMT),
            'markTime': ctx.mark_time.value,
            **self._create_var_model_params(ctx.model_config_id, var_model, lookback_period, quantile, quantiles)
        }
        raw_json = self._call_api('/var/backtest', {}, request)
        return VaRBacktestResult.parse(raw_json, backcompat=(self._get_env() == Environment.PRODUCTION),
                                       backcompat_quantile=quantile)

    def get_asset_covariance_matrix(self, ctx: CalculationContext, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Gets the asset covariance matrix with asset ID's translated to native symbols, as a DataFrame.
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/asset_covariance', params)
        return RiskApi._asset_matrix_to_dataframe(raw_json['matrix'], asset_master)

    def get_asset_residual_covariance_matrix(self, ctx: CalculationContext, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Gets the asset residual covariance matrix with asset ID's translated to native symbols, as a DataFrame.
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/residual_covariance', params)
        rows = [{'assetId': element['assetId1'],
                 'symbol': asset_master.get_symbol_by_id(UUID(element['assetId1'])),
                 'value': element['value']} for element in raw_json['matrix']]
        return pd.DataFrame(rows)

    def get_factor_correlation_matrix(self, ctx: CalculationContext) -> pd.DataFrame:
        """
        Gets the factor correlation matrix.
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/correlation', params)
        return RiskApi._factor_matrix_to_dataframe(raw_json['matrix'])

    def get_factor_covariance_matrix(self, ctx: CalculationContext) -> pd.DataFrame:
        """
        Gets the factor covariance matrix.
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/covariance', params)
        return RiskApi._factor_matrix_to_dataframe(raw_json['matrix'])

    def get_asset_factor_exposures(self, ctx: CalculationContext, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Gets the factor loadings by assets as a DataFrame.
        """
        def map_asset_id(asset_id: str):
            return asset_master.get_symbol_by_id(UUID(asset_id))

        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/exposures', params)
        factor_exposures = pd.DataFrame.from_dict(raw_json['matrix'])
        factor_exposures = factor_exposures.pivot(index='assetId', columns='factor', values='value')
        factor_exposures.set_index(factor_exposures.index.map(map_asset_id), inplace=True)

        return factor_exposures

    def get_factor_returns(self, ctx: CalculationContext) -> pd.DataFrame:
        """
        Gets the factor returns as a DataFrame.
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/returns', params)
        factor_returns = pd.DataFrame.from_dict(raw_json['factorReturns']).pivot(index='closeDate', columns='factor',
                                                                                 values='value')
        return factor_returns.style.format("{:.1%}")

    def get_factor_portfolios(self, ctx: CalculationContext) -> Dict[AnyStr, Portfolio]:
        """
        Gets the factor index compositions for each factor.
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/indexcomps', params)
        factors = {factor: RiskApi._to_portfolio(indexcomps) for (factor, indexcomps) in raw_json['factors'].items()}
        return factors

    def _create_var_model_params(self, model_config_id: UUID, model_id: str, lookback_period: int,
                                 quantile: float, quantiles: List[float]) -> Dict[AnyStr, Any]:
        """
        VaR model parameter conventions changed between the Ricardo and Martineau releases. This method
        takes care of rewriting both conventions to ensure backward compatiblity during the transition.

        :param model_config_id: the UUID for the VaR model selected
        :param model_id: the legacy enum value for the VaR model to use
        :param lookback_period: the lookback period, which in Ricardo is in years, default 1, and in Martineau
            is in days, default 365
        :param quantile: the single quantile parameter for backtest VaR, else None for compute VaR
        :param quantiles: the list of quantiles for compute VaR or, in dev & test only, for backtest VaR as well
        :return: a dictionary with the appropriate config keys based on environment for backward compatibility
        """
        if self._get_env() == Environment.PRODUCTION:
            params = {
                'modelId': model_id,
                'lookbackPeriod': (1 if lookback_period == 365 else lookback_period)
            }
            if quantile is not None:
                # in production backtest VaR takes a single float quantile
                params['quantile'] = quantile
            else:
                # in production compute VaR takes an array of quantiles
                params['quantiles'] = quantiles
        else:
            params = {
                'modelConfigId': str(model_config_id),
                'lookbackPeriod': lookback_period,

                # in dev and test, both backtest and compute VaR take an array of quantiles
                'quantiles': quantiles
            }
        return params

    @staticmethod
    def _asset_matrix_to_dataframe(matrix_json: Any, asset_master: AssetMaster) -> pd.DataFrame:
        def map_asset_id(asset_id: str):
            return asset_master.get_symbol_by_id(UUID(asset_id))

        df = pd.DataFrame.from_dict(matrix_json).dropna()
        df = df.pivot(index='assetId1', columns='assetId2', values='value')
        df.set_index(df.index.map(map_asset_id), inplace=True)
        df.columns = df.columns.map(map_asset_id)

        return df

    @staticmethod
    def _factor_matrix_to_dataframe(matrix_json: Any) -> pd.DataFrame:
        df = pd.DataFrame.from_dict(matrix_json).dropna()
        df = df.pivot(index='factor1', columns='factor2', values='value')
        return df

    @staticmethod
    def _to_portfolio(indexcomps: Any) -> Portfolio:
        positions = {UUID(entry['assetId']): entry['weight'] for entry in indexcomps if entry['weight'] != 0}
        return Portfolio(positions)

    @staticmethod
    def _create_get_params(ctx: CalculationContext) -> Dict[AnyStr, Any]:
        return {
            'as_of_date': ctx.as_of_date.strftime(STD_DATE_FMT),
            'model_config_id': ctx.model_config_id
        }


class ValuationApi(SerenityApi):
    """
    The valuation API group covers basic tools for NAV and other portfolio valuation calcs.
    """
    def __init__(self, client: SerenityClient):
        super().__init__(client, 'valuation')

    def compute_portfolio_value(self, ctx: PricingContext, portfolio: Portfolio):
        request = {
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'pricing_context': {
                **self._create_std_params(ctx.as_of_date),
                'portfolio': {'assetPositions': portfolio.to_asset_positions()},
                'markTime': ctx.mark_time.value,
                'baseCurrencyId': str(ctx.base_currency_id),
                'cashTreatment': ctx.cash_treatment.value
            }
        }
        raw_json = self._call_api('/portfolio/compute', {}, request)
        return ValuationResult.parse(raw_json)


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
        self.valuation_api = ValuationApi(client)
        self.model_api = ModelApi(client)

    def refdata(self):
        return self.refdata_api

    def risk(self):
        return self.risk_api

    def valuation(self):
        return self.valuation_api

    def model(self):
        return self.model_api
