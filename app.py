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
else:
    home_path = '/home/ubuntu'  # Not sure yet
    os.chdir(os.path.join(home_path, 'Ubuntu-Practie-Machine'))
    data = '/home/ubunutu'
    from flask_caching import Cache  # This works on Linux but not Windows :)

# In[] Create the DASH App object
app = dash.Dash(__name__)

# Go to stylesheet, styled after a DASH example (how to serve locally?)
app.css.append_css({'external_url': 'https://rawgit.com/WilliamsTravis/' +
                    'PRF-USDM/master/dash-stylesheet.css'})

# Create Server Object
server = app.server

# Create and initialize a cache for data storage
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(server)

# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')

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

# Set up initial signal and raster to scatterplot conversion
# A source grid for scatterplot maps - will need more for optional resolution
source = xr.open_dataarray(os.path.join(home_path, "data/source_array.nc"))


# Create Coordinate index positions from xarray
def convertCoords(source):
    # Geometry
    x_length = source.shape[2]
    y_length = source.shape[1]
    resolution = source.res[0]
    lon_min = source.transform[0]
    lat_max = source.transform[3] - resolution

    # Make dictionaires with coordinates and array index positions
    xs = range(x_length)
    ys = range(y_length)
    lons = [lon_min + resolution*x for x in xs]
    lats = [lat_max - resolution*y for y in ys]
    londict = dict(zip(lons, xs))
    latdict = dict(zip(lats, ys))
    londict2 = {y: x for x, y in londict.items()}
    latdict2 = {y: x for x, y in latdict.items()}

    return [londict, latdict, londict2, latdict2]


londict, latdict, londict2, latdict2 = convertCoords(source)

# Map Layout:
# Check this out! https://paulcbauer.shinyapps.io/plotlylayout/
layout = dict(
    autosize=True,
    height=500,
    font=dict(color='#CCCCCC'),
    titlefont=dict(color='#CCCCCC', size='20'),
    margin=dict(
        l=55,
        r=35,
        b=65,
        t=95,
        pad=4
    ),
    hovermode="closest",
    plot_bgcolor="#eee",
    paper_bgcolor="#083C04",
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
        html.Div([
                html.Img(src='images/banner2.png'),
                html.H1('Raster to Scatterplot Visualization',
                        className='twelve columns',
                        style={'font-weight': 'bold',
                               'text-align': 'center'})
                ]),
        ],
    className='ten columns offset-by-one'
    )

# In[]:

# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()




