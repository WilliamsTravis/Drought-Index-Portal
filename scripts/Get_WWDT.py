# -*- coding: utf-8 -*-
"""
    Updating WWDT Data on a monthly basis.

    Run this using crontab once a month to pull netcdf files from the
    WestWide Drought Tracker site, transform them to fit in the app, and either
    append them to an existing file, or build the data set from scratch. This
    also rebuilds each percentile netcdf entirely because those are rank based.

    Production notes:
        - The geographic coordinate systems work for the most part. I had to
          use 'degrees_south' for the latitude unit attribute to avoid flipping
          the image. Also, the netcdfs built using my functions appear to have
          coordinates at the grid center, which is different than previous
          geotiffs I created, however, the maps are rendered properly (point in
          lower left corner), and I believe that's because of the binning step.
        - There appears to be a directory bug when starting over, but only for
          wwdt on the virtual machines...this may have been fixed, need to
          check.
        - There are a few ways to make this a little more efficient but I left
          a few redundancies in just to make sure everything is kept in the
          right order, chronologically.
        - Also, if a download fails I'm leaving it be. It should correct itself
          in the next month. This could be improved by redownloading in an
          exception, but I would want advice on how best to handle the case
          where the link/server is down.
        - Also, at the moment, this script only checks the original index files
          so if there's a problem with only the percentiles it won't be
          noticed.

    crontab:
        - to setup a scheduler do this (1:30am on the 2nd of each month):
            1) enter <crontab -e>

            2) insert (but with spaces at these line breaks):
              <30 01 02 * *
               /root/Sync/Ubuntu-Practice-Machine/env/bin/python3
               /root/Sync/Ubuntu-Practice-Machine/scripts/Get_WWDT.py >> 
               cronlog.log>

            3) ctrl + x
            4) This script, because it gets the bulk of the data, is also used
               to set the index ranges for all indices, so schedule it last.

Created on Fri Feb  10 14:33:38 2019

@author: user
"""
from bs4 import BeautifulSoup
from glob import glob
import datetime as dt
import logging
from netCDF4 import Dataset
import numpy as np
import os
from osgeo import gdal
import pandas as pd
import requests
from socket import timeout
import sys
from tqdm import tqdm
from urllib.error import HTTPError, URLError
import urllib
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    sys.path.insert(0, 'C:/Users/User/github/Ubuntu-Practice-Machine')
    os.chdir('C:/Users/User/github/Ubuntu-Practice-Machine')
    data_path = 'f:/'
elif 'travis' in os.getcwd():
    sys.path.insert(0, '/home/travis/github/Ubuntu-Practice-Machine')
    os.chdir('/home/travis/github/Ubuntu-Practice-Machine')
    data_path = ''
else:
    sys.path.insert(0, '/root/Sync/Ubuntu-Practice-Machine')
    os.chdir('/root/Sync/Ubuntu-Practice-Machine')
    data_path = '/root/Sync'

from functions import toNetCDF, toNetCDFAlbers, toNetCDFPercentile
gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# Get resolution from file call
try:
    res = float(sys.argv[1])
except:
    res = 0.25

# In[] Set up paths and urls
wwdt_url = 'https://wrcc.dri.edu/wwdt/data/PRISM'
local_path1 = os.path.join(data_path,
                          'data/droughtindices/netcdfs/wwdt/tifs')
local_path2 = os.path.join(data_path,
                           'data/droughtindices/netcdfs/percentiles')
local_path3 = os.path.join(data_path,
                           'data/droughtindices/netcdfs/albers')
local_path = os.path.join(data_path, 'data/droughtindices/netcdfs/wwdt')

if not os.path.exists(local_path):
    os.makedirs(local_path1)
if not os.path.exists(local_path2):
    os.makedirs(local_path2)
if not os.path.exists(local_path3):
    os.mkdir(local_path3)

# I came up with a slightly differentset of acroynms
indices = ['spi1', 'spi2', 'spi3', 'spi4', 'spi5', 'spi6', 'spi7', 'spi8',
           'spi9', 'spi10', 'spi11', 'spi12', 'spei1', 'spei2', 'spei3',
           'spei4', 'spei5', 'spei6', 'spei7', 'spei8', 'spei9', 'spei10',
           'spei11', 'spei12', 'pdsi', 'scpdsi', 'pzi', 'mdn1']
local_indices = ['spi1', 'spi2', 'spi3', 'spi4', 'spi5', 'spi6', 'spi7',
                 'spi8', 'spi9', 'spi10', 'spi11', 'spi12', 'spei1', 'spei2',
                 'spei3', 'spei4', 'spei5', 'spei6', 'spei7', 'spei8', 'spei9',
                 'spei10', 'spei11', 'spei12', 'pdsi', 'pdsisc', 'pdsiz',
                 'mdn1']

