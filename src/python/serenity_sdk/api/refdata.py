from datetime import date
from typing import Any, AnyStr, Dict, List
from uuid import UUID

from serenity_sdk.api.core import SerenityApi
from serenity_sdk.client.raw import SerenityClient
from serenity_sdk.types.refdata import AssetMaster


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
