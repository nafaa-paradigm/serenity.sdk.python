from dataclasses import dataclass
from typing import Any, Dict
from uuid import UUID


class PortfolioValue:
    # forward declaration
    pass


@dataclass
class PortfolioValue:
    """
    Wrapper object holding all of the valuation output for a given portfolio
    """

    net_holdings_value: float
    """
    The net value of the portfolio's assets excluding cash; the sum of all position values
    """

    gross_holdings_value: float
    """
    The gross value of the portfolio's assets excluding cash; the sum of the absolute values of all position values
    """

    cash_position_value: float
    """
    The total value of the portfolio's cash positionsm, as defined by :class:`CashTreatment`
    """

    net_asset_value: float
    """
    The sum of the net holdings and the cash positions, or NAV
    """

    @staticmethod
    def _parse(raw_json: Any) -> PortfolioValue:
        net_holdings_value = raw_json['netHoldingsValue']
        gross_holdings_value = raw_json['grossHoldingsValue']
        cash_position_value = raw_json['cashPositionValue']
        net_asset_value = raw_json['netAssetValue']
        return PortfolioValue(net_holdings_value, gross_holdings_value, cash_position_value, net_asset_value)


class PositionValue:
    # forward declaration
    pass


@dataclass
class PositionValue:
    value: float
    """
    The value of this specific position, expressed in base currency
    """

    price: float
    """
    The price used to calculate this position value
    """

    quantity: float
    """
    The quantity of the asset used to calculate this position value
    """

    weight: float
    """
    The percentage weight of this asset in the whole portfolio; may be negative in long/short portfolios
    """

    @staticmethod
    def _parse(raw_json: Any) -> PositionValue:
        value = raw_json['value']
        price = raw_json['price']
        quantity = raw_json['qty']
        weight = raw_json['weight']
        return PositionValue(value, price, quantity, weight)


class PositionValues:
    # forward declaration
    pass


@dataclass
class PositionValues:
    close: PositionValue
    """
    The value of the position as of the most recent close, based on :class:`MarkTime`
    """

    previous: PositionValue
    """
    The value of the position as of the previous close, based on :class:`MarkTime`
    """

    @staticmethod
    def _parse(raw_json: Any) -> PositionValues:
        close = PositionValue._parse(raw_json['close'])
        previous = PositionValue._parse(raw_json['previous'])
        return PositionValues(close, previous)


class ValuationResult:
    # forward declaration
    pass


@dataclass
class ValuationResult:
    close: PortfolioValue
    """
    The value of the portfolio as of the most recent close, based on :class:`MarkTime`
    """

    previous: PortfolioValue
    """
    The value of the portfolio as of the previous close, based on :class:`MarkTime`
    """

    positions: Dict[UUID, PositionValue]
    """
    The values of the individual constituents of the portfolio
    """

    @staticmethod
    def _parse(raw_json: Any) -> ValuationResult:
        close = PortfolioValue._parse(raw_json['close'])
        previous = PortfolioValue._parse(raw_json['previous'])
        positions = {
            UUID(asset_id): PositionValues._parse(position_values)
            for asset_id, position_values in raw_json['positions'].items()
        }
        return ValuationResult(close, previous, positions)
