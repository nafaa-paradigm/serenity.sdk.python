from abc import ABC
from datetime import date
from typing import Any, Dict

from serenity_sdk.client.raw import CallType, SerenityClient
from serenity_sdk.config import Environment
from serenity_sdk.types.common import STD_DATE_FMT


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
