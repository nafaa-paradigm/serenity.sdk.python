import json
import requests

from enum import Enum
from typing import Any, AnyStr, Dict

import humps.camel

from bidict import bidict

from serenity_sdk.auth import create_auth_headers, get_credential_user_app
from serenity_sdk.config import ConnectionConfig, Environment


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
    def __init__(self, detail: Any, request_json: Any = None):
        super().__init__(f'Generic API error: {detail}; request body: {json.dumps(request_json, indent=4)}')


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
                    body_json_new[humps.camel.case(key)] = value
                body_json_new['portfolio'] = body_json
                body_json = body_json_new
                params = {}

            response_json = requests.post(api_base_url, headers=http_headers,
                                          params=params, json=body_json).json()
        elif call_type == CallType.PATCH:
            response_json = requests.patch(api_base_url, headers=http_headers,
                                           params=params, json=body_json).json()
        elif call_type == CallType.PUT:
            response_json = requests.put(api_base_url, headers=http_headers,
                                         params=params, json=body_json).json()
        elif call_type == CallType.DELETE:
            response_json = requests.delete(api_base_url, headers=http_headers,
                                            params=params).json()
        elif call_type == CallType.GET:
            response_json = requests.get(api_base_url, headers=http_headers,
                                         params=params).json()
        else:
            raise ValueError(f'{full_api_path} call type is {call_type}, which is not yet supported')

        return SerenityClient._check_response(body_json, response_json)

    @staticmethod
    def _check_response(body_json: Any, response_json: Any):
        """
        Helper function that checks for various kinds of error responses and raises exceptions.

        :param response_json: the raw server response
        """
        if 'detail' in response_json:
            raise SerenityError(response_json['detail'], body_json)
        elif 'message' in response_json:
            raise SerenityError(response_json['message'], body_json)
        else:
            return response_json
