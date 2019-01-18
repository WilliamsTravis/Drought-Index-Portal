# -*- coding: utf-8 -*-
"""
Created on Fri Jan 18 09:18:52 2019

@author: User
"""

# In[] Functions and Libraries
import copy
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import datetime as dt
import gc
import json
from flask_caching import Cache
import numpy as np
import os
import pandas as pd
import psutil
import time
import xarray as xr
import sys
from sys import platform
import warnings
warnings.filterwarnings("ignore")

# Work for Windows and Linux
if platform == 'win32':
    home_path = 'c:/users/user/github'
    data_path = 'd:/'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
    startyear = 1948
else:
    home_path = '/root'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
    data_path = '/root'
    startyear = 1948

from functions import calculateCV
grid = np.load(data_path + "/data/prfgrid.npz")["grid"]
mask = grid*0+1
signal = [[[2000, 2017], [1, 12]], 'mean_perc',
          'Viridis', 'no', 'pdsi']

# In[] Create Cache
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

# Create and initialize a cache for data storage
# cache = Cache(config={'CACHE_TYPE': 'memcached',
                    #  'CACHE_MEMCACHED_SERVERS': ['127.0.0.1:8000']})

cache = Cache(config={'CACHE_TYPE': 'filesystem',
                      'CACHE_DIR': 'cache-directory'})
timeout = 200
cache.init_app(server)

# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')

# In[] Cache Functions
@cache.memoize(timeout=50)
def global_store1(signal):
    gc.collect()
    data = makeMap(signal[0], signal[1], signal[2], signal[3], signal[4])
    return data


def retrieve_data1(signal):
    # cache.delete_memoized(global_store1)
    # cache.clear()
    data = global_store1(signal)
    return data


def retrieve_time1(signal):
    data = global_store1(signal)
    return data

# In a function that return a large dataset
# Stand in function. I will create a simpler class out of this...
def makeMap(time_range, function, colorscale, reverse, choice):    
    # time_range, function, colorscale, reverse_override, choice
    # Split time range up
    year_range = time_range[0]
    month_range = time_range[1]
    y1 = year_range[0]
    y2 = year_range[1]
    if y1 == y2:
        m1 = month_range[0]
        m2 = month_range[1]
    else:
        m1 = 1
        m2 = 12

    # Get numpy arrays
    if function not in ['mean_original', 'omin', 'omax', 'ocv']:
        array_path = os.path.join(
                data_path, "data/droughtindices/netcdfs/percentiles",
                choice + '.nc')
        indexlist = xr.open_dataset(array_path)

        # Get total Min and Max Values for colors
        dmin = 0
        dmax = 1

        # filter by date
        d1 = dt.datetime(y1, m1, 1)
        d2 = dt.datetime(y2, m2, 1)
        arrays = indexlist.sel(time=slice(d1, d2))

        # Apply chosen funtion
        if function == 'mean_perc':
            data = arrays.mean('time')
            array = data.value.data
            array[array == 0] = np.nan
            array = array*mask
        elif function == 'max':
            data = arrays.max('time')
            array = data.value.data
            array[array == 0] = np.nan
            array = array*mask
        else:
            data = arrays.min('time')
            array = data.value.data
            array[array == 0] = np.nan
            array = array*mask

        # Colors - Default is USDM style, sort of
        if colorscale == 'Default':
            colorscale = RdWhBu

        if 'eddi' in choice:
            reverse = True
        else:
            reverse = False

    else:  # Using original values
        array_path = os.path.join(
                data_path, "data/droughtindices/netcdfs",
                choice + '.nc')

        indexlist = xr.open_dataset(array_path)

        # Get total Min and Max Values for colors
        values = indexlist.value.data
        values[values == 0] = np.nan
        limits = [abs(np.nanmin(values)), abs(np.nanmax(values))]
        dmax = max(limits)
        dmin = dmax*-1

        # Filter by Date
        d1 = dt.datetime(y1, m1, 1)
        d2 = dt.datetime(y2, m2, 1)
        arrays = indexlist.sel(time=slice(d1, d2))

        # Apply chosen funtion
        if function == 'mean_original':
            data = arrays.mean('time')
            array = data.value.data
            array = array*mask
            if colorscale == 'Default':
                colorscale = RdYlGnBu
            if 'eddi' in choice:
                reverse = True
            else:
                reverse = False
        elif function == 'omax':
            data = arrays.max('time')
            array = data.value.data
            array[array == 0] = np.nan
            array = array*mask
            if colorscale == 'Default':
                colorscale = RdYlGnBu
            if 'eddi' in choice:
                reverse = True
            else:
                reverse = False
        elif function == 'omin':
            data = arrays.min('time')
            array = data.value.data
            array[array == 0] = np.nan
            array = array*mask
            if colorscale == 'Default':
                colorscale = RdYlGnBu
            if 'eddi' in choice:
                reverse = True
            else:
                reverse = False
        elif function == 'ocv':
            numpy_arrays = arrays.value.data
            array = calculateCV(numpy_arrays)
            array = array*mask
            if colorscale == 'Default':
                colorscale = 'Portland'
            reverse = False

    # With an object as a value the label is left blank? Not sure why?
    if colorscale == 'RdWhBu':
        colorscale = RdWhBu
    if colorscale == 'RdYlGnBu':
        colorscale = RdYlGnBu

    dates = arrays.time.data
    arrays = arrays.value.data
    return [[array, arrays, dates], colorscale, dmax, dmin, reverse]

# In[]: diagnostic functions
# Check Memory
def cm():
    print("\nCPU: {}% \nMemory: {}%\n".format(psutil.cpu_percent(),
                                        psutil.virtual_memory().percent))

# Set up some cached information
x = retrieve_time1(signal)

# In[]: What we'll see in Linux
print('''
      Functions to test:
      retrieve_data1(signal)
      retrieve_time1(signal)
      global_store1(signal)
      
      print("CPU: {}% Memory: {}%".format(psutil.cpu_percent(), psutil.virtual_memorsy().percent))
      ''')


# exec(open("/root/Ubuntu-Practice-Machine/scripts/Cache_Troubleshooting.py").read())