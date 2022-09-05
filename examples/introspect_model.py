#!/usr/bin/env python

import fire

from serenity_sdk.client import Environment, Region, SerenityApiProvider, SerenityClient, load_local_config


def main(config_id: str, env: str = 'PRODUCTION', region: str = 'GLOBAL'):
    config = load_local_config(config_id)
    client = SerenityClient(config, env=Environment[env], region=Region[region])
    api_provider = SerenityApiProvider(client)

    # load all the metadata
    model_meta = api_provider.model().load_model_metadata()

    # dumps out basic information about the model library
    print('\nAvailable Serenity model classes:')
    for model_class in model_meta.get_model_class_names():
        print('\t', model_class)

    print('\nAvailable models:')
    for model in model_meta.get_model_names():
        print('\t', model)

    print('\nAvailable model configurations:')
    for model_config in model_meta.get_model_configuration_names():
        print('\t', model_config)

    # demonstrates looking up a model configuration by its short name
    print(f'\nSFRM model configuration ID: {model_meta.get_model_configuration_id("risk.factor.regression.SLM.MT")}')


if __name__ == '__main__':
    fire.Fire(main)
