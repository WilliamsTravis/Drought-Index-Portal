# -*- coding: utf-8 -*-
"""
    Updating WWDT Data on a monthly basis.

    Target Functionality:
    So using either crontab and letting it
    go on the virtual machine, or finding a hybrid approach, every month this
    will pull the asc file from the NOAA's EDDI server, transform it, and
    append it to the netcdf file of original values. It will also need to
    rebuild the entire percentile netcdf because that is rank based. It will
    also need to update the script to allow for new dates.

    Production Notes:


Created on Fri Feb  10 14:33:38 2019

@author: User
"""
import calendar
from collections import OrderedDict
import datetime as dt
import ftplib
from osgeo import gdal
from inspect import currentframe, getframeinfo
import logging
import numpy as np
import os
import pandas as pd
import sys
import scipy
from tqdm import tqdm
from urllib.error import HTTPError, URLError
import urllib
from socket import timeout
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    os.chdir('Z:/Sync/Ubuntu-Practice-Machine/')
    data_path = 'd:/'
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')
    data_path = '/root/Sync'

import functions
from functions import Index_Maps, readRaster, percentileArrays

# In[] set up
wwdt_url = 'https://wrcc.dri.edu/wwdt/data/PRISM/'
local_path = 'd:/data/droughtindices/netcdfs/wwdt/'
indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2', 'spei3', 'spei6',
           'pdsi', 'scpdsi', 'pzi']
local_indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2',
                           'spei3', 'spei6', 'pdsi', 'pdsisc', 'pdsiz']
index_map = {indices[i]: local_indices[i] for i in range(len(indices))}
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

mask = readRaster(os.path.join(data_path, 'data/droughtindices/prfgrid.tif'),
                  1, -9999)[0]

# In[]
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)

# If we need to start over
index = 'pzi'
print(local_path + " not detected, building new dataset...")

# Get the data from wwdt
for i in range(1, 13):
    file_name = '{}_{}_PRISM.nc'.format(index, i)
    target_url = wwdt_url + '/' + index + '/' + file_name
    temp_path = os.path.join(local_path, 'temp_{}.nc'.format(i))
    try:
        urllib.request.urlretrieve(target_url, temp_path)
    except (HTTPError, URLError) as error:  # I don't think this works
        logging.error('%s not retrieved because %s\nURL: %s',
                      file_name, error, target_url)
    except timeout:
        logging.error('Socket timed out: %s', target_url)
    else:
        logging.info('Access successful.')

# Get some of the attributes from one of the new data sets
source_path = os.path.join(local_path, 'temp_1.nc')
source_data = xr.open_dataset(source_path)
attrs = source_data.attrs
author = attrs['author']
citation = attrs['note3']
index_title = title_map[index]
description = ('Monthly gridded data at 0.25 decimal degrees ' +
               '(15 arc-minute) resolution, calibrated to 1895-2010 for ' +
               'the continental United States.')
new_attrs = OrderedDict({'title': index_title, 'description': description, 
                         'units': 'unitless', 'long_name': 'Index Value',
                         'standard_name': 'index', 'Original Author': author,
                         'citation': citation})

monthly_ncs = []
for i in tqdm(range(1, 13), position=0):
    # Okay, so I'd like to keep the original information and only change
    # geometries. Use each temp_X.nc for the dates and attributes
    source_path = os.path.join(local_path, 'temp_{}.nc'.format(i))
    source = xr.open_dataset(source_path)
    dates = data.day.data

    # However, it is so much easier to transform the files themselves
    out_path = os.path.join(local_path, 'temp.tif')
    ds = gdal.Warp(out_path, source_path, dstSRS='EPSG:4269', xRes=0.25,
                   yRes=0.25, outputBounds=[-130, 20, -55, 50])
    ds = None    
    base_data = gdal.Open(out_path)

    # Now we have arrays of the correct dimensions
    arrays = base_data.ReadAsArray()
    arrays[arrays==-9999.] = np.nan

    monthly = xr.DataArray(data=arrays,
                           coords={'time': dates,
                                   'lat': lats,
                                   'lon': lons},
                           dims=('time', 'lat', 'lon'),
                           attrs=new_attrs)
    monthly_ncs.append(monthly)

final_arrays = xr.concat(monthly_ncs, 'time')
final_arrays = final_arrays.sortby('time')  # somethings off...
final_arrays = final_arrays.dropna('time', 'all')
final_nc = xr.Dataset(data_vars={'value': final},
                      attrs=new_attrs)

# We need the key 'value' to point to the data

save_path = os.path.join(data_path,
                         'data/droughtindices/netcdfs/',
                         index_map[index] + '.nc')
final_nc.to_netcdf(save_path)


