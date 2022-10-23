from collections import defaultdict
from enum import Enum
from typing import Any, AnyStr, Dict, List
from uuid import UUID

from serenity_sdk.types.common import Portfolio


class SectorTaxonomy(Enum):
    """
    Transition enum until the next release is deployed, supporting lookup via API of
    sector taxonomy UUID's so you can use arbitrary taxonomies (including user-defined)
    """
    DACS = "DACS"
    DATS = "DATS"


class AssetMaster:
    """
    Result class that holds the contents of the Serenity asset catalog in memory,
    making it easier to query it and also to create Portfolio objects from it.
    """
    def __init__(self, asset_summaries: List[Any]):
        self.asset_summaries = asset_summaries

        # map UUID => authority => symbol
        self.asset_id_map = {summary['assetId']: {xref_symbol['authority']['name']: xref_symbol['symbol']
                             for xref_symbol in summary['xrefSymbols']} for summary in asset_summaries}

        # inverse map authority => symbol => UUID
        self.asset_id_map = defaultdict(dict)
        self.symbol_map = defaultdict(dict)
        for summary in asset_summaries:
            asset_id = UUID(summary['assetId'])
            native_symbol = summary['nativeSymbol']
            asset_symbol = summary['assetSymbol']

            # add in aliases from various vendors
            for xref_symbol in summary['xrefSymbols']:
                authority = xref_symbol['authority']['name']
                symbol = xref_symbol['symbol']

                self.asset_id_map[asset_id][authority] = symbol
                self.asset_id_map[asset_id]['NATIVE'] = native_symbol
                self.asset_id_map[asset_id]['SERENITY'] = asset_symbol

                self.symbol_map[authority][symbol] = asset_id

            # add in pseudo-symbols for looking up blockchain-native and Serenity symbologies
            self.symbol_map['NATIVE'][native_symbol] = asset_id
            self.symbol_map['SERENITY'][asset_symbol] = asset_id

    def create_portfolio(self, positions: Dict[AnyStr, float], symbology: str = 'NATIVE') -> Portfolio:
        """
        Mapping function that takes a set of raw positions in a given symbology and then converts them
        to Serenity's internal identifiers and creates a Portfolio that can then be used with our tools.
        Note there are two 'special' symbologies, NATIVE and SERENITY. NATIVE uses the native blockchain
        symbol and SERENITY uses Serenity's own native symbology, e.g. BTC and tok.btc.bitcoin
        respectively. The rest correspond to the API's list of symbol authorities, e.g. COINGECKO.

        :param positions: a raw mapping from symbol to weight, where negative weights indicate short positions
        :param symbology: a name from the list of supported symbol authorities, e.g. `COINGECKO`, or
            one of two special symbologies, NATIVE or SERENITY; NATIVE uses the native blockchain
            symbol and SERENITY uses Serenity's own native symbology, e.g. `BTC` and `tok.btc.bitcoin`
            respectively
        """
        asset_positions = {self.get_asset_id_by_symbol(symbol, symbology): qty for (symbol, qty) in positions.items()}
        return Portfolio(asset_positions)

    def get_symbol_by_id(self, asset_id: UUID, symbology: str = 'NATIVE'):
        """
        Lookup helper that gets a particular symbol type for a given asset ID.

        :param asset_id: Serenity's unique ID for this asset
        :param symbology: a name from the list of supported symbol authorities, e.g. `COINGECKO`, or
            one of two special symbologies, NATIVE or SERENITY; NATIVE uses the native blockchain
            symbol and SERENITY uses Serenity's own native symbology, e.g. `BTC` and `tok.btc.bitcoin`
            respectively
        """
        asset_id_symbols = self.asset_id_map.get(asset_id, None)
        if not asset_id_symbols:
            raise ValueError(f'Unknown asset_id: {str(asset_id)}')

        symbol = asset_id_symbols.get(symbology, None)
        if not symbol:
            raise ValueError(f'Unknown symbology {symbology} for asset_id: {str(asset_id)}')

        return symbol

    def get_asset_id_by_symbol(self, symbol: str, symbology: str = 'NATIVE'):
        """
        Lookup helper that looks up asset ID by symbol based on a given symbology.

        :param symbol: a known symbol for this asset, e.g. BTC or bitcoin
        :param symbology: a name from the list of supported symbol authorities, e.g. `COINGECKO`, or
            one of two special symbologies, NATIVE or SERENITY; NATIVE uses the native blockchain
            symbol and SERENITY uses Serenity's own native symbology, e.g. `BTC` and `tok.btc.bitcoin`
            respectively
        """
        symbology_symbols = self.symbol_map.get(symbology, None)
        if not symbology_symbols:
            raise ValueError(f'Unknown symbology {symbology} for symbol: {symbol}')

        asset_id = symbology_symbols.get(symbol, None)
        if not asset_id:
            raise ValueError(f'Unknown symbol {symbol} in symbology {symbology}')

        return asset_id
