# -*- coding: utf-8 -*-
"""
Just an app to visualize raster time series.

Created on Fri Jan  4 12:39:23 2019

@author: User

Sync Check: 01/20/2019
"""

# In[] Functions and Libraries
import os
import sys
import copy
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import datetime as dt
import gc
import json
import pandas as pd
import numpy as np
import psutil
import time
import warnings
import xarray as xr
warnings.filterwarnings("ignore")

# Check if we are working in Windows or Linux
if sys.platform == 'win32':
    home_path = 'z:/Sync'
    data_path = 'd:/'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
else:
    home_path = '/root/Sync'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
    data_path = '/root'

# sys.path.insert(0, os.path.join(home_path,
#                                 'Ubuntu-Practice-Machine', 'scripts'))

import functions
from functions import Index_Maps

# In[] Create the DASH App object
app = dash.Dash(__name__)

# Go to stylesheet, styled after a DASH example (how to serve locally?)
app.css.append_css({'external_url':
                    'https://codepen.io/williamstravis/pen/maxwvK.css'})
app.scripts.config.serve_locally = True

# For the Loading screen - just trying Chriddyp's for now
app.css.append_css({"external_url":
                    "https://codepen.io/williamstravis/pen/EGrWde.css"})

# Create Server Object
server = app.server

# Disable exceptions (attempt to speed things up)
app.config['suppress_callback_exceptions'] = True

# Create four simple caches, each holds one large array, one for each map
cache1 = functions.Cacher(1)
cache2 = functions.Cacher(2)
cache3 = functions.Cacher(3)
cache4 = functions.Cacher(4)

# In[] Drought and Climate Indices (looking to include any raster time series)
# Index Paths (for npz files)
indices = [{'label': 'Rainfall Index', 'value': 'noaa'},
           {'label': 'PDSI', 'value': 'pdsi'},
           {'label': 'PDSI-Self Calibrated', 'value': 'pdsisc'},
           {'label': 'Palmer Z Index', 'value': 'pdsiz'},
           {'label': 'SPI-1', 'value': 'spi1'},
           {'label': 'SPI-2', 'value': 'spi2'},
           {'label': 'SPI-3', 'value': 'spi3'},
           {'label': 'SPI-6', 'value': 'spi6'},
           {'label': 'SPEI-1', 'value': 'spei1'},
           {'label': 'SPEI-2', 'value': 'spei2'},
           {'label': 'SPEI-3', 'value': 'spei3'},
           {'label': 'SPEI-6', 'value': 'spei6'},
           {'label': 'EDDI-1', 'value': 'eddi1'},
           {'label': 'EDDI-2', 'value': 'eddi2'},
           {'label': 'EDDI-3', 'value': 'eddi3'},
           {'label': 'EDDI-6', 'value': 'eddi6'}]

# Index dropdown labels
indexnames = {'noaa': 'NOAA CPC-Derived Rainfall Index',
              'pdsi': 'Palmer Drought Severity Index',
              'pdsisc': 'Self-Calibrated Palmer Drought Severity Index',
              'pdsiz': 'Palmer Z Index',
              'spi1': 'Standardized Precipitation Index - 1 month',
              'spi2': 'Standardized Precipitation Index - 2 month',
              'spi3': 'Standardized Precipitation Index - 3 month',
              'spi6': 'Standardized Precipitation Index - 6 month',
              'spei1': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 1 month',
              'spei2': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 2 month',
              'spei3': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 3 month',
              'spei6': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 6 month',
              'eddi1': 'Evaporative Demand Drought Index - 1 month',
              'eddi2': 'Evaporative Demand Drought Index - 2 month',
              'eddi3': 'Evaporative Demand Drought Index - 3 month',
              'eddi6': 'Evaporative Demand Drought Index - 6 month'}

# Function options
function_options = [{'label': 'Mean - Percentiles', 'value': 'mean_perc'},
                    {'label': 'Maximum - Percentiles', 'value': 'max'},
                    {'label': 'Minimum - Percentiles', 'value': 'min'},
                    {'label': 'Mean - Original Values',
                     'value': 'mean_original'},
                    {'label': 'Maximum - Original Values', 'value': 'omax'},
                    {'label': 'Minimum - Original Values', 'value': 'omin'},
                    {'label': 'Coefficient of Variation - Original Value',
                     'value': 'ocv'}]
