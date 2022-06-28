from typing import Dict, List

from azure.identity import ClientSecretCredential

SERENITY_CLIENT_ID_HEADER = 'X-Serenity-Client-ID'


def get_credential_user_app(client_id: str, client_secret: str, tenant_id: str) -> object:
    """
    Standard mechanism to acquire a credential for accessing the Serenity API. You
    can create one or more user applications using the Serenity Admin screen, and
    as part of setup you will be given the application's client ID and secret.
    """
    return ClientSecretCredential(tenant_id, client_id, client_secret)


def create_auth_headers(credential: object, scopes: List[str], user_app_id: str) -> Dict[str, str]:
    """
    Helper function for the standard requests module to construct the appropriate
    HTTP headers for a given set of API endpoints (scopes) and a user application's
    client ID. The latter is used by Serenity to distinguish between different client
    applications on the backend.
    """
    access_token = credential.get_token(*scopes)
    http_headers = {'Authorization': f'Bearer {access_token.token}',
                    SERENITY_CLIENT_ID_HEADER: user_app_id}

    return http_headers
