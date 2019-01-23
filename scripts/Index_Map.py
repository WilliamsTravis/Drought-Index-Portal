# -*- coding: utf-8 -*-
"""
Created on Sun Jan 20 12:36:36 2019

Creating a class out of the mapMaker function
@author: User
"""

# In[] Functions and Libraries
import datetime as dt
import warnings
import numpy as np
import os
import pandas as pd
import psutil
import sys
import time
import warnings
import xarray as xr

warnings.filterwarnings("ignore")

# Check if we are working in Windows or Linux
if sys.platform == 'win32':
    home_path = 'c:/users/user/github'
    data_path = 'd:/'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
    startyear = 1948
else:
    home_path = '/root/Sync'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
    data_path = '/root'
    startyear = 1948

from functions import calculateCV
from functions import standardize
source_signal = [[[2000, 2017], [1, 12]], 'mean_perc', 'Viridis', 'no', 'pdsi']

# In[] Original Function
# Stand in function. I will create a simpler class out of this...

class Index_Maps():
    '''
    This class creates a singular map as a function of some timeseries of
        rasters for use in the Ubuntu-Practice-Machine index comparison app.
        It also returns information needed for rendering. 

        Initializing arguments:
            
            timerange (list)    = [[Year1, Year2], [Month1, Month2]]
            function (string)   = 'mean_perc': 'Average Percentiles',
                                  'max': 'Maxmium Percentile',
                                  'min': 'Minimum Percentile',
                                  'mean_original': 'Mean Original Values',
                                  'omax': 'Maximum Original Value',
                                  'omin': 'Minimum Original Value',
                                  'ocv': 'Coefficient of Variation - Original'
            choice (string)     = 'noaa', 'pdsi', 'pdsisc', 'pdsiz', 'spi1',
                                  'spi2', 'spi3', 'spi6', 'spei1', 'spei2',
                                  'spei3', 'spei6', 'eddi1', 'eddi2', 'eddi3',
                                  'eddi6'
        Each function returns:
    
            array      = Singular 2D Numpy array of function output
            arrays     = Timeseries of 2D Numpy arrays within time range
            dates      = List of Posix time stamps
            dmax       = maximum value of array
            dmin       = minimum value of array
    '''

    # Reduce memory by preallocating attribute slots
    __slots__ = ('year1', 'year2', 'month1', 'month2', 'function',
                 'colorscale', 'reverse', 'choice', 'mask',
                 'RdWhBu', 'RdYlGnBu')

    # Create Initial Values
    def __init__(self, time_range=[[2000, 2017], [1, 12]],
                 colorscale='Viridis', reverse='no', choice='pdsi'): 
        self.year1 = time_range[0][0]
        self.year2 = time_range[0][1]
        if self.year1 == self.year2:
            self.month1 = time_range[1][0]
            self.month2 = time_range[1][1]
        else:
            self.month1 = 1
            self.month2 = 12
        self.colorscale = colorscale
        self.reverse = reverse
        self.choice = choice
        grid = np.load(os.path.join(data_path, "data/prfgrid.npz"))["grid"]
        self.mask = grid * 0 + 1
        self.RdWhBu = [[0.00, 'rgb(115,0,0)'],
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

        self.RdYlGnBu = [[0.00, 'rgb(124, 36, 36)'],
                         [0.25, 'rgb(255, 255, 48)'],
                         [0.5, 'rgb(76, 145, 33)'],
                         [0.85, 'rgb(0, 92, 221)'],
                         [1.00, 'rgb(0, 46, 110)']]


    def getOriginal(self):
        '''
        Retrieve Original Timeseries
        '''
        # Get time series of values
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/",
                                  self.choice + '.nc')
        indexlist = xr.open_dataset(array_path)

        # Get total Min and Max Values for colors
        values = indexlist.value.data
        values[values == 0] = np.nan
        limits = [abs(np.nanmin(values)), abs(np.nanmax(values))]
        dmax = max(limits)
        dmin = dmax*-1
        del values

        # filter by date
        d1 = dt.datetime(self.year1, self.month1, 1)
        d2 = dt.datetime(self.year2, self.month2, 1)
        arrays = indexlist.sel(time=slice(d1, d2))
        del indexlist

        return [arrays, dmin, dmax]


    def getPercentile(self):
        '''
        Retrieve Percentiles of Original Timeseries
        '''
        # Get time series of values
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/percentiles",
                                  self.choice + '.nc')
        indexlist = xr.open_dataset(array_path)

        # Get total Min and Max Values for colors
        dmax = 1
        dmin = 0

        # filter by date
        d1 = dt.datetime(self.year1, self.month1, 1)
        d2 = dt.datetime(self.year2, self.month2, 1)
        arrays = indexlist.sel(time=slice(d1, d2))
        del indexlist

        return [arrays, dmin, dmax]


    def meanOriginal(self):
        '''
        Calculate mean of original index values
        '''
        # Get time series of values
        [arrays, dmin, dmax] = self.getOriginal()

        # Get data
        data = arrays.mean('time')
        array = data.value.data
        del data
        array[array == 0] = np.nan
        array = array*self.mask

        # It is easier to work with these in this format
        dates = arrays.time.data
        arrays = arrays.value.data
        
        # Colors - Default is a custom style
        if self.colorscale == 'Default':
            colorscale = self.RdYlGnBu
        else:
            colorscale = self.colorscale

        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [[array, arrays, dates], colorscale, dmax, dmin, reverse]


    def maxOriginal(self):
        '''
        Calculate max of original index values
        '''
        # Get time series of values
        [arrays, dmin, dmax] = self.getOriginal()

        # Get data
        data = arrays.max('time')
        array = data.value.data
        del data
        array[array == 0] = np.nan
        array = array*self.mask

        # It is easier to work with these in this format
        dates = arrays.time.data
        arrays = arrays.value.data
        
        # Colors - Default is a custom style
        if self.colorscale == 'Default':
            colorscale = self.RdYlGnBu
        else:
            colorscale = self.colorscale

        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [[array, arrays, dates], colorscale, dmax, dmin, reverse]


    def minOriginal(self):
        '''
        Calculate max of original index values
        '''
        # Get time series of values
        [arrays, dmin, dmax] = self.getOriginal()

        # Get data
        data = arrays.min('time')
        array = data.value.data
        del data
        array[array == 0] = np.nan
        array = array*self.mask

        # It is easier to work with these in this format
        dates = arrays.time.data
        arrays = arrays.value.data
        
        # Colors - Default is a custom style
        if self.colorscale == 'Default':
            colorscale = self.RdYlGnBu
        else:
            colorscale = self.colorscale

        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [[array, arrays, dates], colorscale, dmax, dmin, reverse]


    def meanPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [arrays, dmin, dmax] = self.getPercentile()

        # Get data
        data = arrays.mean('time')
        array = data.value.data
        del data
        array[array == 0] = np.nan
        array = array*self.mask
        
        # It is easier to work with these in this format
        dates = arrays.time.data
        arrays = arrays.value.data

        # Colors - Default is USDM style, sort of
        if self.colorscale == 'Default':
            colorscale = self.RdWhBu
        else:
            colorscale = self.colorscale

        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [[array, arrays, dates], colorscale, dmax, dmin, reverse]


    def maxPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [arrays, dmin, dmax] = self.getPercentile()

        # Get data
        data = arrays.max('time')
        array = data.value.data
        del data
        array[array == 0] = np.nan
        array = array*self.mask
        
        # It is easier to work with these in this format
        dates = arrays.time.data
        arrays = arrays.value.data

        # Colors - Default is USDM style, sort of
        if self.colorscale == 'Default':
            colorscale = self.RdWhBu
        else:
            colorscale = self.colorscale

        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [[array, arrays, dates], colorscale, dmax, dmin, reverse]


    def minPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [arrays, dmin, dmax] = self.getPercentile()

        # Get data
        data = arrays.min('time')
        array = data.value.data
        del data
        array[array == 0] = np.nan
        array = array*self.mask
        
        # It is easier to work with these in this format
        dates = arrays.time.data
        arrays = arrays.value.data

        # Colors - Default is USDM style, sort of
        if self.colorscale == 'Default':
            colorscale = self.RdWhBu
        else:
            colorscale = self.colorscale

        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [[array, arrays, dates], colorscale, dmax, dmin, reverse]

    def coefficientVariation(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [arrays, dmin, dmax] = self.getOriginal()

        # Get data
        numpy_arrays = arrays.value.data
        array = calculateCV(numpy_arrays)
        del numpy_arrays
        array[array == 0] = np.nan
        array = array*self.mask
        
        # It is easier to work with these in this format
        dates = arrays.time.data
        arrays = arrays.value.data

        # Colors - Default is USDM style, sort of
        if self.colorscale == 'Default':
            colorscale = 'Portland'
        else:
            colorscale = self.colorscale

        # The colorscale will always mean the same thing
        reverse = False

        return [[array, arrays, dates], colorscale, dmax, dmin, reverse]

