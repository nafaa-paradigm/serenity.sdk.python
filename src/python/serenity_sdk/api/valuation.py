from serenity_sdk.api.core import SerenityApi
from serenity_sdk.client.raw import CallType, SerenityClient
from serenity_sdk.types.common import Portfolio, PricingContext
from serenity_sdk.types.valuation import ValuationResult


class ValuationApi(SerenityApi):
    """
    The valuation API group covers basic tools for NAV and other portfolio valuation calcs.
    """
    def __init__(self, client: SerenityClient):
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'valuation')

    def compute_portfolio_value(self, ctx: PricingContext, portfolio: Portfolio) -> ValuationResult:
        """
        Computes portfolio NAV and other high-level valuation details at both the portfolio level
        and position-by-position.

        :param ctx: the pricing parameters to use, e.g. which base currency and the as-of date for prices
        :param portfolio: the portfolio to value
        :return: a parsed :class:`ValuationResult` containing all portfolio & position values
        """
        request = {
            'portfolio': {'assetPositions': portfolio.to_asset_positions()},
            'pricing_context': {
                **self._create_std_params(ctx.as_of_date),
                'portfolio': {'assetPositions': portfolio.to_asset_positions()},
                'markTime': ctx.mark_time.value,
                'baseCurrencyId': str(ctx.base_currency_id),
                'cashTreatment': ctx.cash_treatment.value
            }
        }
        raw_json = self._call_api('/portfolio/compute', {}, request, CallType.POST)
        return ValuationResult._parse(raw_json)
