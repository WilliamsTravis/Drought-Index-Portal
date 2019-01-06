# -*- coding: utf-8 -*-
"""
Just an app to visualize raster time series.

Created on Fri Jan  4 12:39:23 2019

@author: User
"""

# In[] Functions and Libraries
import copy
import dash
from dash.dependencies import Input, Output, State, Event
import dash_core_components as dcc
import dash_html_components as html
import datetime as dt
import gc
import gdal
import glob
import json
from flask import Flask
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import numpy.ma as ma
from collections import OrderedDict
import os
import pandas as pd
import plotly
import re
from textwrap import dedent
import time
from tqdm import tqdm
import xarray as xr
from sys import platform
import warnings
# warnings.filterwarnings("ignore")

# Work for Windows and Linux
if platform == 'win32':
    home_path = 'c:/users/user/github'
    data_path = 'd:/'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
    from flask_cache import Cache  # This one works on Windows but not Linux
    startyear = 1948
else:
    home_path = '/home/ubuntu'  # Not sure yet
    os.chdir(os.path.join(home_path, 'Ubuntu-Practie-Machine'))
    data = '/home/ubunutu'
    from flask_caching import Cache  # This works on Linux but not Windows :)
    startyear = 1980

from functions import indexHist
from functions import npzIn
from functions import calculateCV

# In[] Create the DASH App object
app = dash.Dash(__name__)

# Go to stylesheet, styled after a DASH example (how to serve locally?)
app.css.append_css({'external_url': 'https://codepen.io/williamstravis/pen/' +
                                    'maxwvK.css'})

# Create Server Object
server = app.server

# Create and initialize a cache for data storage
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(server)

# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')
def makeMap(function, choice, year_range):
    # Get numpy arrays
    if function != 'cv':
        array_path = os.path.join(data_path,
                                  "data/droughtindices/npz/percentiles",
                                  choice + '_arrays.npz')
        date_path = os.path.join(data_path,
                                 "data/droughtindices/npz/percentiles",
                                 choice + '_dates.npz')
        indexlist = npzIn(array_path, date_path)

        # Get total Min and Max Values for colors
        dmin = np.nanmin([i[1] for i in indexlist])
        dmax = np.nanmax([i[1] for i in indexlist])

        # filter by year
        indexlist = [a for a in indexlist if
                     int(a[0][-6:-2]) >= year_range[0] and
                     int(a[0][-6:-2]) <= year_range[1]]
        arrays = [i[1] for i in indexlist]

        # Apply chosen funtion
        if function == 'mean_perc':
            array = np.nanmean(arrays, axis=0)
        elif function == 'max':
            array = np.nanmax(arrays, axis=0)
        else:
            array = np.nanmin(arrays, axis=0)

        # Colors - RdYlGnBu
        colorscale = [[0.00, 'rgb(197, 90, 58)'],
                      [0.25, 'rgb(255, 255, 48)'],
                      [0.50, 'rgb(39, 147, 57)'],
                      # [0.75, 'rgb(6, 104, 70)'],
                      [1.00, 'rgb(1, 62, 110)']]

    else:
        array_path = os.path.join(data_path,
                                  "data/droughtindices/npz",
                                  choice + '_arrays.npz')
        date_path = os.path.join(data_path,
                                 "data/droughtindices/npz",
                                 choice + '_dates.npz')
        indexlist = npzIn(array_path, date_path)

        # Get total Min and Max Values for colors
        dmin = 0
        dmax = 1

        # filter by year
        indexlist = [a for a in indexlist if
                     int(a[0][-6:-2]) >= year_range[0] and
                     int(a[0][-6:-2]) <= year_range[1]]
        arrays = [i[1] for i in indexlist]

        # Apply chosen funtion
        array = calculateCV(arrays)

        # Colors - RdYlGnBu
        colorscale = [[0.00, 'rgb(1, 62, 110)'],
                      [0.35, 'rgb(6, 104, 70)'],
                      [0.45, 'rgb(39, 147, 57)'],
                      [0.55, 'rgb(255, 255, 48)'],
                      [1.00, 'rgb(197, 90, 58)']]

    return [[array, indexlist], colorscale, dmax, dmin]
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
                    {'label': 'Coefficient of Variation - Original Values',
                     'value': 'cv'},
                    {'label': 'Maximum - Percentiles', 'value': 'max'},
                    {'label': 'Minimum - Percentiles', 'value': 'min'}]
