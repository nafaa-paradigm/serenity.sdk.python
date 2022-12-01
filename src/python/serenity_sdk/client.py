import json
import requests

import humps
import pandas as pd

from abc import ABC
from bidict import bidict
from datetime import date, datetime
from enum import Enum
from typing import Any, AnyStr, Dict, List, Optional
from uuid import UUID

from serenity_sdk.auth import create_auth_headers, get_credential_user_app
from serenity_sdk.config import ConnectionConfig, Environment
from serenity_sdk.types.common import STD_DATE_FMT, CalculationContext, Portfolio, PricingContext
from serenity_sdk.types.factors import RiskAttributionResult
from serenity_sdk.types.model import ModelMetadata
from serenity_sdk.types.refdata import AssetMaster
from serenity_sdk.types.valuation import ValuationResult
from serenity_sdk.types.var import VaRAnalysisResult, VaRBacktestResult
from serenity_types.pricing.derivatives.options.valuation import OptionValuationRequest, OptionValuationResult
from serenity_types.pricing.derivatives.options.volsurface import (VolatilitySurfaceAvailability,
                                                                   VolatilitySurfaceVersion)
from serenity_types.pricing.derivatives.rates.yield_curve import YieldCurveAvailability, YieldCurveVersion

SERENITY_API_VERSION = 'v1'


class CallType(Enum):
    """
    Types of REST calls supported. All values correspond to HTTP methods from
    `RFC 9110 <https://www.rfc-editor.org/rfc/rfc9110.html#name-method-definitions>`_.
    """
    DELETE = 'DELETE'
    """
    Used for soft-delete operations in the API, e.g. delete a custom scenario
    """

    GET = 'GET'
    """
    Used for basic retrieval operations in the API
    """

    PATCH = 'PATCH'
    """
    Used for updating objects in the Serenity platform, e.g. updating a custom scenario
    """

    POST = 'POST'
    """
    Used for compute-type operations like risk attribution and backtesting VaR.
    """

    PUT = 'PUT'
    """
    Used to add content to the Serenity platform, e.g. adding a new custom scenario
    """


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
        """
        Internal helper class that takes care of re-mapping API paths; once
        we are in full production we will switch to using API versions to
        support these transitions.

        :param env: target Serenity environment, if not production
        """

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

    def get_api_path(self, input_path: str) -> str:
        """
        Given the new API path, return the corresponding path currently supported in production.
        If there is no configuration for this path, this call raises UnsupportedOperationException.

        :param input_path: the API path requested by the caller
        :return: the correct API path for the target environment
        """
        # translate the path, or if no aliasing, keep the input path
        api_path = self._get_env_path_aliases().get(input_path, input_path)

        # final check: if the translated api_path is listed as unsupported
        # for this environment, raise UnsupportedOperation
        if api_path in self.env_override_map[self.env]['unsupported']:
            raise UnsupportedOperationError(api_path, self.env)

        return api_path

    def _get_env_path_aliases(self) -> Dict[AnyStr, AnyStr]:
        """
        Gets all the old-to-new path mapping aliases.
        """
        return self.env_override_map[self.env]['aliases']