function_names = {'mean_perc': 'Average Percentiles',
                  'max': 'Maxmium Percentile',
                  'min': 'Minimum Percentile',
                  'mean_original': 'Average Original Index Values',
                  'omax': 'Maximum Original Value',
                  'omin': 'Minimum Original Value',
                  'ocv': 'Coefficient of Variation for Original Values'}

# For the county names - need to get a more complete data set
grid = np.load(data_path + "/data/prfgrid.npz")["grid"]
mask = grid*0+1
counties_df = pd.read_csv("data/counties.csv")
counties_df = counties_df[['grid', 'county', 'state']]
# counties_df['grid'] = counties_df['grid'].astype(str)
counties_df['place'] = (counties_df['county'] +
                        ' County, ' + counties_df['state'])

# For when EDDI before 1980 is selected
with np.load("data/NA_overlay.npz") as data:
    na = data.f.arr_0
    data.close()

# Make the color scale stand out 
for i in range(na.shape[0]):
    na[i] = na[i]*i

# In[] The map
# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')

# For testing
source_signal = [[[2000, 2017], [1, 12]], 'mean_perc', 'Viridis', 'no', 'pdsi']



# Map types
maptypes = [{'label': 'Light', 'value': 'light'},
            {'label': 'Dark', 'value': 'dark'},
            {'label': 'Basic', 'value': 'basic'},
            {'label': 'Outdoors', 'value': 'outdoors'},
            {'label': 'Satellite', 'value': 'satellite'},
            {'label': 'Satellite Streets', 'value': 'satellite-streets'}]

RdWhBu = [[0.00, 'rgb(115,0,0)'],
          [0.10, 'rgb(230,0,0)'],
          [0.20, 'rgb(255,170,0)'],
          [0.30, 'rgb(252,211,127)'],
          [0.40, 'rgb(255, 255, 0)'],
          [0.45, 'rgb(255, 255, 255)'],
          [0.55, 'rgb(255, 255, 255)'],
          [0.60, 'rgb(143, 238, 252)'],
          [0.70, 'rgb(12,164,235)'],
          [0.80, 'rgb(0,125,255)'],
          [0.90, 'rgb(10,55,166)'],
          [1.00, 'rgb(5,16,110)']]

RdYlGnBu = [[0.00, 'rgb(124, 36, 36)'],
            [0.25, 'rgb(255, 255, 48)'],
            [0.5, 'rgb(76, 145, 33)'],
            [0.85, 'rgb(0, 92, 221)'],
            [1.00, 'rgb(0, 46, 110)']]

colorscales = ['Blackbody', 'Bluered', 'Blues', 'Earth', 'Electric', 'Greens',
               'Greys', 'Hot', 'Jet', 'Picnic', 'Portland', 'Rainbow', 'RdBu',
               'Reds', 'Viridis', 'Default']
color_options = [{'label': c, 'value': c} for c in colorscales]
color_options.append({'label': 'RdWhBu', 'value': 'RdWhBu'})
color_options.append({'label': 'RdYlGnBu', 'value': 'RdYlGnBu'})

# Year Marks for Slider
years = [int(y) for y in range(1948, 2018)]
yearmarks = dict(zip(years, years))
monthmarks = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
for y in yearmarks:
    if y % 5 != 0:
        yearmarks[y] = ""

# Set up initial signal and raster to scatterplot conversion
# A source grid for scatterplot maps - will need more for optional resolution
source = xr.open_dataarray(os.path.join(data_path,
                                        "data/droughtindices/source_array.nc"))

# This converts array coordinates into array positions
londict, latdict, res = functions.coordinateDictionaries(source)

# Map Layout:
# Check this out! https://paulcbauer.shinyapps.io/plotlylayout/
layout = dict(
    autosize=True,
    height=500,
    font=dict(color='#CCCCCC',
              fontweight='bold'),
    titlefont=dict(color='#CCCCCC',
                   size='20',
                   family='Time New Roman',
                   fontweight='bold'),
    margin=dict(
        l=55,
        r=35,
        b=65,
        t=90,
        pad=4),
    hovermode="closest",
    plot_bgcolor="#083C04",
    paper_bgcolor="#0D347C",
    legend=dict(font=dict(size=10, fontweight='bold'), orientation='h'),
    title='<b>Index Values/b>',
    mapbox=dict(
        accesstoken=mapbox_access_token,
        style="satellite-streets",
        center=dict(
            lon=-95.7,
            lat=37.1),
        zoom=2,
    )
)