function_names = {'mean_perc': 'Average Percentiles',
                  'cv': 'Coefficient of Variation using Original Index Values',
                  'min': 'Minimum Percentile',
                  'max': 'Maxmium Percentile'}

# In[] The map
# Map types
maptypes = [{'label': 'Light', 'value': 'light'},
            {'label': 'Dark', 'value': 'dark'},
            {'label': 'Basic', 'value': 'basic'},
            {'label': 'Outdoors', 'value': 'outdoors'},
            {'label': 'Satellite', 'value': 'satellite'},
            {'label': 'Satellite Streets', 'value': 'satellite-streets'}]

# Year Marks for Slider
years = [int(y) for y in range(startyear, 2018)]
yearmarks = dict(zip(years, years))
for y in yearmarks:
    if y % 5 != 0:
        yearmarks[y] = ""

# Set up initial signal and raster to scatterplot conversion
# A source grid for scatterplot maps - will need more for optional resolution
source = xr.open_dataarray(os.path.join(data_path,
                                        "data/droughtindices/source_array.nc"))

# Create Coordinate index positions from xarray
# Geometry
x_length = source.shape[2]
y_length = source.shape[1]
res = source.res[0]  
lon_min = source.transform[0]
lat_max = source.transform[3] - res

# Make dictionaires with coordinates and array index positions
xs = range(x_length)
ys = range(y_length)
lons = [lon_min + res*x for x in xs]
lats = [lat_max - res*y for y in ys]
londict = dict(zip(lons, xs))
latdict = dict(zip(lats, ys))
londict2 = {y: x for x, y in londict.items()}
latdict2 = {y: x for x, y in latdict.items()}

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
        pad=4
    ),
    hovermode="closest",
    plot_bgcolor="#083C04",
    paper_bgcolor="#0D347C",
    legend=dict(font=dict(size=10, fontweight='bold'), orientation='h'),
    title='<b>Potential Payout Frequencies</b>',
    mapbox=dict(
        accesstoken=mapbox_access_token,
        style="satellite-streets",
        center=dict(
            lon=-95.7,
            lat=37.1
        ),
        zoom=2,
    )
)


# In[]: Create a Div maker
def divMaker(id_num, index='noaa'):
    div = html.Div([
              html.Div([
                       dcc.Dropdown(id='choice_{}'.format(id_num),
                                    options=indices,
                                    value=index)],
                       style={'width': '30%',
                              'margin-top': 20},
                       className='row'),

                dcc.Graph(id='map_{}'.format(id_num)),

                html.Div([dcc.Graph(id='series_{}'.format(id_num),
                                    style={'margin-top': 15,
                                           'margin-bottom': 50,
                                           'height': '150'})],
                         className='six columns')],
                className='six columns',
                style={'float': 'left',
                       'margin-top': '40'})
    return div


# In[]: Create App Layout
app.layout = html.Div([
        html.Div([html.Img(id='banner',
                           src=('https://github.com/WilliamsTravis/' +
                                'Ubuntu-Practice-Machine/blob/master/images/' +
                                'banner1.png?raw=true'),
                 style={'width': '100%',
                        'box-shadow': '1px 1px 1px 1px black'})]),
        html.Hr(),
        html.Div([html.H1('Raster to Scatterplot Visualization')],
                 className='twelve columns',
                 style={'font-weight': 'bold',
                        'text-align': 'center',
                        'font-family': 'Times New Roman'}),

        # Year Slider
        html.Div([
                 html.Hr(),
                 html.P('Study Period Year Range'),
                 dcc.RangeSlider(
                     id='year_slider',
                     value=[2017, 2017],
                     min=startyear,
                     max=2017,
                     marks=yearmarks)],
                 className="twelve columns",
                 style={'margin-top': '0',
                        'margin-bottom': '40'}),
        # Options
        html.Div([        
            # Maptype
            html.Div([
                    html.P("Map Type"),
                    dcc.Dropdown(
                            id="map_type",
                            value="light",
                            options=maptypes,
                            multi=False)],
                    className='two columns'),

           # Function 
           html.Div([
                   html.P("Function"),
                   dcc.Dropdown(id='function_choice',
                                options=function_options,
                                value='mean_perc')],
                    className='four columns')],
                className='row'),

        # Four by Four Map Layout
        # Row 1
        html.Div([divMaker(1, 'noaa'),
                  divMaker(2, 'pdsi')],
                 className='row'),
        
        # I need a gap!
        html.Div([html.P("")],
                  className='row'),

        # Row 2
        html.Div([divMaker(3, 'spi1'),
                  divMaker(4, 'spei1')],
                 className='row'),

        # Signals
        html.Div(id='signal_store',
                 style={'display': 'none'}),
        html.Div(id='click_store',
                 style={'display': 'hidden'})

        # The end!
        ], className='ten columns offset-by-one')


