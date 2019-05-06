# -*- coding: utf-8 -*-
"""
Created on Mon May  6 10:42:35 2019

@author: User
"""

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
from functions2 import Admin_Elements, Cacher, Index_Maps

# Parameters
admin = Admin_Elements(0.25)
[state_array, county_array, grid, mask,
 source, albers_source, crdict, admin_df] = admin.getElements()
signal = [[[2008, 2017], [1, 12], [5, 6, 7, 8]], 'Viridis', 'no']
time_data = signal[0]
colorscale = signal[1]
choice = 'pdsi'
function = 'oarea'
choice_type =  'area'
location = ['all', 'y', 'x', 'Contiguous United States', 0]

# Map class
maps = Index_Maps(choice, choice_type, time_data, colorscale)
maps.setMask(location, crdict)

aress2 = maps.getArea()
maps.setMask(location, crdict)
aress1 = maps.getArea()

