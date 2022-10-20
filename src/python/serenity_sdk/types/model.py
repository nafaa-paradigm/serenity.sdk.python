from typing import Any, AnyStr, Dict, List
from uuid import UUID


class ModelMetadata:
    """
    Helper class that encapsulates all the model metadata. You can get at the underlying calls directly from the
    ModelApi client or you can just load everything in this class and use it to traverse the metadata tree.

    The most important call is probably get_model_configuration_id(), which lets you do a lookup of a
    ModelConfiguration ID by the short name. This is needed to specify model inputs for risk calcs.
    """
    def __init__(self, model_classes: List[Any],  models: List[Any], model_configs: List[Any]):
        self.model_classes = model_classes
        self.models = models
        self.model_configs = model_configs
        self.model_config_map = {model_config['shortName']: UUID(model_config['modelConfigId'])
                                 for model_config in model_configs}

    def get_model_class_names(self) -> List[str]:
        """
        Enumerates the names of model classes, groupings of related models like Market Risk,
        Liquidity Risk or Value at Risk.
        """
        # allow for missing displayName until production upgraded
        return [model_class.get('displayName', model_class['shortName']) for model_class in self.model_classes]

    def get_model_names(self) -> List[str]:
        """
        Enumerates the names of all models; this corresponds to code implementations
        of different types of models.
        """
        # allow for missing displayName until production upgraded
        return [model.get('displayName', model['shortName']) for model in self.models]

    def get_model_configurations(self) -> Dict[AnyStr, AnyStr]:
        """
        Enumerates the names of all model configurations; this corresponds to specific
        parameterizations of models, e.g. short time horizon and long time horizon
        variations of a factor risk model are two different configurations.
        """

        # allow for missing displayName until production upgraded
        return {model_config['shortName']: model_config.get('displayName', None) for model_config in self.model_configs}

    def get_model_configuration_id(self, short_name: str) -> UUID:
        """
        Lookup function that gives you the UUID of a ModelConfiguration given
        its short name. Returns None if unknown.
        """
        model_config_id = self.model_config_map.get(short_name, None)
        if not model_config_id:
            raise ValueError(f'Unknown ModelConfiguration: {short_name}')
        return model_config_id
