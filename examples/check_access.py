import fire

from serenity_sdk.auth import create_auth_headers, get_credential_user_app
from serenity_sdk.client import Environment, get_scopes


def main(tenant: str, client_id: str, client_secret: str, user_app_id: str):
    scopes = get_scopes(env=Environment.DEV)
    credential = get_credential_user_app(client_id=client_id,
                                         client_secret=client_secret,
                                         tenant_id=f'{tenant}.onmicrosoft.com')
    header = create_auth_headers(credential, scopes, user_app_id=user_app_id)

    print(header)


if __name__ == '__main__':
    fire.Fire(main)