# In[]: Create a Div maker
def divMaker(id_num, index='noaa'):
    div = html.Div([

                 html.Div([dcc.Dropdown(id='choice_{}'.format(id_num),
                                        options=indices, value=index)],
                          style={'width': '30%'}),
                 dcc.Graph(id='map_{}'.format(id_num)),
                 html.Div([dcc.Graph(id='series_{}'.format(id_num))]),

              ], className='six columns')
    return div


# In[]: Create App Layout
app.layout = html.Div([
        # html.Div([
        #         html.Img(id='banner',
        #                  src=('https://github.com/WilliamsTravis/' +
        #                       'Ubuntu-Practice-Machine/blob/master/images/' +
        #                       'banner1.png?raw=true'),
        #                  style={'width': '100%',
        #                         'box-shadow': '1px 1px 1px 1px black'})]),
        # html.Hr(),
        html.Div([html.H1('Raster to Scatterplot Visualization'),
                  html.Hr()],
                 className='twelve columns',
                 style={'font-weight': 'bolder',
                        'text-align': 'center',
                        'font-size': '50px',
                        'font-family': 'Times New Roman'}),

        # Year Slider
        html.Div(id='options',
                 children=[
                     html.Div([
                     html.H3('Study Period Year Range'),
                     html.Div([dcc.RangeSlider(
                                 id='year_slider',
                                 value=[1985, 2017],
                                 min=1948,
                                 max=2017,
                                 marks=yearmarks)],
                              style={'margin-top': '0',
                                     'margin-bottom': '40'}),

                     # Month Slider
                     html.Div(id='month_slider',
                              children=[
                                      html.H3('Month Range'),
                                      html.Div([
                                               dcc.RangeSlider(id='month',
                                                               value=[1, 12],
                                                               min=1, max=12,
                                                               marks=monthmarks)],
                                               style={'width': '35%'})],
                              style={'display': 'none'},
                              # className="six columns"
                              )
                     ],
                     className="row",
                     style={'margin-bottom': '55'}),

            # Options
            html.Div([
                # Maptype
                html.Div([
                        html.H3("Map Type"),
                         dcc.RadioItems(
                                id="map_type",
                                value="dark",
                                options=maptypes)],
                         className='two columns'),

                # Function
                html.Div([
                         html.H3("Function"),
                         dcc.RadioItems(id='function_choice',
                                        options=function_options,
                                        value='mean_perc')],
                         className='three columns'),

                # Customize Color Scales
                html.Div([
                        html.H3('Color Gradient'),
                        dcc.Dropdown(id='colors',
                                     options=color_options,
                                     value='Default'),
                        html.H4("Reverse"),
                        dcc.RadioItems(id='reverse',
                                       options=[{'label': 'Yes', 
                                                 'value': 'yes'},
                                                {'label': 'No',
                                                 'value': 'no'}],
                                       value='no')],
                         className='two columns')
                ],
               className='row',
               style={'margin-bottom': '50',
                      'margin-top': '0'}),

            # Break
            html.Hr(),
        ]),

        # Toggle Options
        html.Div([
                html.Button(id='submit',
                            children='Submit Options',
                            type='button',
                            title='It updates automatically without this.',
                            style={'background-color':'#3168ce',
                                   'color': 'white',
                                   'margin-right': '20'}),
                html.Button(id='toggle_options',
                            children='Toggle Options: Off',
                            type='button',
                            title='Click to collapse the options above'),
                html.Button(id="click_sync",
                            children="Click Syncing: On",
                            title=("Toggle this on and off to sync the " +
                                    "location of the time series between each" +
                                    "map"),
                            style={'background-color': '#c7d4ea',
                                    'border-radius': '4px'})],
                style={'margin-buttom': '50',}),

        # Break
        html.Br(style={'line-height': '150%'}),

        # Four by Four Map Layout
        # Row 1
        html.Div([divMaker(1, 'pdsi'), divMaker(2, 'spei1')],
                 className='row'),

        # Row 2
        html.Div([divMaker(3, 'spei6'), divMaker(4, 'spi3')],
                 className='row'),

        # Signals
        html.Div(id='signal', style={'display': 'none'}),
        html.Div(id='click_store',
                 # children=['{"points": [{"lon": -107.5, "lat": 40.5}]}'],
                 style={'display': 'none'}),
        html.Div(id='key_1', children='1', style={'display': 'none'}),
        html.Div(id='key_2', children='2', style={'display': 'none'}),
        html.Div(id='key_3', children='3', style={'display': 'none'}),
        html.Div(id='key_4', children='4', style={'display': 'none'}),
        html.Div(id='time_1', style={'display': 'none'}),
        html.Div(id='time_2', style={'display': 'none'}),
        html.Div(id='time_3', style={'display': 'none'}),
        html.Div(id='time_4', style={'display': 'none'}),
        html.Div(id='cache_check_1', style={'display': 'none'}),
        html.Div(id='cache_check_2', style={'display': 'none'}),
        html.Div(id='cache_check_3', style={'display': 'none'}),
        html.Div(id='cache_check_4', style={'display': 'none'}),



        # The end!
        ], className='ten columns offset-by-one')


