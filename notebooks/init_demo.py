# flake8: noqa

import datetime
import pandas as pd

from ipywidgets import Button, HBox, Output, Text, VBox
from IPython.display import clear_output, display

from serenity_sdk.client import SerenityApiProvider, SerenityClient
from serenity_sdk.config import Environment, Region, load_local_config

api_config = Text(description='API Config:')
connect = Button(description='Connect',
                 disabled=False,
                 button_style='',
                 tooltip='Connect to Serenity',
                 icon='link')

out = Output()

client = None
api = None
env_value = None

def on_connect(button):
    global client
    global api
    global env_value
    
    config_id = api_config.value
    config = load_local_config(config_id)
    client = SerenityClient(config)
    api = SerenityApiProvider(client)
    with (out):
        clear_output()
        print(f'Connecting to {config_id}: env={client.env}, URL={client.config.url}')

connect.on_click(on_connect)

hbox = HBox([api_config])
vbox = VBox([hbox, connect])

display(vbox)
display(out)