class SerenityClient:
    def __init__(self, config: ConnectionConfig):
        """
        Low-level client object which can be used for direct calls to any REST endpoint.

        :param config: the Serenity platform connection configuration

        .. seealso:: :class:`SerenityApiProvider` for an easier-to-use API wrapper
        """

        scopes = config.get_scopes()
        credential = get_credential_user_app(config)

        self.version = SERENITY_API_VERSION
        self.config = config
        self.env = config.env
        self.region = config.region
        self.auth_headers = create_auth_headers(credential, scopes, user_app_id=config.user_application_id)
        self.api_mapper = APIPathMapper(self.env)

    def call_api(self, api_group: str, api_path: str, params: Dict[str, str] = {}, body_json: Any = None,
                 call_type: CallType = CallType.GET) -> Any:
        """
        Low-level function that lets you call *any* Serenity REST API endpoint. For the call
        arguments you can pass a dictionary of request parameters or a JSON object, or both.
        In future versions of the SDK we will offer higher-level calls to ease usage.

        :param api_group: API take like risk or refdata
        :param api_path: the requested API sub-path to call (non including group or version prefix)
        :param params: any GET-style parameters to include in the call
        :param body_json: a JSON object to POST or PATCH on the server
        :return: the raw JSON response object
        """
        host = self.config.get_url()

        # first make sure we don't have a stale Bearer token, and get the auth HTTP headers
        self.auth_headers.ensure_not_expired()
        http_headers = self.auth_headers.get_http_headers()

        # execute the REST API call after constructing the full URL
        full_api_path = f'/{api_group}{api_path}'
        full_api_path = self.api_mapper.get_api_path(full_api_path)
        api_base_url = f'{host}/{self.version}{full_api_path}'

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
        """
        Helper function that checks for various kinds of error responses and raises exceptions.

        :param response_json: the raw server response
        """
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
        """
        :param client: the raw client to delegate to when making API calls
        :param api_group: the specific API group to target, e.g. risk or refdata
        """
        self.client = client
        self.api_group = api_group

    def _call_api(self, api_path: str, params: Dict[str, str] = {}, body_json: Any = None,
                  call_type: CallType = CallType.GET) -> Any:
        """
        Helper method for derived classes that calls a target API in the supported API group.

        :param api_path: the target API path, excluding version prefix and API group (e.g. `/v1/risk`)
        :param params: the GET-style parameters to pass through to the raw client
        :param body_json: a raw JSON object to POST or PATCH via the raw client
        :return: the raw JSON response object
        """
        return self.client.call_api(self.api_group, api_path, params, body_json, call_type)

    def _get_env(self) -> Environment:
        """
        Internal helper to get the current API environment (dev, test, production).

        :return: the currently-connected environment
        """
        return self.client.env

    @staticmethod
    def _create_std_params(as_of_date: date) -> Dict[str, str]:
        """
        Internal helper that generates params dict based on common parameters for Model API.

        :param as_of_date: the universal as_of_date for all bitemporal API's
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
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'refdata')

    def load_asset_master(self, as_of_date: date = None) -> AssetMaster:
        """
        Bulk load operation that loads the whole asset master into memory so it can be
        used to help build portfolios bassed on inputs in different symbologies, and
        so it can be queried without hitting the server multiple times. Reference data
        is always as of a date, as it can change over time, but if a date is not provided
        the system will default to the latest date.

        :param as_of_date: the effective date for all loaded refdata, else latest if None
        :return: an :class:`AssetMaster` object containing all asset-linked reference data
        """
        asset_summaries = self.get_asset_summaries(as_of_date)
        return AssetMaster(asset_summaries)

    def get_asset_summaries(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of asset records in the asset master. In general you should prefer
        to use :func:`load_asset_master` instead, which will help parsing the JSON records,
        rather than this lower-level call.

        :param as_of_date: the effective date for all loaded refdata, else latest if None
        :return: a list of JSON-formatted asset summary objects
        """
        params = self._create_std_params(as_of_date)
        resp = self._call_api('/asset/summaries', params)
        asset_summaries = resp['assetSummary']
        return asset_summaries

    def get_asset_types(self, as_of_date: date = None) -> Dict[AnyStr, AnyStr]:
        """
        Gets the list of supported asset types in the system, e.g. TOKEN

        :return: a map from name to description
        """
        params = self._create_std_params(as_of_date)
        resp = self._call_api('/asset/types', params)
        asset_types = resp['assetType']
        return {asset_type['name']: asset_type['description'] for asset_type in asset_types}

    def get_symbol_authorities(self, as_of_date: date = None) -> Dict[AnyStr, AnyStr]:
        """
        Gets the list of supported symbol authorities, e.g. KAIKO, DAR or COINGECKO

        :return: a map from name to description
        """
        params = self._create_std_params(as_of_date)
        resp = self._call_api('/symbol/authorities', params)
        authorities = resp['symbolAuthority']
        return {authority['name']: authority['description'] for authority in authorities}

    def get_sector_taxonomies(self, as_of_date: date = None) -> Dict[str, UUID]:
        """
        Gets a mapping from a short key like DACS or DATS to the sectory taxonomy ID (UUID).
        This will be required in the next release if you wish to override the sector
        taxonomy in use for risk attribution.

        :return: a map from taxonomy short name to taxonomy UUID
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
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'risk')

    def compute_risk_attrib(self, ctx: CalculationContext,
                            portfolio: Portfolio,
                            sector_taxonomy_id: UUID = None) -> RiskAttributionResult:
        """
        Given a portfolio, breaks down the volatility and variance of the portfolio in various
        slices, e.g. by asset, by sector & asset, by sector & factor, and by factor. These different
        pivots of the risk can help you identify areas of risk concentration. All risk calculations
        are always as of a given date, which among other things determines precomputed model values
        that will be applied, e.g. for a factor risk model, as-of date determines the factor loadings.

        Note that sector_taxonomy support will be dropped with the next release, once the refdata endpoint
        for looking up sector_taxonomy_id is available.

        :param ctx: the common risk calculation parameters to use, e.g. as-of date or factor risk model ID
        :param portfolio: the portfolio on which to perform risk attribution
        :param sector_taxonomy_id: the unique ID of the sector taxonomy for pivoting, else DACS if None
        :return: a typed wrapper around the risk attribution results
        """
        body_json = {
            **self._create_std_params(ctx.as_of_date),
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'modelConfigId': str(ctx.model_config_id),
            'assetPositions': portfolio.to_asset_positions()
        }
        risk_attribution_json = self._call_api('/market/factor/attribution', {}, body_json, CallType.POST)
        result = RiskAttributionResult(risk_attribution_json)
        return result

    def compute_var(self, ctx: CalculationContext,
                    portfolio: Portfolio,
                    horizon_days: int = 1,
                    lookback_period: int = 365,
                    quantiles: List[float] = [95, 97.5, 99]) -> VaRAnalysisResult:
        """
        Uses a chosen model to compute Value at Risk (VaR) for a portfolio. Note: this API
        currently ignores CalculationContext.model_config_id, so if you want to use a
        different model you must set var_model to either 'VAR_PARAMETRIC_NORMAL' or
        'VAR_HISTORICAL' -- this will be fixed in the next production upgrade.

        :param ctx: the common risk calculation parameters to use, e.g. as-of date or VaR model ID
        :param portfolio: the portfolio to test against the VaR model
        :param horizon_days: loss forecast horizon in days , defaults to 1 day; it is used to scale single day VaR
            by `sqrt(horizonDays)`; must be positive
        :param lookback_period: length of risk factor time series data used to calibrate VaR, measured in days
        :param quantiles: loss forecast quantiles used in VaR calculation; must be unique
            and in range 0 < quantile < 100
        :return: a typed wrapper around the VaR calculation results
        """
        request = {
            **self._create_std_params(ctx.as_of_date),
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'markTime': ctx.mark_time.value,
            'horizonDays': horizon_days,
            'lookbackPeriod': lookback_period,
            **self._create_var_model_params(ctx.model_config_id, lookback_period, quantiles)
        }
        raw_json = self._call_api('/var/compute', {}, request, CallType.POST)
        result_json = raw_json['result']
        result = VaRAnalysisResult._parse(result_json)
        result.warnings = raw_json.get('warnings', [])
        return result

    def compute_var_backtest(self, ctx: CalculationContext,
                             portfolio: Portfolio,
                             start_date: date,
                             end_date: date,
                             lookback_period: int = 365,
                             quantiles: List[float] = [95, 97.5, 99]) -> VaRBacktestResult:
        """
        Performs a VaR backtest, a run of the VaR model for a given portfolio over a time period.
        The goal of the backtest to identify days where the losses exceeded the model prediction,
        i.e. days with VaR breaches. Too many such breaches can lower confidence in the VaR model,
        so it is an important test of the model's predictive power. Note: this API
        currently ignores CalculationContext.model_config_id, so if you want to use a
        different model you must set var_model to either 'VAR_PARAMETRIC_NORMAL' or
        'VAR_HISTORICAL' -- this will be fixed in the next production upgrade.

        :param ctx: the common risk calculation parameters to use, e.g. as-of date or VaR model ID
        :param portfolio: the portfolio to test against the VaR model
        :param start_date: the end date of the backtesting run range
        :param end_date: the end date of the backtesting run range
        :param lookback_period: length of risk factor time series data used to calibrate VaR, measured in days
        :param quantiles: loss forecast quantiles used in VaR calculation; must be unique
            and in range 0 < quantile < 100
        :return: a typed wrapper around the VaR calculation results
        """
        request = {
            **self._create_std_params(ctx.as_of_date),
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'startDate': start_date.strftime(STD_DATE_FMT),
            'endDate': end_date.strftime(STD_DATE_FMT),
            'markTime': ctx.mark_time.value,
            **self._create_var_model_params(ctx.model_config_id, lookback_period, quantiles)
        }
        raw_json = self._call_api('/var/backtest', {}, request, CallType.POST)
        return VaRBacktestResult._parse(raw_json)

    def get_asset_covariance_matrix(self, ctx: CalculationContext, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Gets the asset covariance matrix with asset ID's translated to native symbols, as a DataFrame.

        :param ctx: the common risk calculation parameters to use, specifically the as-of date and model ID in this case
        :return: a DataFrame pivoted by `assetId1` and `assetId2` with the asset covariance `value` as a column
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/asset_covariance', params)
        return RiskApi._asset_matrix_to_dataframe(raw_json['matrix'], asset_master)

    def get_asset_residual_covariance_matrix(self, ctx: CalculationContext, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Gets the asset residual covariance matrix with asset ID's translated to native symbols, as a DataFrame.

        :param ctx: the common risk calculation parameters to use, specifically the as-of date and model ID in this case
        :return: a DataFrame pivoted by `assetId1` and `assetId2` with the asset residual `value` as a column
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

        :param ctx: the common risk calculation parameters to use, specifically the as-of date and model ID in this case
        :return: a DataFrame pivoted by `factor1` and `factor2` with the
            factor correlation coefficient `value` as a column
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/correlation', params)
        return RiskApi._factor_matrix_to_dataframe(raw_json['matrix'])

    def get_factor_covariance_matrix(self, ctx: CalculationContext) -> pd.DataFrame:
        """
        Gets the factor covariance matrix.

        :param ctx: the common risk calculation parameters to use, specifically the as-of date and model ID in this case
        :return: a DataFrame pivoted by `factor1` and `factor2` with the factor covariance `value` as a column
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/covariance', params)
        return RiskApi._factor_matrix_to_dataframe(raw_json['matrix'])

    def get_asset_factor_exposures(self, ctx: CalculationContext, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Gets the factor exposures by assets as a DataFrame.

        :param ctx: the common risk calculation parameters to use, specifically the as-of date and model ID in this case
        :return: a DataFrame pivoted by `assetId` and `factor` with the exposure `value` as a column
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

        :param ctx: the common risk calculation parameters to use, specifically the as-of date and model ID in this case
        :return: a DataFrame indexed by `closeDate` and `factor` with the return `value` as a column
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/returns', params)
        factor_returns = pd.DataFrame.from_dict(raw_json['factorReturns']).pivot(index='closeDate', columns='factor',
                                                                                 values='value')
        return factor_returns.style.format("{:.1%}")

    def get_factor_portfolios(self, ctx: CalculationContext) -> Dict[AnyStr, Portfolio]:
        """
        Gets the factor index compositions for each factor.

        :param ctx: the common risk calculation parameters to use, specifically the as-of date and model ID in this case
        :return: a mapping from factor name to the factor portfolio
        """
        params = RiskApi._create_get_params(ctx)
        raw_json = self._call_api('/market/factor/indexcomps', params)
        factors = {factor: RiskApi._to_portfolio(indexcomps) for (factor, indexcomps) in raw_json['factors'].items()}
        return factors

    def _create_var_model_params(self, model_config_id: UUID, lookback_period: int,
                                 quantiles: List[float]) -> Dict[AnyStr, Any]:
        """
        VaR model parameter conventions changed between the Ricardo and Martineau releases. This method
        takes care of rewriting both conventions to ensure backward compatiblity during the transition.

        :param model_config_id: the UUID for the VaR model selected
        :param lookback_period: the lookback period, which in Ricardo is in years, default 1, and in Martineau
            is in days, default 365
        :param quantiles: the list of quantiles for compute VaR or, in dev & test only, for backtest VaR as well
        :return: a dictionary with the appropriate config keys based on environment for backward compatibility
        """
        params = {
            'modelConfigId': str(model_config_id),
            'lookbackPeriod': lookback_period,
            'quantiles': quantiles
        }
        return params

    @staticmethod
    def _asset_matrix_to_dataframe(matrix_json: Any, asset_master: AssetMaster) -> pd.DataFrame:
        """
        Converts an asset matrix (asset pairs and values) into a simple DataFrame

        :param matrix_json: the raw matrix output from the API
        :param asset_master: a loaded AssetMaster to convert UUID to symbols
        :return: a DataFrame pivoted by `assetId1` and `assetId2` with `value` columns
        """
        def map_asset_id(asset_id: str):
            return asset_master.get_symbol_by_id(UUID(asset_id))

        df = pd.DataFrame.from_dict(matrix_json).dropna()
        df = df.pivot(index='assetId1', columns='assetId2', values='value')
        df.set_index(df.index.map(map_asset_id), inplace=True)
        df.columns = df.columns.map(map_asset_id)

        return df

    @staticmethod
    def _factor_matrix_to_dataframe(matrix_json: Any) -> pd.DataFrame:
        """
        Converts a factor matrix (factor pairs and values) into a simple DataFrame

        :param matrix_json: _description_
        :return: a DataFrame pivoted by `factor1` and `factor2` with `value` columns
        """
        df = pd.DataFrame.from_dict(matrix_json).dropna()
        df = df.pivot(index='factor1', columns='factor2', values='value')
        return df

    @staticmethod
    def _to_portfolio(indexcomps: Any) -> Portfolio:
        """
        Converts raw factor index composition data in JSON format to a typed Portfolio object.

        :param indexcomps: _description_
        :return: the typed Portfolio object
        """
        positions = {UUID(entry['assetId']): entry['weight'] for entry in indexcomps if entry['weight'] != 0}
        return Portfolio(positions)

    @staticmethod
    def _create_get_params(ctx: CalculationContext) -> Dict[AnyStr, Any]:
        """
        Creates the full set of GET-style parameters given a :class:`CalculationContext`.

        :param ctx: the bundle of calculation defaults, e.g. base currency to use
        :return: the full set of call parameters
        """
        return {
            'as_of_date': ctx.as_of_date.strftime(STD_DATE_FMT),
            'model_config_id': ctx.model_config_id
        }


class ValuationApi(SerenityApi):
    """
    The valuation API group covers basic tools for NAV and other portfolio valuation calcs.
    """
    def __init__(self, client: SerenityClient):
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'valuation')

    def compute_portfolio_value(self, ctx: PricingContext, portfolio: Portfolio) -> ValuationResult:
        """
        Computes portfolio NAV and other high-level valuation details at both the portfolio level
        and position-by-position.

        :param ctx: the pricing parameters to use, e.g. which base currency and the as-of date for prices
        :param portfolio: the portfolio to value
        :return: a parsed :class:`ValuationResult` containing all portfolio & position values
        """
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
        raw_json = self._call_api('/portfolio/compute', {}, request, CallType.POST)
        return ValuationResult._parse(raw_json)


