# -*- coding: utf-8 -*-
"""
Rebuilding Index Maps and retrieveData to improve efficiency.

Created on Mon Apr 29 10:53:59 2019

@author: User
"""



# Functions and Libraries
import netCDF4  # Leave this, without it there are problems in Linux
import base64
import copy
from collections import OrderedDict
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import datetime as dt
import fiona
from flask_caching import Cache
import gc
import geopandas as gpd
from inspect import currentframe, getframeinfo
import json
import numpy as np
import os
from osgeo import gdal, osr
import pandas as pd
import psutil
import sys
import urllib
import warnings
import xarray as xr

# Set Working Directory
sys.path.insert(0, 'c:/users/user/github/ubuntu-practice-machine')

# Import functions and classes
from functions2 import Admin_Elements, areaSeries, correlationField, datePrint
from functions2 import droughtArea, Index_Maps, Location_Builder
from functions2 import shapeReproject, xMask

# A sample signal
signal = [[[2000, 2019], [1, 12], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]],
          'Default', 'no']

# Retrieve signal elements
time_data = signal[0]
colorscale = signal[1]
reverse = signal[2]
choice = 'pdsi'
choice_type = 'original'  # Could also be percentiles or projected
function = 'omean'
location = ['grids', '[10, 11, 11, 11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12]', 
            '[243, 242, 243, 244, 245, 246, 247, 241, 242, 243, 244, 245, 246, 247, 248]',
            'Aroostook County, ME to Aroostook County, ME', 2]

# Ultimately I want to return a single object with:
    # 1) a single aggregated array
    # 2) a 3d dask array
    # 3) a colorscale with defaults depending on choice_type
    # 4) dates
    # 5) min and max values

# The only time we need to rebuild the dataset is if the index choice changes
# Retrieve data object
data = Index_Maps(choice, choice_type, time_data, colorscale)

# Now I want to set a mask based on an admin mask...starting with states
admin = Admin_Elements(0.25)
[state_array, county_array, grid, mask,
 source, albers_source, crdict, admin_df] = admin.getElements()

# Okay, now I want to use that mask to get a time series of aggregate values
data.getSeries(location, crdict)
