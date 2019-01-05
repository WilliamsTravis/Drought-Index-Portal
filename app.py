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
import dash_table_experiments as dt
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

from functions import npzIn

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

# which banner?
time_modulo = round(time.time())%5
banners = {0: 1, 1:2, 2:3, 3:4, 4:5}
image_time = banners[time_modulo]

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
    font=dict(color='#CCCCCC'),
    titlefont=dict(color='#DD7D24', size='20'),
    margin=dict(
        l=55,
        r=35,
        b=65,
        t=95,
        pad=4
    ),
    hovermode="closest",
    plot_bgcolor="#083C04",
    paper_bgcolor="#0D347C",
    legend=dict(font=dict(size=10), orientation='h'),
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

# In[]: Create App Layout
app.layout = html.Div([
        html.Div([html.Img(src=('https://github.com/WilliamsTravis/' +
                                'Ubuntu-Practice-Machine/blob/master/images/' +
                                'banner' + str(image_time) + '.png?raw=true'),
                  style={'width': '100%',
                         'box-shadow': '1px 1px 1px 1px black'})]),
        html.Hr(),
        html.Div([html.H1('Raster to Scatterplot Visualization')],
                 className='twelve columns',
                 style={'font-weight': 'bold',
                        'text-align': 'center',
                        'font-family': 'Bookman Old Style'}),
        

        # Year Slider
        html.Div([
                 html.Hr(),
                 html.P('Study Period Year Range'),
                 dcc.RangeSlider(
                     id='year_slider',
                     value=[startyear, 2017],
                     min=startyear,
                     max=2017,
                     marks=yearmarks)],
                 className="twelve columns",
                 style={'margin-top': '0',
                        'margin-bottom': '40'}),

        # Four by Four Map Layout
        # Row 1
        html.Div([
                 html.Div([
                          html.Div([
                                   dcc.Dropdown(id='choice_1',
                                                options=indices,
                                                value='pdsi')],
                                   style={'width': '35%'}),
                          dcc.Graph(id='map_1')],
                          className='six columns',
                          style={'float': 'left',
                                 'margin-top': '40'}),
                 html.Div([
                          html.Div([
                                   dcc.Dropdown(id='choice_2',
                                                options=indices,
                                                value='noaa')],
                                   style={'width': '35%'}),
                          dcc.Graph(id='map_2')],
                          className='six columns',
                          style={'float': 'right',
                                 'margin-top': '40'})],
                 className='row'),

        # Row 2
        html.Div([
                 html.Div([
                          html.Div([
                                   dcc.Dropdown(id='choice_3',
                                                options=indices,
                                                value='noaa')],
                                   style={'width': '35%'}),
                          dcc.Graph(id='map_3')],
                          className='six columns',
                          style={'float': 'left',
                                 'margin-top': '40'}),
                 html.Div([
                          html.Div([
                                   dcc.Dropdown(id='choice_4',
                                                options=indices,
                                                value='noaa')],
                                   style={'width': '35%'}),
                          dcc.Graph(id='map_4')],
                          className='six columns',
                          style={'float': 'right',
                                 'margin-top': '40'})],
                 className='row'),
    # The end!
        ],
    className='ten columns offset-by-one')


# In[]: App callbacks
@app.callback(Output('map_1', 'figure'),
              [Input('choice_1', 'value'),
               Input('year_slider', 'value')])
def makeMap1(choice, years):
    # Clear memory space...what's the best way to do this?
    gc.collect()

    # Get numpy arrays
    array_path = os.path.join(data_path, "data/droughtindices/npz",
                              choice + '_arrays.npz')
    date_path = os.path.join(data_path, "data/droughtindices/npz", 
                              choice + '_dates.npz')
    indexlist = npzIn(array_path, date_path)

    # filter by year
    indexlist = [a for a in indexlist if int(a[0][-6:-2]) >= years[0] and
              int(a[0][-6:-2]) <= years[1]]

    # Apply chosen funtion
    arrays = [i[1] for i in indexlist]
    array = np.nanmean(arrays, axis=0)

    # get coordinate-array index dictionaries data!
    source.data[0] = array

    # Now all this
    dfs = xr.DataArray(source, name = "data")
    pdf = dfs.to_dataframe()
    step = res
    to_bin = lambda x: np.floor(x / step) * step
    pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
    pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
    pdf['gridx']= pdf['lonbin'].map(londict)
    pdf['gridy']= pdf['latbin'].map(latdict)
    # grid2 = np.copy(grid)
    # grid2[np.isnan(grid2)] = 0
    # pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
    # pdf['grid'] = pdf['grid'].apply(int).apply(str)
    # pdf['data'] = pdf['data'].astype(float).round(3)
    # pdf['printdata'] = "GRID #: " + pdf['grid'] + "<br>Data: " + pdf['data'].apply(str)

    df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
    df = df_flat[np.isfinite(df_flat['data'])]

    # Colors 
    # Split the range into 6 numbers from min to max
    dmin = np.nanmin(pdf.data)
    dmax = np.nanmax(pdf.data)
    tick = abs((dmin - dmax) / 6)
    ticks = [dmin + tick*i for i in range(7)]
    colorscale = [[ticks[0], 'rgb(68, 13, 84)'],
                  [ticks[1], 'rgb(47, 107, 142)'],
                  [ticks[2], 'rgb(32, 164, 134)'],
                  [ticks[3], 'rgb(255, 239, 71)'],
                  [ticks[4], 'rgb(229, 211, 13)'],
                  [ticks[5], 'rgb(252, 63, 0)'],
                  [ticks[6], 'rgb(140, 35, 0)']]
    
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
                font=dict(size=15)
                )
            )
        )]
    figure = dict(data=data, layout=layout)
    return figure

# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()