class PricerApi(SerenityApi):
    def __init__(self, client: SerenityClient):
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'pricing')

    def compute_option_valuations(self, request: OptionValuationRequest) -> List[OptionValuationResult]:
        """
        Given a list of options, market data and market data override parameters, value all the options.

        :param request: the set of options to value using the given market data and overrides
        :return: ordered list of option valuations with PV, greeks, market data, etc.
        """
        request_json = json.loads(request.json(exclude_unset=True, by_alias=True))
        raw_json = self._call_api('/derivatives/options/valuation/compute', {}, request_json, CallType.POST)
        return [OptionValuationResult.parse_obj(result) for result in raw_json['result']]

    def get_volatility_surface_version(self, vol_surface_id: UUID,
                                       as_of_time: Optional[datetime] = datetime.now()) -> VolatilitySurfaceVersion:
        """
        Gets the volsurface given a unique identifier for the parameter set and an as-of time to pick
        up the most recent version as of that date/time. These JSON objects can be very large, so in general the
        protocol should be to list what's available.

        :param vol_surface_id: the specific combination of parameters (VolModel, etc.) that you want to retrieve
        :return: the raw and interpolated VS as of the given time for the given set of parameters
        """
        params = {
            'as_of_time': as_of_time
        }
        raw_json = self._call_api(f'/derivatives/options/volsurfaces/{str(vol_surface_id)}', params)
        return VolatilitySurfaceVersion.parse_obj(raw_json['result'])

    def get_available_volatility_surface_versions(self, vol_surface_id: Optional[UUID] = None,
                                                  start_datetime: Optional[datetime] = None,
                                                  end_datetime: Optional[datetime] = None) \
            -> List[VolatilitySurfaceAvailability]:
        """
        Gets a list of generic volsurface descriptions and their available versions.

        :param vol_surface_id: optional specific vol_surface_id to be retrieved; defaults to all available in the
                               chosen date/time range
        :param end_datetime: optional end of date/time range (inclusive) to query for available surface
                             parameterizations and their versions; defaults to UNIX epoch
        :param end_datetime: optional end of date/time range (inclusive) to query for available surface
                             parameterizations and their versions; defaults to now
        """
        params = {
            'vol_surface_id': str(vol_surface_id) if vol_surface_id is not None else None,
            'start_datetime': start_datetime,
            'end_datetime': end_datetime
        }
        raw_json = self._call_api('/derivatives/options/volsurfaces', params)
        return [VolatilitySurfaceAvailability.parse_obj(raw_avail) for raw_avail in raw_json['result']]

    def get_yield_curve_version(self, yield_curve_id: UUID,
                                as_of_time: Optional[datetime] = datetime.now()) -> YieldCurveVersion:
        """
        Gets the yield curve given a unique identifier. These JSON objects can be very large so
        in general the protocol should be to list what's available for a time range and then retrieve each one.

        :param yield_curve_id: the specific combination of parameters that you want to retrieve
        :param as_of_time: the effective date/time for the version; defaults to latest
        :return: the raw and interpolated YC as of the given time for the given set of parameters
        """
        params = {
            'as_of_time': as_of_time
        }
        raw_json = self._call_api(f'/derivatives/rates/yield_curves/{str(yield_curve_id)}', params)
        return YieldCurveVersion.parse_obj(raw_json['result'])

    def get_available_yield_curve_versions(self, yield_curve_id: Optional[UUID] = None,
                                           start_datetime: Optional[datetime] = None,
                                           end_datetime: Optional[datetime] = None) -> List[YieldCurveAvailability]:
        """
        Gets a list of generic yield curve descriptions and their available versions.

        :param yield_curve_id: optional specific yield_curve_id to be retrieved; defaults to all available
                               in the chosen date/time range
        :param start_datetime: optional start of date/time range (inclusive) to query for available curve
                               parameterizations and their versions; defaults to UNIX epoch
        :param end_datetime: optional end of date/time range (inclusive)to query for available curve
                             parameterizations and their versions; defaults to now
        """
        params = {
            'vol_surface_id': str(yield_curve_id) if yield_curve_id is not None else None,
            'start_datetime': start_datetime,
            'end_datetime': end_datetime
        }
        raw_json = self._call_api('/derivatives/rates/yield_curves', params)
        return [YieldCurveAvailability.parse_obj(raw_avail) for raw_avail in raw_json['result']]


