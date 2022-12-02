import ipywidgets as widgets
import numpy as np
import pandas as pd


class VersionTimeChooser:
    def __init__(self, versions: list, id_key: str):
        self.versions = versions
        self.id_key = id_key
        self.name_to_id = {v.definition.display_name: getattr(v.definition, id_key) for v in versions}
        self.available_id_times = {
            getattr(v.definition, id_key):
            sorted([as_of_time.replace(tzinfo=None) for as_of_time in v.as_of_times], reverse=True)
            for v in versions}

        self.widget_name = widgets.Dropdown(
            options=[name for name in self.name_to_id],
            value=None,
            description='Name')

        self.widget_id = widgets.Text(
            value='',
            description='Id (uuid)',
            disabled=False)

        self.widget_as_of_time = widgets.Dropdown(
            options=[],
            disabled=False,
            description='as-of Time')
        self.id_selected = None
        self.widget_name.observe(self.__name_changed, names='value')

        # set the first element into name box
        self.widget_name.value = list(self.name_to_id)[0]

    def __name_changed(self, wb):
        name = self.widget_name.value
        id = self.name_to_id[name]
        self.widget_as_of_time.options = self.available_id_times[id]
        self.widget_id.value = str(id)
        self.selected_id = id

    def get_widget_to_display(self):
        return widgets.VBox(
            [widgets.HBox([self.widget_name, self.widget_as_of_time]),
             self.widget_id])

    def get_id_as_of_time(self):
        return self.selected_id, self.widget_as_of_time.value


class YieldCurveVersionTimeChooser(VersionTimeChooser):
    def __init__(self, versions):
        super().__init__(versions, 'yield_curve_id')


class VolatilitySurfaceVersionTimeChooser(VersionTimeChooser):
    def __init__(self, versions):
        super().__init__(versions, 'vol_surface_id')


class OptionChooser:

    def __init__(self, option_data: pd.DataFrame):
        self.data = option_data.reset_index()

        linked_asset_symbols = np.sort(self.data['linked_asset_native_symbol'].unique())

        self.widget_linked_asset_symbol = widgets.Dropdown(
            options=linked_asset_symbols,
            value=None,
            description='Linked Asset'
        )

        self.widget_expiry = widgets.Dropdown(
            options=[],
            disabled=False,
            description='Expiry'
        )

        self.widget_strike = widgets.Dropdown(
            options=[],
            disabled=False,
            description='Strike'
        )

        self.widget_option_type = widgets.Dropdown(
            options=[],
            disabled=False,
            description='Type'
        )

        self.widget_linked_asset_symbol.observe(self.__widget_linked_asset_symbol_changed, names='value')
        self.widget_expiry.observe(self.__widget_expiry_changed, names='value')
        self.widget_strike.observe(self.__widget_strike_changed, names='value')

        # set the initial symbol
        self.widget_linked_asset_symbol.value = linked_asset_symbols[0]
        self.widget_expiry.value = self.widget_expiry.options[-1]
        num_strikes = len(self.widget_strike.options)
        self.widget_strike.value = self.widget_strike.options[num_strikes//2]

    def __match(self, level=4):
        cols = ['linked_asset_native_symbol', 'expiry_datetime', 'strike_price', 'option_type']
        wdgts = [self.widget_linked_asset_symbol, self.widget_expiry, self.widget_strike, self.widget_option_type]

        df = self.data
        for i in range(level):
            df = df[df[cols[i]] == wdgts[i].value].copy()
        return df

    def __widget_linked_asset_symbol_changed(self, wb):

        df = self.__match(1)
        expiries = list(np.sort(df['expiry_datetime'].unique()))
        self.widget_expiry.options = expiries

    def __widget_expiry_changed(self, wb):

        df = self.__match(2)
        self.widget_strike.options = list(np.sort(df['strike_price'].unique()))

    def __widget_strike_changed(self, wb):

        df = self.__match(3)
        self.widget_option_type.options = list(np.sort(df['option_type'].unique()))

    def get_widget_to_display(self):
        return widgets.VBox([self.widget_linked_asset_symbol, self.widget_expiry,
                             self.widget_strike, self.widget_option_type])

    def get_selected_option(self) -> pd.Series:

        df = self.__match(4)

        if df.shape[0] != 1:
            raise ValueError('Something went wrong. Check your selection')
        else:
            return df.iloc[0].to_dict()