index_map = {indices[i]: local_indices[i] for i in range(len(indices))}
title_map = {'noaa': 'NOAA CPC-Derived Rainfall Index',
             'mdn1': 'Mean Temperature Departure  (1981 - 2010) - 1 month',
             'pdsi': 'Palmer Drought Severity Index',
             'scpdsi': 'Self-Calibrated Palmer Drought Severity Index',
             'pzi': 'Palmer Z-Index',
             'spi1': 'Standardized Precipitation Index - 1 month',
             'spi2': 'Standardized Precipitation Index - 2 month',
             'spi3': 'Standardized Precipitation Index - 3 month',
             'spi4': 'Standardized Precipitation Index - 4 month',
             'spi5': 'Standardized Precipitation Index - 5 month',
             'spi6': 'Standardized Precipitation Index - 6 month',
             'spi7': 'Standardized Precipitation Index - 7 month',
             'spi8': 'Standardized Precipitation Index - 8 month',
             'spi9': 'Standardized Precipitation Index - 9 month',
             'spi10': 'Standardized Precipitation Index - 10 month',
             'spi11': 'Standardized Precipitation Index - 11 month',
             'spi12': 'Standardized Precipitation Index - 12 month',
             'spei1': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 1 month',
             'spei2': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 2 month',
             'spei3': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 3 month',
             'spei4': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 4 month',
             'spei5': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 5 month',
             'spei6': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 6 month',
             'spei7': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 7 month',
             'spei8': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 8 month',
             'spei9': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 9 month',
             'spei10': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 10 month',
             'spei11': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 11 month',
             'spei12': 'Standardized Precipitation-Evapotranspiration Index' +
                      ' - 12 month',
             'eddi1': 'Evaporative Demand Drought Index - 1 month',
             'eddi2': 'Evaporative Demand Drought Index - 2 month',
             'eddi3': 'Evaporative Demand Drought Index - 3 month',
             'eddi6': 'Evaporative Demand Drought Index - 6 month'}

# There are often missing epsg codes in the gcs.csv file, but proj4 works
proj = ('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 +lon_0=-96 +x_0=0 +y_0=0 ' +
        '+ellps=GRS80 +datum=NAD83 +units=m no_defs')

# Starting today
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)
print("##")
print("#####")
print("############")
print("#######################")
print("#######################################")
print("####################################################")
print("\nRunning Get_WWDT.py using a " + str(res) + " degree resolution:\n")
print(str(today) + '\n')

