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

# In[] 
wwdt_url = 'https://wrcc.dri.edu/wwdt/data/PRISM/'
local_path = 'd:/data/droughtindices/netcdfs/wwdt/'
indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2', 'spei3', 'spei6',
           'pdsi', 'scpdsi', 'pzi']
local_indices = indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2',
                           'spei3', 'spei6', 'pdsi', 'pdsisc', 'pdsiz']
index_map = {indices[i]: local_indices[i] for i in range(len(indices))}

# If we need to start over
index = 'pzi'
for i in range(1, 13):
    file_name = '{}_{}_PRISM.nc'.format(index, i)
    target_url = wwdt_url + '/' + index + '/' + file_name
    temp_path = os.path.join(local_path, 'temp_{}.nc'.format(i))
    try:
        urllib.request.urlretrieve(target_url, temp_path)
    except (HTTPError, URLError) as error:
        logging.error('%s not retrieved because %s\nURL: %s',
                      file_name, error, target_url)
    except timeout:
        logging.error('Socket timed out: %s', target_url)
    else:
        logging.info('Access successful.')





for i in range(1, 13):
    # Okay, so I'd like to keep the original information and only change
    # geometries. Use each temp_X.nc for the dates and attributes
    source_data = xr.open_dataset(os.path.join(local_path, 'temp_4.nc'))

    # However, it is so much easier to transform the files themselves
    in_path = os.path.join(local_path, 'temp_4.nc'.format(i))
    out_path = os.path.join(local_path, 'temp2.tif')
    ds = gdal.Warp(in_path, out_path,dstSRS='EPSG:4269', xRes=0.25, yRes=0.25,
                   outputBounds=[-130, 20, -55, 50])
    ds = None    
    base_data = gdal.Open(out_path)
    
    # Now we have arrays of the correct dimensions
    arrays = base_data.ReadAsArray()
    so 
    
    
    
