# In[]: App callbacks
@cache.memoize()
def global_store(signal):
    # Dejsonify the signal
    signal = json.loads(signal)

    # get individual signals
    choices = [signal[0], signal[1], signal[2], signal[3]]
    fun = signal[4]
    year_range = signal[5]

    # Clear memory space...what's the best way to do this?
    gc.collect()

    # Make one map
    def makeMap(function, choice, year_range):
        # Get numpy arrays
        if function != 'cv':
            array_path = os.path.join(data_path,
                                      "data/droughtindices/npz/percentiles",
                                      choice + '_arrays.npz')
            date_path = os.path.join(data_path,
                                     "data/droughtindices/npz/percentiles",
                                     choice + '_dates.npz')
            indexlist = npzIn(array_path, date_path)

            # Get total Min and Max Values for colors
            dmin = np.nanmin([i[1] for i in indexlist])
            dmax = np.nanmax([i[1] for i in indexlist])

            # filter by year
            indexlist = [a for a in indexlist if
                         int(a[0][-6:-2]) >= year_range[0] and
                         int(a[0][-6:-2]) <= year_range[1]]
            arrays = [i[1] for i in indexlist]

            # Apply chosen funtion
            if function == 'mean_perc':
                array = np.nanmean(arrays, axis=0)
            elif function == 'max':
                array = np.nanmax(arrays, axis=0)
            else:
                array = np.nanmin(arrays, axis=0)

            # Colors - RdYlGnBu
            colorscale = [[0.00, 'rgb(197, 90, 58)'],
                          [0.25, 'rgb(255, 255, 48)'],
                          [0.50, 'rgb(39, 147, 57)'],
                          # [0.75, 'rgb(6, 104, 70)'],
                          [1.00, 'rgb(1, 62, 110)']]

        else:
            array_path = os.path.join(data_path,
                                      "data/droughtindices/npz",
                                      choice + '_arrays.npz')
            date_path = os.path.join(data_path,
                                     "data/droughtindices/npz",
                                     choice + '_dates.npz')
            indexlist = npzIn(array_path, date_path)

            # Get total Min and Max Values for colors
            dmin = 0
            dmax = 1

            # filter by year
            indexlist = [a for a in indexlist if
                         int(a[0][-6:-2]) >= year_range[0] and
                         int(a[0][-6:-2]) <= year_range[1]]
            arrays = [i[1] for i in indexlist]

            # Apply chosen funtion
            array = calculateCV(arrays)

            # Colors - RdYlGnBu
            colorscale = [[0.00, 'rgb(1, 62, 110)'],
                          [0.35, 'rgb(6, 104, 70)'],
                          [0.45, 'rgb(39, 147, 57)'],
                          [0.55, 'rgb(255, 255, 48)'],
                          [1.00, 'rgb(197, 90, 58)']]

        return [[array, indexlist], colorscale, dmax, dmin]

    data = {choice: makeMap(fun, choice, year_range) for choice in choices}

    return data


def retrieve_data(signal):
    data = global_store(signal)
    return data

@app.callback(Output('signal_store', 'children'),
              [Input('choice_1', 'value'),
               Input('choice_2', 'value'),
               Input('choice_3', 'value'),
               Input('choice_4', 'value'),
               Input('function_choice', 'value'),
               Input('year_slider', 'value')])
def submitSignal(choice1, choice2, choice3, choice4, function, year_range):

    return json.dumps([choice1, choice2, choice3, choice4,
                       function, year_range])

@app.callback(Output('click_store', 'children'),
              [Input('map_1', 'clickData'),
              Input('map_2', 'clickData'),
              Input('map_3', 'clickData'),
              Input('map_4', 'clickData')])
def clickPicker(click1, click2, click3, click4):
    clicks = [click1, click2, click3, click4]
    # if not any(c is not None for c in  clicks):
    #     coords = [50, 50]
    return json.dumps(clicks)