# In[]: App callbacks
def makeMap(signal, choice):
    '''
    To choose which function to return from Index_Maps
    '''
    gc.collect()

    [time_range, function, colorscale, reverse] = signal

    maps = Index_Maps(time_range, colorscale, reverse, choice)

    if function == "mean_original":
        data = maps.meanOriginal()
    if function == "omax":
        data = maps.maxOriginal()
    if function == "omin":
        data = maps.minOriginal()
    if function == "mean_perc":
        data = maps.meanPercentile()
    if function == "max":
        data = maps.maxPercentile()
    if function == "min":
        data = maps.minPercentile()
    if function == "ocv":
        data = maps.coefficientVariation()
    
    return data


@cache1.memoize
def retrieve_data1(signal, choice):
    return makeMap(signal, choice)


@cache2.memoize
def retrieve_data2(signal, choice):
    return makeMap(signal, choice)


@cache3.memoize
def retrieve_data3(signal, choice):
    return makeMap(signal, choice)


@cache4.memoize
def retrieve_data4(signal, choice):
    return makeMap(signal, choice)


def chooseCache(key, signal, choice):
    if key == '1':
        return retrieve_data1(signal, choice)
    elif key == '2':
        return retrieve_data2(signal, choice)
    elif key == '3':
        return retrieve_data3(signal, choice)
    else:
        return retrieve_data4(signal, choice)


# Store data in the cache and hide the signal to activate it in the hidden div
@app.callback(Output('signal', 'children'),
              [Input('submit', 'n_clicks')],
              [State('function_choice', 'value'),
               State('colors', 'value'),
               State('reverse', 'value'),
               State('year_slider', 'value'),
               State('month', 'value'),
               State('map_type', 'value')])
def submitSignal(click, function, colorscale, reverse, year_range,
                 month_range, map_type):

    if not month_range:
        month_range = [1, 1]
    signal = [[year_range, month_range], function,
                       colorscale, reverse, map_type]
    return json.dumps(signal)

    
# Allow users to select a month range if the year slider is set to one year
@app.callback(Output('month_slider', 'style'),
              [Input('year_slider', 'value')])
def monthSlider(year_range):
    if year_range[0] == year_range[1]:
        style = {}
    else:
        style = {'display': 'none'}
    return style


@app.callback(Output('options', 'style'),
              [Input('toggle_options', 'n_clicks')])
def toggleOptions(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'display': 'none'}
    else:
        style = {}
    return style


@app.callback(Output('toggle_options', 'style'),
              [Input('toggle_options', 'n_clicks')])
def toggleToggleColor(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'background-color': '#a8b3c4',
                  'border-radius': '4px'}
    else:
        style = {'background-color': '#c7d4ea',
                  'border-radius': '4px'}
    return style

@app.callback(Output('toggle_options', 'children'),
              [Input('toggle_options', 'n_clicks')])
def toggleOptionsLabel(click):
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Display Options: Off"
    else:
        children = "Display Options: On"
    return children

@app.callback(Output('click_sync', 'style'),
              [Input('click_sync', 'n_clicks')])
def toggleSyncColor(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'background-color': '#c7d4ea',
                 'border-radius': '4px'}
    else:
        style = {'background-color': '#a8b3c4',
                  'border-radius': '4px'}
    return style


@app.callback(Output('click_sync', 'children'),
              [Input('click_sync', 'n_clicks')])
def toggleSyncLabel(click):
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Click Syncing: On"
    else:
        children = "Click Syncing: Off"
    return children


