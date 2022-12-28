from datetime import date
from typing import Any, List

from serenity_sdk.api.core import SerenityApi
from serenity_sdk.client.raw import SerenityClient
from serenity_sdk.types.model import ModelMetadata


class ModelApi(SerenityApi):
    """
    Helper class for the Model Metadata API, which lets clients introspect model parameters
    and other information about available risk models. This endpoint is also required for
    looking up the appropriate Model Configuration ID in the forthcoming Risk API upgrade
    so you can specify which configuration you want to use for risk attribution, scenarios
    and other risk tools.
    """
    def __init__(self, client: SerenityClient):
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'catalog')

    def load_model_metadata(self, as_of_date: date = None) -> ModelMetadata:
        """
        Helper method that preloads all the model metadata into memory for easy access.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        model_classes = self.get_model_classes(as_of_date)
        models = self.get_models(as_of_date)
        model_configs = self.get_model_configurations(as_of_date)
        return ModelMetadata(model_classes, models, model_configs)

    def get_model_classes(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/modelclasses', params=params)['modelClasses']

    def get_models(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/models', params=params)['models']

    def get_model_configurations(self, as_of_date: date = None) -> List[Any]:
        """
        Gets the list of available model classes, e.g. Market Risk, Liquidity Risk or VaR.
        These are the high-level groups of models supported by Serenity.

        :param as_of_date: the effective date for the model metadata in the database, else latest if None
        """
        params = SerenityApi._create_std_params(as_of_date)
        return self._call_api('/model/modelconfigurations', params=params)['modelConfigurationSummaries']