############ Get and Build Data Sets ########################################
for index in indices:
    # We need the key 'value' to point to local data
    nc_path = os.path.join(data_path,
                           'data/droughtindices/netcdfs/',
                           index_map[index] + '.nc')
    nc_proj_path = os.path.join(data_path,
                                'data/droughtindices/netcdfs/albers/',
                                index_map[index] + '.nc')
    wwdt_index_url = wwdt_url + '/' + index

    if os.path.exists(nc_path):  # Create a netcdf and append to file
        print(nc_path + " exists, checking for missing data...")

        ############## If we only need to add a few dates ###################
        with xr.open_dataset(nc_path) as data:
            dates = pd.DatetimeIndex(data.time.data)
            data.close()

        # Extract Dates
        t1 = dates[0]
        t2 = dates[-1]

        if t2.year == todays_date.year and t2.month == todays_date.month - 1:
            print('No missing files, moving on...\n')
        else:
            # Get a list of the dates already in the netcdf file
            existing_dates = pd.date_range(*(pd.to_datetime([t1, t2]) +
                                              pd.offsets.MonthEnd()), freq='M')

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
            final_months = [int(l.split('_')[2]) for l in month_ncs if
                            str(final_year) in l]
            final_month = max(final_months)

            # Now, get the range of dates
            t2 = pd.datetime(final_year, final_month, 15)
            available_dates = pd.date_range(*(pd.to_datetime([t1, t2]) +  # <-- Why end of month? To be as confused as possible, I think. 
                                              pd.offsets.MonthEnd()), freq='M')
            needed_dates = [a for a in available_dates if
                            a not in existing_dates]

            # Just in case a date got in too early
            for d in needed_dates:
                if d > pd.Timestamp(today):
                    idx = needed_dates.index(d)
                    needed_dates.pop(idx)

            # Download new files
            if len(needed_dates) > 0:
                print_statement = '{} missing file(s) since {}...\n'
                print(print_statement.format(len(needed_dates),
                                             needed_dates[0]))

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

                    ds = gdal.Warp(out_path, source_path, dstSRS='EPSG:4326',
                                   xRes=res, yRes=res,
                                   outputBounds=[-130, 20, -55, 50])
                    del ds

                    # Also create an alber's equal area projection
                    source_path = out_path
                    out_path_p = os.path.join(local_path, 'proj_temp.tif')
                    if os.path.exists(out_path):
                        os.remove(out_path)

                    ds = gdal.Warp(out_path_p, source_path,
                                   dstSRS=proj)
                    del ds

                    # Open old data sets
                    old = Dataset(nc_path, 'r+')
                    old_p = Dataset(nc_proj_path, 'r+')
                    times = old.variables['time']
                    times_p = old_p.variables['time']
                    values = old.variables['value']
                    values_p = old_p.variables['value']
                    n = times.shape[0]

                    # Convert new date to days
                    date = dt.datetime(d.year, d.month, day=15)
                    days = date - dt.datetime(1900, 1, 1)
                    days = np.float64(days.days)

                    # Convert new data to array
                    base_data = gdal.Open(out_path)
                    base_data_p = gdal.Open(out_path_p)
                    array = base_data.ReadAsArray()
                    array_p = base_data_p.ReadAsArray()
                    del base_data
                    del base_data_p

                    # Write changes to file and close
                    times[n] = days
                    times_p[n] = days
                    values[n] = array
                    values_p[n] = array_p
                    old.close()
                    old_p.close()

                # Now recreate the entire percentile data set
                print('Reranking percentiles...')
                pc_path = os.path.join(data_path,
                                     'data/droughtindices/netcdfs/percentiles',
                                     index_map[index] + '.nc')    
                os.remove(pc_path)
                toNetCDFPercentile(nc_path, pc_path) 

    else:
        ############## If we need to start over #######################
        print(nc_path + " not detected, building new data set...")

        # Get the data from wwdt
        print("Downloading the 12 netcdf files for " + index + "...")
        for i in tqdm(range(1, 13), position=0):
            # These come in monthly files - e.g. all januaries in one file
            file_name = '{}_{}_PRISM.nc'.format(index, i)
            target_url = wwdt_url + '/' + index + '/' + file_name
            temp_path = os.path.join(local_path, 'temp_{}.nc'.format(i))

            # Download
            try:
                urllib.request.urlretrieve(target_url, temp_path)
            except (HTTPError, URLError) as error:
                logging.error('%s not retrieved. %s\nURL: %s',
                              file_name, error, target_url)
            except timeout:
                logging.error('Socket timed out: %s', target_url)
            else:
                logging.info('Access successful.')

        # Get the dates from one of the new data sets
        print("Transforming downloaded netcdfs into properly shaped tiffs...")
        for i in tqdm(range(1, 13), position=0):
            # DL each monthly file
            source_path = os.path.join(local_path, 'temp_{}.nc'.format(i))

            # Get the original dates in the right format
            with xr.open_dataset(source_path) as data:
                dates = data.day.data

            # It is much easier to transform the files themselves
            out_path = os.path.join(local_path, 'tifs',
                                    'temp_{}.tif'.format(i))

            if os.path.exists(out_path):
                os.remove(out_path)

            ds = gdal.Warp(out_path, source_path, dstSRS='EPSG:4326', xRes=res,
                           yRes=res, outputBounds=[-130, 20, -55, 50])
            del ds

            # Do the same for alber's
            source_path = out_path
            out_path = os.path.join(local_path, 'tifs',
                                    'proj_temp_{}.tif'.format(i))
            ds = gdal.Warp(out_path, source_path, dstSRS=proj)
            del ds

        # These are lists of all the temporary files, (1, 10, 11, 12, 2, 3,...)
        tfiles = glob(os.path.join(local_path, 'tifs', 'temp_*[0-9]*.tif'))
        tfiles_proj = glob(os.path.join(local_path, 'tifs',
                                        'proj_temp_*[0-9]*.tif'))
        ncfiles = glob(os.path.join(local_path, 'temp_*[0-9]*.nc'))

        # This is the target file - wwdt acronyms differ
        nc_path = os.path.join(data_path, 'data/droughtindices/netcdfs/',
                               index_map[index] + '.nc')
        nc_path_proj = os.path.join(data_path, 
                                    'data/droughtindices/netcdfs/albers',
                                    index_map[index] + '.nc')

        # This function smooshes everything into one netcdf file
        toNetCDF(tfiles, ncfiles, nc_path, index, proj=4326, year1=1895,
                 month1=1, year2=todays_date.year, month2=todays_date.month,
                 wmode='w', percentiles=False)

        # We are also including percentiles, so lets build another dataset
        pc_path = os.path.join(data_path,
                               'data/droughtindices/netcdfs/percentiles',
                               index_map[index] + '.nc')
        print("Calculating Percentiles...")
        toNetCDFPercentile(nc_path, pc_path)

        # Now create the alber's netcdf
        toNetCDFAlbers(tfiles_proj, ncfiles, nc_path_proj, index, proj=proj,
                       year1=1895, month1=1, year2=todays_date.year,
                       month2=todays_date.month, wmode='w', percentiles=False)


# We use a pre-made min/max value data frame to set color scales
print("Downloads and transformations complete, establishing index ranges...")
index_paths = [os.path.join(data_path,'data/droughtindices/netcdfs',
                            i  + '.nc') for i in local_indices]
maxes = {}
mins = {}
for i in tqdm(range(len(index_paths)), position=0):
    try:
        with xr.open_dataset(index_paths[i]) as data:
            indexlist = data
            data.close()
        mx = float(indexlist.max().value)
        mn = float(indexlist.min().value)
        maxes[local_indices[i]] = mx
        mins[local_indices[i]] = mn
    except:
        pass

df = pd.DataFrame([maxes, mins]).T
df.columns = ['max', 'min']
df['index'] = df.index
df.to_csv('data/index_ranges.csv', index=False)


print("Update Complete.")
print("####################################################")
print("#######################################")
print("#######################")
print("############")
print("#####")
print("##")