class ModelApi(SerenityApi):
    """
    Helper class for the Model Metadata API, which lets clients introspect model parameters
    and other information about available risk models. This endpoint is also required for
    looking up the appropriate Model Configuration ID in the forthcoming Risk API upgrade
    so you can specify which configuration you want to use for risk attribution, scenarios
    and other risk tools.
    """
    def __init__(self, client: SerenityClient):
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'catalog')

    def load_model_metadata(self, as_of_date: date = None) -> ModelMetadata:
        """
        Helper method that preloads all the model metadata into memory for easy access.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        model_classes = self.get_model_classes(as_of_date)
        models = self.get_models(as_of_date)
        model_configs = self.get_model_configurations(as_of_date)
        return ModelMetadata(model_classes, models, model_configs)

    def get_model_classes(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/modelclasses', params=params)['modelClasses']

    def get_models(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/models', params=params)['models']

    def get_model_configurations(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/modelconfigurations', params=params)['modelConfigurationSummaries']


class SerenityApiProvider:
    """
    Simple entrypoint that gives you access to the full set of Serenity API's from a single class.
    """
    def __init__(self, client: SerenityClient):
        """
        :param client: the raw client to wrap around for every typed endpoint
        """

        self.refdata_api = RefdataApi(client)
        self.risk_api = RiskApi(client)
        self.valuation_api = ValuationApi(client)
        self.pricer_api = PricerApi(client)
        self.model_api = ModelApi(client)

    def refdata(self) -> RefdataApi:
        """
        Gets a typed wrapper around all the supported reference data API calls.
        """
        return self.refdata_api

    def risk(self) -> RiskApi:
        """
        Gets a typed wrapper aorund all the supported risk-related API calls. Currently this mixes
        factor risk attribution and VaR-related calls, but we may break this out later.
        """
        return self.risk_api

    def valuation(self) -> ValuationApi:
        """
        Gets a typed wrapper for all the portfolio valuation API functions.
        """
        return self.valuation_api

    def pricer(self) -> PricerApi:
        """
        Gets a typed wrapper for all the pricing API's for derivatives.
        """
        return self.pricer_api

    def model(self) -> ModelApi:
        """
        Gets a typed wrapper for all the ModelOps (model metadata) API functions.
        """
        return self.model_api
