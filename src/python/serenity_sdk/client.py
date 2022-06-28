from enum import Enum
from typing import List


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


def get_scopes(env: Environment = Environment.PRODUCTION, region: Region = Region.US_PRIMARY) -> List[str]:
    """
    Helper function that returns the login scopes required to access the API given an environment
    and a region. In general you do not need to call this directly.
    """
    return [
        f'https://serenity-api-{env.value}-{region.value}.cloudwall.network/.default'
    ]
