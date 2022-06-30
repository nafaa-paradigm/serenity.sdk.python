import json
import os
import os.path
import requests
import stat

from enum import Enum
from typing import Any, Dict, List

from serenity_sdk.auth import create_auth_headers, get_credential_user_app

SERENITY_API_VERSION = 'v1'


class Environment(Enum):
    """
    The operational environment (e.g. test vs. production) to use for connection purposes.
    """
    DEV = 'dev'
    TEST = 'test'
    PRODUCTION = 'prod'


class Region(Enum):
    """
    The regional installation of Serenity to use for connection purposes.
    """
    US_PRIMARY = 'eastus2'


class SerenityClient:
    def __init__(self, config_json: Any, env: Environment = Environment.PRODUCTION, region: Region = Region.US_PRIMARY):
        scopes = get_scopes(env)
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
        api_base_url = f'https://serenity-rest-{self.env.value}-{self.region.value}' \
                       f'.cloudwall.network/{self.version}/{api_group}{api_path}'
        if body_json:
            response_json = requests.post(api_base_url, headers=self.http_headers,
                                          params=params, json=body_json).json()
        else:
            response_json = requests.get(api_base_url, headers=self.http_headers,
                                         params=params).json()

        return response_json


def load_local_config(config_id: str) -> Any:
    """
    Helper function that lets you read a JSON config file with client ID and client secret from
    $HOME/.serenity/${config_id}.json on your local machine. NOTE: for security reasons this
    function will fail if the file is world-readable.
    """
    home_dir = os.path.expanduser('~')
    config_path = os.path.join(home_dir, '.serenity', f'{config_id}.json')
    st = os.stat(config_path)

    # basic security check because this config file contains a cloud client secret
    unsafe_file_perms = bool(st.st_mode & (stat.S_IRGRP | stat.S_IROTH))
    if unsafe_file_perms:
        raise IOError(f'{config_path} should only be readable by the current user')

    # good to load
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


def get_scopes(env: Environment = Environment.PRODUCTION, region: Region = Region.US_PRIMARY) -> List[str]:
    """
    Helper function that returns the login scopes required to access the API given an environment
    and a region. In general you do not need to call this directly.
    """
    return [
        f'https://serenity-api-{env.value}-{region.value}.cloudwall.network/.default'
    ]
