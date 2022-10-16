# flake8: noqa

import datetime
import pandas as pd

from ipywidgets import (Button, Combobox, Dropdown, HBox, 
                        RadioButtons, VBox)
from IPython.display import display

from serenity_sdk.client import SerenityApiProvider, SerenityClient
from serenity_sdk.config import Environment, Region, load_local_config

api_config = Combobox(placeholder='Choose API config',
                      options=['athansor', 'pgi'],
                      value='pgi',
                      description='API Config:',
                      ensure_option=True,
                      disabled=False)

env = RadioButtons(options=['DEV', 'TEST', 'PRODUCTION'],
                   value='PRODUCTION',
                   description='Environment:',
                   disabled=False)

region = Dropdown(options=['EASTUS', 'EASTUS_2', 'GLOBAL'],
                  value='GLOBAL',
                  description='Region:',
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
    env_value = Environment[env.value]
    region_value = Region[region.value]
                            
    config = load_local_config(config_id)
    client = SerenityClient(config, env=env_value, region=region_value)
    api = SerenityApiProvider(client)

connect.on_click(on_connect)

hbox = HBox([api_config, env, region])
vbox = VBox([hbox, connect])

display(vbox)