@app.callback(Output('click_store', 'children'),
              [Input('map_1', 'clickData'),
               Input('map_2', 'clickData'),
               Input('map_3', 'clickData'),
               Input('map_4', 'clickData'),
               Input('time_1', 'children'),
               Input('time_2', 'children'),
               Input('time_3', 'children'),
               Input('time_4', 'children')],
              [State('click_sync', 'children')])
def clickPicker(click1, click2, click3, click4,
                time1, time2, time3, time4,
                click_sync):
    clicks = [click1, click2, click3, click4]
    times = [time1, time2, time3, time4]
    times = [0 if t is None else t for t in times]
    index = times.index(max(times))
    if 'On' in click_sync:
        if not any(c is not None for c in clicks):
            click = {'points': [{'lon': -107.75, 'lat': 40.5}]}
        else:
            click = clicks[index]
        return json.dumps(click)
    else:
        return(json.dumps(clicks))

# In[] For the future
for i in range(1, 5):
    @app.callback(Output('time_{}'.format(i), 'children'),
                  [Input('map_{}'.format(i), 'clickData')])
    def clickTime(click):
        clicktime = time.time()
        return(clicktime)

    @app.callback(Output('cache_check_{}'.format(i), 'children'),
                  [Input('signal', 'children'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('key_{}'.format(i), 'children')])
    def storeData(signal, choice, key):
        signal = json.loads(signal)
        signal.pop(4)
        chooseCache(key, signal, choice)
        print("\nCPU: {}% \nMemory: {}%\n".format(psutil.cpu_percent(),
                                       psutil.virtual_memory().percent))
        key = json.dumps([signal, choice])
        return key


    @app.callback(Output("map_{}".format(i), 'figure'),
                  [Input('cache_check_{}'.format(i), 'children')],
                  [State('key_{}'.format(i), 'children'),
                   State('choice_{}'.format(i), 'value'),
                   State('signal', 'children')])
    def makeGraph(trigger, key, choice, signal):

        print("Rendering Map #{}".format(int(key)))
        # Clear memory space...what's the best way to do this?
        gc.collect()


        # Create signal for the global_store
        signal = json.loads(signal)

        # Collect and adjust signal
        [[year_range, month_range], function, colorscale,
         reverse_override, map_type] = signal
        signal.pop(4)

        # Split the time range up
        y1 = year_range[0]
        y2 = year_range[1]
        m1 = month_range[0]
        m2 = month_range[1]

        # Get data - check which cache first
        print(json.dumps([signal, choice]))
        [[array, arrays, dates],
         colorscale, dmax, dmin, reverse] = chooseCache(key, signal, choice)

        # There's a lot of colorscale switching in the default settings
        if reverse_override == 'yes':
            reverse = not reverse

        # Individual array min/max
        amax = np.nanmax(array)
        amin = np.nanmin(array)

        # Set to this thing
        source.data[0] = array

        # Because EDDI only extends back to 1980
        if 'eddi' in choice and y1 < 1980 and y2 < 1980:
            source.data[0] = na

        # Now all this
        dfs = xr.DataArray(source, name="data")
        pdf = dfs.to_dataframe()
        step = res
        to_bin = lambda x: np.floor(x / step) * step
        pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
        pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
        pdf['gridx'] = pdf['lonbin'].map(londict)
        pdf['gridy'] = pdf['latbin'].map(latdict)

        # For hover information
        grid2 = np.copy(grid)
        grid2[np.isnan(grid2)] = 0
        pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
        # pdf['grid'] = pdf['grid'].apply(int).apply(str)
        pdf = pd.merge(pdf, counties_df, how='inner')
        pdf['data'] = pdf['data'].astype(float).round(3)
        pdf['printdata'] = pdf['place'] + ":<br>     " + pdf['data'].apply(str)

        df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
        df = df_flat[np.isfinite(df_flat['data'])]

        # Create the scattermapbox object
        data = [
            dict(
                type='scattermapbox',
                lon=df['lonbin'],
                lat=df['latbin'],
                text=df['printdata'],
                mode='markers',
                hoverinfo='text',
                hovermode='closest',
                marker=dict(
                    colorscale=colorscale,
                    reversescale=reverse,
                    color=df['data'],
                    cmax=amax,
                    cmin=amin,
                    opacity=0.85,
                    size=5,
                    colorbar=dict(
                        textposition="auto",
                        orientation="h",

                        font=dict(size=15,
                                  fontweight='bold')
                    )
                )
            )]

        if y1 != y2:
            date_print = '{} - {}'.format(y1, y2)
        elif y1 == y2 and m1 != m2:
            date_print = "{} - {}, {}".format(monthmarks[m1],
                                              monthmarks[m2], y1)
        else:
            date_print = "{}, {}".format(monthmarks[m1], y1)

        layout_copy = copy.deepcopy(layout)
        layout_copy['mapbox'] = dict(
            accesstoken=mapbox_access_token,
            style=map_type,
            center=dict(lon=-95.7, lat=37.1),
            zoom=2)

        layout_copy['title'] = (indexnames[choice] + '<br>' +
                                function_names[function] + ': ' +
                                date_print)

        figure = dict(data=data, layout=layout_copy)
        return figure


    @app.callback(Output('series_{}'.format(i), 'figure'),
                  [Input("map_{}".format(i), 'clickData'),
                   Input('click_store', 'children'),
                   Input('signal', 'children'),
                   Input('choice_{}'.format(i), 'value')],
                  [State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children')])
    def makeSeries(single_click, click, signal, choice,  key, sync):
        '''
        Each callback is called even if this isn't synced...It would require
         a whole new set of callbacks to avoid the lag from that. Also, the
         synced click process is too slow...what can be done?
        '''

        # Create signal for the global_store
        signal = json.loads(signal) 
        # [[year_range, month_range], function, colorscale, reverse, map_type, click_sync]

        # Collect signals
        [[year_range, month_range], function, colorscale,
         reverse_override, map_type] = signal
        signal.pop(4)

        # [[year_range, month_range], function, colorscale, reverse, map_type, click_sync, 'pdsi']

        # Get data - check which cache first
        print(json.dumps([signal, choice]))
        [[array, arrays, dates],
         colorscale, dmax, dmin, reverse] = chooseCache(key, signal, choice)

        # There's a lot of colorscale switching in the default settings
        if reverse_override == 'yes':
            reverse = not reverse

        #  Check if we are syncing clicks
        click = json.loads(click)  
        if 'On' in sync:
            click=click
        else:
            index = int(key) - 1
            if single_click is None:
                click = click[index]
                # click = {"points": [{"lon": -107.5, "lat": 40.5}]}
            elif single_click is not None:
                click = single_click
      
        if click is None:
            raise PreventUpdate

        lon = click['points'][0]['lon']
        lat = click['points'][0]['lat']
        x = londict[lon]
        y = latdict[lat]
        gridid = grid[y, x]
        county = counties_df['place'][counties_df.grid == gridid].unique()
        print("Click: " + county)

        # There are often more than one county, sometimes none in this df
        if len(county) == 0:
            county = ""
        else:
            county = county[0]

        # Get time series
        dates = [pd.to_datetime(str(d)) for d in dates]
        dates = [d.strftime('%Y-%m') for d in dates]
        timeseries = np.array([round(a[y, x], 4) for a in arrays])
        yaxis=dict(range=[dmin, dmax])

        # Build the data dictionaries that plotly reads
        data = [
            dict(
                type='bar',
                x=dates,
                y=timeseries,
                marker=dict(color=timeseries,
                            colorscale=colorscale,
                            reversescale=reverse,
                            line=dict(width=0.2, color="#000000")),
            )]

        # Copy and customize Layout
        layout_copy = copy.deepcopy(layout)
        layout_copy['title'] = ("Time Series - Individual Observations" +
                                "<Br>" + county)
        layout_copy['plot_bgcolor'] = "white"
        layout_copy['paper_bgcolor'] = "white"
        layout_copy['height'] = 250
        layout_copy['yaxis'] = yaxis
        layout_copy['hovermode'] = 'closest',
        layout_copy['titlefont']['color'] = '#636363'
        layout_copy['font']['color'] = '#636363'
        figure = dict(data=data, layout=layout_copy)

        return figure

# In[]
# @app.callback(Output('banner', 'src'),
#               [Input('choice_1', 'value')])
# def whichBanner(value):
#     # which banner?
#     time_modulo = round(time.time()) % 5
#     print(str(time_modulo))
#     banners = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
#     image_time = banners[time_modulo]
#     image = ('https://github.com/WilliamsTravis/' +
#              'Ubuntu-Practice-Machine/blob/master/images/' +
#              'banner' + str(image_time) + '.png?raw=true')
#     return image


# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()
