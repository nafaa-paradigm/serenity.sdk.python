from datetime import datetime
from typing import AnyStr, Dict, List

from azure.identity import ClientSecretCredential

from serenity_sdk.config import ConnectionConfig


SERENITY_CLIENT_ID_HEADER = 'X-Serenity-Client-ID'


class AuthHeaders:
    """
    Helper object that carries all the headers required for API authentication and authorization.
    """
    def __init__(self, credential: object, scopes: List[str], user_app_id: str):
        """
        Creates an initial access token using the given credentials and scopes.

        :param credential: the Azure credential object
        :param scopes: the list of scopes for API authorization
        :param user_app_id: the unique ID for this API secret
        """
        self.credential = credential
        self.user_app_id = user_app_id
        self.scopes = scopes

        self.access_token = None
        self.ensure_not_expired()

    def ensure_not_expired(self):
        """
        Check whether we need to refresh the bearer token now.
        """
        expired = not self.access_token or int(datetime.utcnow().timestamp()) >= self.access_token.expires_on
        if expired:
            self._refresh_token()

    def get_http_headers(self) -> Dict[AnyStr, AnyStr]:
        """
        Gets the current set of headers including latest Bearer token for authentication.
        """
        return self.http_headers

    def _refresh_token(self):
        self.access_token = self.credential.get_token(*self.scopes)
        self.http_headers = {'Authorization': f'Bearer {self.access_token.token}',
                             SERENITY_CLIENT_ID_HEADER: self.user_app_id}


def get_credential_user_app(config: ConnectionConfig) -> object:
    """
    Standard mechanism to acquire a credential for accessing the Serenity API. You
    can create one or more user applications using the Serenity Admin screen, and
    as part of setup you will be given the application's client ID and secret.

    :param config: Serenity API Management API configuration from `load_local_config()`
    """
    return ClientSecretCredential(config.tenant_id,
                                  config.client_id,
                                  config.user_application_secret)


def create_auth_headers(credential: object, scopes: List[str], user_app_id: str) -> Dict[str, str]:
    """
    Helper function for the standard requests module to construct the appropriate
    HTTP headers for a given set of API endpoints (scopes) and a user application's
    client ID. The latter is used by Serenity to distinguish between different client
    applications on the backend.
    """
    return AuthHeaders(credential, scopes, user_app_id)
