# -*- coding: utf-8 -*-
"""
defining area in drought by severity categories


Created on Thu Feb 21 15:06:57 2019

@author: User
"""
import os
import sys
import copy
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
from flask_caching import Cache
import gc
from inspect import currentframe, getframeinfo
import json
import pandas as pd
import numpy as np
import psutil
# import redis
import time
import warnings
import xarray as xr

# Where should this go?
f = getframeinfo(currentframe()).filename
p = os.path.dirname(os.path.abspath(f))
os.chdir('C:/users/user/github/Ubuntu-Practice-Machine')

# Check if we are working in Windows or Linux to find the data
if sys.platform == 'win32':
    data_path = 'f:/'
else:
    data_path = '/root/Sync'

# What to do with the mean of empty slice warning?
warnings.filterwarnings("ignore")
from functions import Index_Maps, makeMap, outLine, readRaster
from functions import coordinateDictionaries

# In[]
# TO make a mask
grid = np.load(data_path + "/data/prfgrid.npz")["grid"]
mask = grid * 0+1

# A sample signal for the map maker
signal = [[[2000, 2017], [1, 12]], 'pmean', 'Viridis', 'no']
choice = 'pdsi'

# The index history
[[array, arrays, dates],
 colorscale, dmax, dmin, reverse] = makeMap(signal, choice)  # <---------------fix index maps to return projected arrays is function is parea

# Fix non-values and put in percentile space
arrays = arrays * mask * 100

def droughtArea(arrays, category=1, inclusive=False):
    '''
    This will take in a time series of arrays and a drought severity category
    and mask out all cells with values above or below the category thresholds. 
    If inclusive is 'True' it will only mask out all cells that fall above the
    chosen category. 
    
    For now this requires percentiles.
    '''

    # Drought Categories
    drought_cats = {0: [20, 30], 1: [10, 20], 2: [5, 10], 3: [2, 5], 4: [0, 2]}


    # Make a copy of arrays
    a = arrays.copy()
    
    # example drought category
    d = drought_cats[1]
    
# Total grid cells
# (this might have to be projected)
total_area = np.nansum(mask)

# Every thing that is within the d range is kept
print(dates[0])
for i in range(5):
    d = drought_cats[i]
    a = arrays.copy()
    
    # Filter above or below threshold
    a[(a<d[0]) | (a>d[1])] = np.nan
    
    # get a sample
    a1 = a[0]
    # %varexp --imshow a1

    # get percent of land 'area' in drought
    a2 = a1 * 0 + 1
    drought_area = np.nansum(a2)
    percent = round(100 * (drought_area/total_area), 4)

    print('DM ' + str(i) +': %' + str(percent))

