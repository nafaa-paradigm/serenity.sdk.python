from typing import Optional
from datetime import datetime, date
import itertools
import pandas as pd
from serenity_sdk.client import SerenityApiProvider
from .converters import convert_object_list_to_df


def get_predefined_option_infos(api: SerenityApiProvider, as_of_date: Optional[date] = None):

    underliers = api.pricer().get_supported_underliers(as_of_date=as_of_date)
    underliers_df = convert_object_list_to_df(underliers)
    # underliers_df

    # Load using get_supported_options call and convert them to a dataframe for an easier display
    option_df = convert_object_list_to_df(itertools.chain.from_iterable((
        api.pricer().get_supported_options(as_of_date=as_of_date, underlier_asset_id=underlier.asset_id)
        for underlier in underliers)))

    # Add additional fields to help displaying
    # (1) add underlier_asset_id
    option_df = pd.merge(option_df, underliers_df[['asset_id', 'native_symbol']],
                         left_on='underlier_asset_id', right_on='asset_id', suffixes=['', '_underlier'])
    # (2) add expiry_datetime by combining date and time information into one
    option_df['expiry_datetime'] = option_df['expiry'].apply(
        lambda x: datetime.combine(x.expiration_date, x.expiration_time))
    # (3) select key columns
    option_df = option_df[['asset_id', 'asset_type', 'native_symbol', 'underlier_asset_id',
                           'contract_size', 'option_type', 'option_style',
                           'strike_price', 'expiry', 'expiry_datetime', 'native_symbol_underlier', 'display_name']]

    return option_df
