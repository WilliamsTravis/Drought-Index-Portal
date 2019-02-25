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
import requests
import sys
from progressbar import progressbar as pb
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
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')  # might need for automation...though i could automate cd and back
    data_path = '/root/Sync'

from functions import Index_Maps, readRaster, percentileArrays, im
# gdal.PushErrorHandler('CPLQuietErrorHandler')

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
local_path = os.path.join(data_path, 'data/droughtindices/netcdfs/test.nc')
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)

# So here it is, we will start with a single netcdf and then append another
file1 = '{}_{}_{}_PRISM.nc'.format(index, 2018, 12)
file2 = '{}_{}_{}_PRISM.nc'.format(index, 2019, 1)
local_file1 = 'f:/data/droughtindices/netcdfs/' + file1
local_file2 = 'f:/data/droughtindices/netcdfs/' + file2
url1 = wwdt_url + '/' + index + '/' + file1
url2 = wwdt_url + '/' + index + '/' + file2
date1 = pd.datetime(2018, 12, 15)
date2 = pd.datetime(2018, 12, 15)

# # Get files
# urllib.request.urlretrieve(url1, local_file1)
# urllib.request.urlretrieve(url2, local_file2)

# Reproject files
resampled_file1 = 'f:/data/droughtindices/netcdfs/test1.tif'
resampled_file2 = 'f:/data/droughtindices/netcdfs/test2.tif'

ds = gdal.Warp(resampled_file1, local_file1,
                dstSRS='EPSG:4326', xRes=0.25, yRes=0.25, 
                outputBounds=[-130, 20, -55, 50])
del ds

ds = gdal.Warp(resampled_file2, local_file2,
                dstSRS='EPSG:4326', xRes=0.25, yRes=0.25, 
                outputBounds=[-130, 20, -55, 50])
del ds

# for the first file we need the initial information
file = resampled_file1
savepath = 'f:/data/droughtindices/netcdfs/testers/' + file1
ncfile = local_file1

def toNetCDF(file, ncfile, savepath, epsg=4326, wmode='w'):
    '''
    Take an individual tif and either write or append to netcdf
    '''
    nco = Dataset(savepath, mode=wmode, format='NETCDF4')

    # We need some things from the old nc file
    data = Dataset(ncfile)
    days = data.variables['day'][0]  # This is in days since 1900
    date = dt.date(1900, 1, 1) + dt.timedelta(int(days))
    year = date.year
    month = date.month
    attrs = {key: data.getncattr(key) for key in data.ncattrs()}
    
    # Get a sample file, the first, and get some info from it
    name1 = os.path.basename(file)
    name = os.path.splitext(name1)[0]
    title = 'Palmer Drought Severity Index'

    # Read raster for the structure
    data = gdal.Open(file)
    geom = data.GetGeoTransform()
    proj = data.GetProjection()
    array = data.ReadAsArray()
    array[array==-9999.] = np.nan
    nlat, nlon = np.shape(array)
    longitudes = np.arange(nlon) * geom[1] + geom[0]
    latitudes = np.arange(nlat) * geom[5] + geom[3]
    del data

    # create NetCDF file
    try: nco.close()
    except: pass

    # Dimensions
    lat = nco.createDimension('lat', nlat)
    lon = nco.createDimension('lon', nlon)
    time = nco.createDimension('time', None)
    
    # Variables
    lats = nco.createVariable('lat',  'f4', ('lat',))
    lons = nco.createVariable('lon',  'f4', ('lon',))
    variable = nco.createVariable('value', 'f4', ('time', 'lat', 'lon'),
                                  fill_value=-9999)
    times = nco.createVariable('time', 'f8', ('time',))
    variable.standard_name = 'index'
    variable.units = 'unitless'
    variable.long_name = 'Index Value'
    variable.setncattr('grid_mapping', 'crs')
    crs = nco.createVariable('grid_mapping', 'c')
    crs.crs_wkt = proj
    import rasterio
    crs.epsg_code = rasterio.crs.CRS(init='epsg:4326').to_string()
    crs.GeoTransform = geom

    # Attributes
    # Global Attrs
    nco.title = title_map[index]
    nco.description = ('Monthly gridded data at 0.25 decimal degree' +
                       ' (15 arc-minute resolution, calibrated to 1895-2010 ' +
                       ' for the continental United States.'),
    nco.original_author = 'John Abatzoglou - University of Idaho'
    nco.date = pd.to_datetime(str(today)).strftime('%Y-%m-%d')
    nco.projection = 'WGS 1984 EPSG: 4326'
    nco.citation = ('Westwide Drought Tracker, ' +
                    'http://www.wrcc.dri.edu/monitor/WWDT')

    # Variable Attrs
    times.units = 'days since 1900-01-01'
    times.standard_name = 'time'
    times.calendar = 'gregorian'
    lats.units = 'degrees_north'
    lats.standard_name = 'latitude'
    lons.units = 'degrees_east'
    lons.standard_name = 'longitude'

    # Write    
    lats[:] = latitudes
    lons[:] = longitudes
    times[:] = int(days)

    variable[0, :,] = array
    
    # create container variable for CRS
    refs = osr.SpatialReference()
    refs.ImportFromEPSG(epsg)
    crs.long_name = 'Lon/Lat WGS 84'
    crs.grid_mapping_name = 'latitude_longitude'
    crs.longitude_of_prime_meridian = 0.0
    crs.semi_major_axis = refs.GetSemiMajor()
    crs.inverse_flattening = refs.GetInvFlattening()

    nco.Conventions = 'CF-1.6'
    # nco.title = title
    nco.subtitle = "Monthly Index values since 1900-01-01"

    nco.close()

toNetCDF(file, ncfile, savepath, epsg=4326, wmode='w')
