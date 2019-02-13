# -*- coding: utf-8 -*-
"""
    Updating WWDT Data on a monthly basis.

    Target Functionality:
    So using either crontab and letting it
    go on the virtual machine, or finding a hybrid approach, every month this
    will pull the asc file from the WestWide Drought Tracker, transform it, and
    append it to the netcdf file of original values. It will also need to
    rebuild the entire percentile netcdf because that is rank based.


Created on Fri Feb  10 14:33:38 2019

@author: User
"""
from bs4 import BeautifulSoup
from collections import OrderedDict
import datetime as dt
from osgeo import gdal
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import requests
import sys
from tqdm import tqdm
from urllib.error import HTTPError, URLError
import urllib
from socket import timeout
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    os.chdir('Z:/Sync/Ubuntu-Practice-Machine/')  # might need for automation...though i could automate cd and back
    data_path = 'f:/'  # Watch out its d: on the laptop (which isn't available on this pc!)
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')  # might need for automation...though i could automate cd and back
    data_path = '/root/Sync'

from functions import Index_Maps, readRaster, percentileArrays

# In[] set up
wwdt_url = 'https://wrcc.dri.edu/wwdt/data/PRISM'
local_path = os.path.join(data_path, 'data/droughtindices/netcdfs/wwdt/')
if not os.path.exists(local_path):
    os.mkdir(local_path)
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

# For quick array imaging
def im(array):
    plt.imshow(array)

# Starting today
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)

############ Get and Build Data Sets ########################################
for index in indices:
    # We need the key 'value' to point to local data
    nc_path = os.path.join(data_path,
                             'data/droughtindices/netcdfs/',
                             index_map[index] + '.nc')
    print(nc_path + " exists, adding new data...")
    wwdt_index_url = wwdt_url + '/' + index

    if os.path.exists(nc_path):
        ############## If we only need to add a few dates ###################
        with xr.open_dataset(nc_path) as data:
            nc_index = data.load()
            data.close()

        # Get attributes
        new_attrs = nc_index.attrs

        # Extract Dates
        dates = pd.DatetimeIndex(nc_index.time.data)
        t1 = dates[0]
        t2 = dates[-1]

        # Get a list of the dates already in the netcdf file
        existing_dates = pd.date_range(*(pd.to_datetime([t1, t2]) + pd.offsets.MonthEnd()), freq='M')

        # now break the data set into individual months
        nc_index_list = [nc_index.value[i] for i in range(len(nc_index.value))]

        # Get available dates from wwdt
        html = requests.get(wwdt_index_url)
        soup = BeautifulSoup(html.content, "html.parser")
        all_links = soup.find_all('a')
        link_text = [str(l) for l in all_links]
        netcdfs = [l.split('"')[1] for l in link_text if '.nc' in l]

        # how to get single month files?
        month_ncs = [l for l in netcdfs if len(l.split('_')) == 4]
        years = [int(l.split('_')[1]) for l in month_ncs]
        final_year = max(years)
        final_months = [int(l.split('_')[2]) for l in month_ncs if str(final_year) in l]
        final_month = max(final_months)

        # Now, get the range of dates
        t2 = pd.datetime(final_year, final_month, 15)
        available_dates = pd.date_range(*(pd.to_datetime([t1, t2]) + pd.offsets.MonthEnd()), freq='M')
        needed_dates = [a for a in available_dates if a not in existing_dates]

        # Download new files
        for d in tqdm(needed_dates, position=0):
            # build paths
            file = '{}_{}_{}_PRISM.nc'.format(index, d.year, d.month)
            url = wwdt_url + '/' + index + '/' + file
            source_path = os.path.join(local_path, 'temp.nc')

            # They save their dates on day 15
            date = pd.datetime(d.year, d.month, 15)

            # Get file
            try:
                urllib.request.urlretrieve(url, source_path)
            except (HTTPError, URLError) as error:
                logging.error('%s not retrieved because %s\nURL: %s',
                              file, error, url)
            except timeout:
                logging.error('Socket timed out: %s', url)

            # now transform that file
            out_path = os.path.join(local_path, 'temp.tif')
            if os.path.exists(out_path):
                os.remove(out_path)

            ds = gdal.Warp(out_path, source_path, dstSRS='EPSG:4269', xRes=0.25,
                           yRes=0.25, outputBounds=[-130, 20, -55, 50])
            del ds

            # Read it in and append the data array to the list
            base_data = gdal.Open(out_path)
            array = base_data.ReadAsArray()
            del base_data
            array[array == -9999.] = np.nan

            # Use one of the old data arrays as a template
            new = nc_index_list[-1].copy()

            # Assign new value and date to the template
            new.data = array
            new.time.data = date

            # And append it to the old list
            nc_index_list.append(new)

        nc_index_arrays = xr.concat(nc_index_list, dim='time')
        index_nc = xr.Dataset(data_vars={'value': nc_index_arrays},
                              attrs=new_attrs)

        # We need the key 'value' to point to the data
        nc_path = os.path.join(data_path,
                               'data/droughtindices/netcdfs/',
                                index_map[index] + '.nc')

        # In case they release an empty data set
        index_nc = index_nc.dropna(dim='time', how='all')

        # Now save
        index_nc.to_netcdf(nc_path)

    else:
        ############## If we need to start over #######################
        print(nc_path + " not detected, building new data set...")

        # Get the data from wwdt
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
            dates = source.day.data

            # However, it is so much easier to transform the files themselves
            out_path = os.path.join(local_path, 'temp.tif')
            if os.path.exists(out_path):
                os.remove(out_path)

            ds = gdal.Warp(out_path, source_path, dstSRS='EPSG:4269', xRes=0.25,
                           yRes=0.25, outputBounds=[-130, 20, -55, 50])
            del ds
            base_data = gdal.Open(out_path)

            # Now we have arrays of the correct dimensions
            arrays = base_data.ReadAsArray()
            del base_data
            arrays[arrays==-9999.] = np.nan

            # Create lats and lons (will change with resolution)
            lons = np.linspace(-130.0, -55.25, 300, dtype=np.float32)
            lats = np.linspace(50.0, 20.25, 120, dtype=np.float32)
            monthly = xr.DataArray(data=arrays,
                                   coords={'time': dates,
                                           'lat': lats,
                                           'lon': lons},
                                   dims=('time', 'lat', 'lon'))
                                   # attrs=new_attrs)
            monthly_ncs.append(monthly)

        final_arrays = xr.concat(monthly_ncs, 'time')
        final_arrays = final_arrays.sortby('time')  # somethings off...
        final_arrays = final_arrays.dropna('time', 'all')
        index_nc = xr.Dataset(data_vars={'value': final_arrays},
                              attrs=new_attrs)
        t1 = '1948-01-01'
        t2 = index_nc.time.data[-1]
        index_nc = index_nc.sel(time=slice(t1, t2))

        # We need the key 'value' to point to the data
        nc_path = os.path.join(data_path,
                               'data/droughtindices/netcdfs/',
                                index_map[index] + '.nc')
        index_nc.to_netcdf(nc_path)

    # Now recreate the entire percentile data set
    pc_nc = index_nc.copy()

    # let's rank this according to the 1948 to present time period
    percentiles = percentileArrays(pc_nc.value.data)
    pc_nc.value.data = percentiles
    pc_nc.attrs['long_name'] = 'Monthly percentile values since 1948'
    pc_nc.attrs['standard_name'] = 'percentile'
    pc_path = os.path.join(data_path,
                           'data/droughtindices/netcdfs/percentiles',
                            index_map[index] + '.nc')
    pc_nc.to_netcdf(pc_path)
