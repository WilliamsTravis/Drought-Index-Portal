# -*- coding: utf-8 -*-
"""
Working with netcdfs

Created on Sun Feb 24 13:05:22 2019

@author: User
"""
from bs4 import BeautifulSoup
from collections import OrderedDict
import datetime as dt
from osgeo import gdal
from osgeo import osr
import logging
import matplotlib.pyplot as plt
import netCDF4
from netCDF4 import Dataset
import numpy as np
import os
import pandas as pd
import rasterio
import requests
import sys
from urllib.error import HTTPError, URLError
import urllib
from socket import timeout
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    sys.path.extend(['Z:/Sync/Ubuntu-Practice-Machine/',
                     'C:/Users/User/github/Ubuntu-Practice-Machine',
                     'C:/Users/travi/github/Ubuntu-Practice-Machine'])
    data_path = 'f:/'
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')
    data_path = '/root/Sync'

from functions import Index_Maps, readRaster, percentileArrays, im
gdal.PushErrorHandler('CPLQuietErrorHandler')

# For titles
title_map = {'noaa': 'NOAA CPC-Derived Rainfall Index',
             'pdsi': 'Palmer Drought Severity Index',
             'scpdsi': 'Self-Calibrated Palmer Drought Severity Index',
             'pzi': 'Palmer Z-Index',
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

#  We need to include spatial reference information in these, here's a sample
index = 'pdsi'
wwdt_url = 'https://wrcc.dri.edu/wwdt/data/PRISM'
wwdt_index_url = wwdt_url + '/' + index
# local_path = os.path.join(data_path, 'data/droughtindices/netcdfs/' + index +
#                           '_local.nc')
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)

# So here it is, we will start with a single netcdf and then append another
file1 = '{}_{}_{}_PRISM.nc'.format(index, 2018, 12)
file2 = '{}_{}_{}_PRISM.nc'.format(index, 2019, 1)
local_file1 = 'f:/data/droughtindices/netcdfs/testers/' + file1
local_file2 = 'f:/data/droughtindices/netcdfs/testers/' + file2
url1 = wwdt_url + '/' + index + '/' + file1
url2 = wwdt_url + '/' + index + '/' + file2
date1 = pd.datetime(2018, 12, 15)
date2 = pd.datetime(2018, 12, 15)

# # # Get files
urllib.request.urlretrieve(url1, local_file1)
urllib.request.urlretrieve(url2, local_file2)

# Reproject files
resampled_file1 = 'f:/data/droughtindices/netcdfs/testers/' + index + '_new1.tif'
resampled_file2 = 'f:/data/droughtindices/netcdfs/testers/' + index + '_new2.tif'


# Here, we need to translate to flip it right side up, resample to .25 degrees, 
# set the extent to -130, 20, -55, 50, write that, and then write an albers
# equal area projection version

# First set
ds = gdal.Warp(resampled_file1, local_file1,
                dstSRS='EPSG:4326', xRes=0.25, yRes=0.25, 
                outputBounds=[-130, 20, -55, 50])
del ds

ds = gdal.Warp(resampled_file2, local_file2,
                dstSRS='EPSG:4326', xRes=0.25, yRes=0.25, 
                outputBounds=[-130, 20, -55, 50])
del ds

# Albers set
albers_file = 'f:/data/droughtindices/netcdfs/testers/' + index + '_albers1.tif'
ds = gdal.Warp(albers_file, resampled_file1, dstSRS='EPSG:102008')
del ds

# for the first file we need the initial information
file = resampled_file1
savepath = 'f:/data/droughtindices/netcdfs/testers/testing.nc'
ncfile = local_file1

toNetCDF(file, ncfile, savepath, epsg=4326, wmode='w')

# # This still doesn't work
d1 = Dataset('f:/data/droughtindices/netcdfs/testers/testingout.nc')

# # This one does though!
# d2 = Dataset('c:/users/user/downloads/narccap_ecpc-20c3m-tasmin-ncep-with-srs-one-t.nc')
