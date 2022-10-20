from dataclasses import dataclass
from typing import Any, Dict
from uuid import UUID


class PortfolioValue:
    # forward declaration
    pass


@dataclass
class PortfolioValue:
    net_holdings_value: float
    gross_holdings_value: float
    cash_position_value: float
    net_asset_value: float

    @staticmethod
    def parse(raw_json: Any) -> PortfolioValue:
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
    price: float
    quantity: float
    weight: float

    @staticmethod
    def parse(raw_json: Any) -> PositionValue:
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
    previous: PositionValue

    @staticmethod
    def parse(raw_json: Any) -> PositionValues:
        close = PositionValue.parse(raw_json['close'])
        previous = PositionValue.parse(raw_json['previous'])
        return PositionValues(close, previous)


class ValuationResult:
    # forward declaration
    pass


@dataclass
class ValuationResult:
    close: PortfolioValue
    previous: PortfolioValue
    positions: Dict[UUID, PositionValue]

    @staticmethod
    def parse(raw_json: Any) -> ValuationResult:
        close = PortfolioValue.parse(raw_json['close'])
        previous = PortfolioValue.parse(raw_json['previous'])
        positions = {
            UUID(asset_id): PositionValues.parse(position_values)
            for asset_id, position_values in raw_json['positions'].items()
        }
        return ValuationResult(close, previous, positions)