for i in range(1, 5):
    @app.callback(Output("map_{}".format(i), 'figure'),
                  [Input('signal_store', 'children'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('function_choice', 'value'),
                   Input('year_slider', 'value'),
                   Input('map_type', 'value')])
    def makeGraph(signal, choice, function, year_range, map_type):
        # Clear memory space...what's the best way to do this?
        gc.collect()

        # Collect signal and choose appropriate choice
        # data = retrieve_data(signal)
            # Make one map


        data = makeMap(function, choice, year_range)
        # data = data[choice]
        maps = data[0]
        array = maps[0]
        colorscale = data[1]
        dmax = data[2]
        dmin = data[3]

        # get coordinate-array index dictionaries data!
        source.data[0] = array

        # Now all this
        dfs = xr.DataArray(source, name="data")
        pdf = dfs.to_dataframe()
        step = res
        to_bin = lambda x: np.floor(x / step) * step
        pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
        pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
        pdf['gridx'] = pdf['lonbin'].map(londict)
        pdf['gridy'] = pdf['latbin'].map(latdict)
        # grid2 = np.copy(grid)
        # grid2[np.isnan(grid2)] = 0
        # pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
        # pdf['grid'] = pdf['grid'].apply(int).apply(str)
        # pdf['data'] = pdf['data'].astype(float).round(3)
        # pdf['printdata'] = "GRID #: " + pdf['grid'] + "<br>Data: " + pdf['data'].apply(str)

        df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
        df = df_flat[np.isfinite(df_flat['data'])]

        # Create the scattermapbox object
        data = [
            dict(
                type='scattermapbox',
                lon=df['lonbin'],
                lat=df['latbin'],
                text=df['data'],
                mode='markers',
                hoverinfo='text',
                marker=dict(
                    colorscale=colorscale,
                    cmin=dmin,
                    color=df['data'],
                    cmax=dmax,
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

        if year_range[0] != year_range[1]:
            year_print = '{} - {}'.format(year_range[0], year_range[1])
        else:
            year_print = str(year_range[0])
            
        layout_copy = copy.deepcopy(layout)
        layout_copy['mapbox'] = dict(
            accesstoken=mapbox_access_token,
            style=map_type,
            center=dict(lon=-95.7, lat=37.1),
            zoom=2)

        layout_copy['title'] = (indexnames[choice] + '<br>' +
                               function_names[function] + ', ' +
                               year_print)

        figure = dict(data=data, layout=layout_copy)
        return figure

    @app.callback(Output('series_{}'.format(i), 'figure'),
                  [Input("map_{}".format(i), 'clickData'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('signal_store', 'children'),
                   Input('year_slider', 'value'),
                   Input('function_choice', 'value')])
    def makeSeries(click, choice, signal, year_range, function):
        # Get data
        # data = retrieve_data(signal)
        data = makeMap(function, choice, year_range)
        # data = data[choice]
        indexlist = data[0][1]
        arrays = [i[1] for i in indexlist]

        # find coordinates
        if click is None:
            x = londict[-100]
            y = latdict[40]
        else:
            lon = click['points'][0]['lon']
            lat = click['points'][0]['lat']
            x = londict[lon]
            y = latdict[lat]

        # Get time series
        timeseries = [a[y, x] for a in arrays]
        dates = [i[0][-6:] for i in indexlist]

        # Convert dates to datetime
        dates2 = [dt.datetime(int(d[:4]), int(d[4:]), day=1) for d in dates]

        data = [
            dict(
                type='bar',
                # marker = dict(color='blue', line=dict(width=3.5,
                #                                       color="#000000")),
                # yaxis=dict(range = [0,100]),
                x=dates2,
                y=timeseries
            )]

        # Change Layout
        layout_copy = copy.deepcopy(layout)
        layout_copy['title'] = "Time Series"
        layout_copy['plot_bgcolor'] ="white"
        layout_copy['paper_bgcolor'] ="white"

        figure = dict(data=data, layout=layout_copy)

        return figure


# In[]
@app.callback(Output('banner', 'src'),
              [Input('choice_1', 'value')])
def whichBanner(value):
    # which banner?
    time_modulo = round(time.time()) % 5
    print(str(time_modulo))
    banners = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
    image_time = banners[time_modulo]
    image = ('https://github.com/WilliamsTravis/' +
             'Ubuntu-Practice-Machine/blob/master/images/' +
             'banner' + str(image_time) + '.png?raw=true')
    return image


# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()
