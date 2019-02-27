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
os.chdir('C:/users/travi/github/Ubuntu-Practice-Machine')

# Check if we are working in Windows or Linux to find the data
if sys.platform == 'win32':
    data_path = 'f:/'
else:
    data_path = '/root/Sync'

# What to do with the mean of empty slice warning?
warnings.filterwarnings("ignore")
from functions import Index_Maps, makeMap, outLine, readRaster
from functions import coordinateDictionaries


def droughtArea( inclusive=False):
    '''
    This will take in a time series of arrays and a drought severity
    category and mask out all cells with values above or below the category
    thresholds. If inclusive is 'True' it will only mask out all cells that
    fall above the chosen category.

    For now this requires original values, percentiles even out too quickly
    '''

    arealist, dmin, dmax = Index_Maps().getAlbers()  # This is used for areal calcs

    [array, arrays, dates, colorscale,
     amax, amin, reverse] = self.meanOriginal()  # This used for display
    arrays = arealist.value.data

    # Drought Categories
    drought_cats = {0: [.20, .30], 1: [.10, .20], 2: [.05, .10],
                    3: [.02, .05], 4: [.00, .02]}

    # Total number of pixels
    total_area = np.nansum(self.mask)

    # We want an ndarray for each category, too
    dm_arrays = {}

    # We want a map for each drought category?
    for i in range(5):
        d = drought_cats[i]
        a = arrays.copy()

        # Filter above or below thresholds
        if inclusive is False:
            a[(a < d[0]) | (a > d[1])] = np.nan
        else:
            a[a > d[1]] = np.nan

        dm_arrays[i] = a

    # Below will have to be outside after the area is filtered
    # a1 = a[0]
    # im(a1)
    #
    # # get percent of land 'area' in drought
    # a2 = a1 * 0 + 1
    # drought_area = np.nansum(a2)
    # percent = round(100 * (drought_area / total_area), 4)
    #
    # print('DM ' + str(i)  + ': %' + str(percent))

    del arrays

    # It is easier to work with these in this format
    dates = indexlist.time.data

    # Get color scale
    colorscale = self.setColor(default='percentile')

    # The colorscale will always mean the same thing
    reverse = False

    # Return a list of five layers, the signal might need to be adjusted
    # for inclusive
    return [array, dm_arrays, dates, colorscale, dmax, dmin, reverse]
