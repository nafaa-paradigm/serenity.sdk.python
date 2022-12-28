from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

import json

from serenity_sdk.api.core import SerenityApi
from serenity_sdk.client.raw import CallType, SerenityClient
from serenity_types.pricing.derivatives.options.valuation import OptionValuationRequest, OptionValuationResult
from serenity_types.pricing.derivatives.options.volsurface import (VolatilitySurfaceAvailability,
                                                                   VolatilitySurfaceVersion)
from serenity_types.pricing.derivatives.rates.yield_curve import YieldCurveAvailability, YieldCurveVersion
from serenity_types.refdata.currency import Currency
from serenity_types.refdata.futures import Future
from serenity_types.refdata.options import ListedOption
from serenity_types.refdata.token import TokenAsset


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

    def get_supported_currencies(self, as_of_date: Optional[date] = None) -> List[Currency]:
        """
        Gets a list of currencies that can be used for quote asset and base currency; currently USD only.

        :param as_of_date: optional date to use when loading reference data; defaults to latest, from cache
        """
        PricerApi._validate_as_of_date_not_supported(as_of_date)
        raw_json = self._call_api('/derivatives/refdata/currencies', {})
        return [Currency.parse_obj(raw_avail) for raw_avail in raw_json['result']]

    def get_supported_futures(self, as_of_date: Optional[date] = None,
                              underlier_asset_id: Optional[UUID] = None) -> List[Future]:
        """
        Gets a list of active futures that may be referenced in projection curve points;
        currently Deribit BTC and ETH futures only.

        :param as_of_date: optional date to use when loading reference data; defaults to latest, from cache
        :param underlier_asset_id: optional filter to limit to futures on the given underlier, defaults to all
        """
        params = {}
        if underlier_asset_id:
            params['underlier_asset_id'] = underlier_asset_id
        raw_json = self._call_api('/derivatives/refdata/futures', params)
        return [Future.parse_obj(raw_avail) for raw_avail in raw_json['result']]

    def get_supported_options(self, as_of_date: Optional[date] = None,
                              underlier_asset_id: Optional[UUID] = None) -> List[ListedOption]:
        """
        Gets a list of active listed options that can be priced using the API;
        currently only Deribit BTC and ETH options.

        :param as_of_date: optional date to use when loading reference data; defaults to latest, from cache
        :param underlier_asset_id: optional filter to limit to options on the given underlier, defaults to all
        """
        PricerApi._validate_as_of_date_not_supported(as_of_date)
        params = {}
        if underlier_asset_id:
            params['underlier_asset_id'] = underlier_asset_id
        raw_json = self._call_api('/derivatives/refdata/options', params)
        return [ListedOption.parse_obj(raw_avail) for raw_avail in raw_json['result']]

    def get_supported_underliers(self, as_of_date: Optional[date] = None) -> List[TokenAsset]:
        """
        Gets all the underlying tokens supported by the system for derivatives pricing (currently only BTC and ETH).

        :param as_of_date: optional date to use when loading reference data; defaults to latest, from cache
        """
        PricerApi._validate_as_of_date_not_supported(as_of_date)
        raw_json = self._call_api('/derivatives/refdata/underliers', {})
        return [TokenAsset.parse_obj(raw_avail) for raw_avail in raw_json['result']]

    @staticmethod
    def _validate_as_of_date_not_supported(as_of_date: Optional[date]):
        if as_of_date:
            raise ValueError("as_of_date is not yet supported in the Derivatives Refdata API; "
                             "historical support expected Q1'23")
