# flake8: noqa

import datetime
import pandas as pd

from ipywidgets import (Button, Combobox, Dropdown, HBox, 
                        RadioButtons, VBox)
from IPython.display import display

from serenity_sdk.client import SerenityApiProvider, SerenityClient
from serenity_sdk.config import Environment, Region, load_local_config

api_config = Combobox(placeholder='Choose API config',
                      options=['athansor-dev', 'athansor-test' 'pgi'],
                      value='pgi',
                      description='API Config:',
                      ensure_option=True,
                      disabled=False)

connect = Button(description='Connect',
                 disabled=False,
                 button_style='',
                 tooltip='Connect to Serenity',
                 icon='link')

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

connect.on_click(on_connect)

hbox = HBox([api_config])
vbox = VBox([hbox, connect])

display(vbox)
