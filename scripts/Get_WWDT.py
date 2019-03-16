# -*- coding: utf-8 -*-
"""
    Updating WWDT Data on a monthly basis.

    Target Functionality:
    So using either crontab and letting it
    go on the virtual machine, or finding a hybrid approach, every month this
    will pull the netcdf files from the WestWide Drought Tracker, transform
    them, and append to the netcdf file of original values. It will also need
    to rebuild the entire percentile netcdf because that is rank based.


    Production notes:
        - This doesn't work if the files exist! Turn off crontab scheduler!
        - The geographic coordinate systems work for the most part. I had to use
        'degrees_south' for the latitude unit attribute to avoid flipping the
        image. Also, the netcdfs built using my functions appear to have coordinates
        at the grid center, which is different than previous geotiffs I created, however,
        the maps are rendered properly (point in lower left corner)
        - This currently does not work in linux
        - An error reading wwdt data included artifacts for future dates.

Created on Fri Feb  10 14:33:38 2019

@author: User
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
import sys
from tqdm import tqdm
from urllib.error import HTTPError, URLError
import urllib
from socket import timeout
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    os.chdir('C:/Users/User/github/Ubuntu-Practice-Machine')
    data_path = 'f:/'
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine')
    data_path = '/root/Sync'

from functions import  percentileArrays, toNetCDF2, im
gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# Set up paths and urls
wwdt_url = 'https://wrcc.dri.edu/wwdt/data/PRISM'
local_path = os.path.join(data_path, 'data/droughtindices/netcdfs/wwdt/')
if not os.path.exists(local_path):
    os.mkdir(local_path)
indices = ['spi1', 'spi2', 'spi3', 'spi6', 
          # 'spei1', 'spei2', 'spei3', 'spei6',
           'pdsi', 'scpdsi', 'pzi'
           ]
local_indices = ['spi1', 'spi2', 'spi3', 'spi6',
                # 'spei1', 'spei2', 'spei3', 'spei6',
                 'pdsi', 'pdsisc', 'pdsiz'
                 ]

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

# Starting today
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)
print("##")
print("#####")
print("############")
print("#######################")
print("#######################################")
print("####################################################")
print("\nRunning Get_WWDT.py:")
print(str(today) + '\n')

############ Get and Build Data Sets ########################################
for index in indices:
    # We need the key 'value' to point to local data
    nc_path = os.path.join(data_path,
                           'data/droughtindices/netcdfs/',
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
            available_dates = pd.date_range(*(pd.to_datetime([t1, t2]) +  # <-- Why end of month? Could be useful for another data set, I guess, and doesn't really matter yet
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

                for d in tqdm(needed_dates, redirect_stdout=True):

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
                                   xRes=0.25, yRes=0.25,
                                   outputBounds=[-130, 20, -55, 50])
                    del ds
    

                    # Open old data set
                    # old = Dataset(nc_path, 'r')
                    old = Dataset(nc_path, 'a')

                    # Append new date to time dimension
                    date = dt.datetime(d.year, d.month, day=15)
                    days = date - dt.datetime(1900, 1, 1)
                    days = np.float64(days.days)
                    old_times = old.variables['time'][:]  # <------------------ days since 1900-1-1
                    new_times = np.ma.append(old_times, days)
                    old.variables['time'][:] = new_times[:]

                    # Append new data to value dimension
                    # Read it in extract the array
                    base_data = gdal.Open(out_path)
                    array = base_data.ReadAsArray()
                    del base_data
                    # array[array == -9999.] = np.nan
                    array = np.ma.masked_where(array==-9999, array)
                    np.ma.set_fill_value(array, -9999)
                    old_data = list(old.variables['value'][:])  # <------------------ masked_arrays are causing problems some where. An extra empty data array with a non value for the time
                    old_data.append(array)
                    # new_data = np.array(old_data)
                    # new_data[new_data == -9999] = np.nan
                    new_data = np.ma.stack(old_data, axis=0)
                    np.ma.set_fill_value(new_data, -9999)
                    old.variables['value'][:] = new_data[:]
    
                    # Close dataset write changes to file
                    old.set_auto_mask(False)
                    old.set_fill_off()
                    old.close()      


            # # Now recreate the entire percentile data set
            # print('Reranking percentiles...')
            # pc_nc = index_nc.copy()
        
            # # let's rank this according to the 1900 to present time period
            # percentiles = percentileArrays(pc_nc.value.data)
            # pc_nc.value.data = percentiles
            # pc_nc.attrs['long_name'] = 'Monthly percentile values since 1895'
            # pc_nc.attrs['standard_name'] = 'percentile'
            # pc_path = os.path.join(data_path,
            #                        'data/droughtindices/netcdfs/percentiles',
            #                         index_map[index] + '.nc')
            # os.remove(pc_path)
            # pc_nc.to_netcdf(pc_path)
            
    else:
        ############## If we need to start over #######################
        print(nc_path + " not detected, building new data set...")

        # Get the data from wwdt
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

        # Get some of the attributes from one of the new data sets
        for i in tqdm(range(1, 13), position=0):
            # DL each monthly file
            source_path = os.path.join(local_path, 'temp_{}.nc'.format(i))

            # Get the original dates in the right format
            with xr.open_dataset(source_path) as data:
                dates = data.day.data
                data.close()

            # It is much easier to transform the files themselves
            out_path = os.path.join(local_path, 'tifs',
                                    'temp_{}.tif'.format(i))

            if os.path.exists(out_path):
                os.remove(out_path)

            ds = gdal.Warp(out_path, source_path, format='GTiff',
                           dstSRS='EPSG:4326', xRes=.25,
                           yRes=.25, outputBounds=[-130, 20, -55, 50])
            del ds

        # These are lists of all the temporary files
        tfiles = glob(os.path.join(local_path, 'tifs', 'temp_*[0-9]*.tif'))
        ncfiles = glob(os.path.join(local_path, 'temp_*[0-9]*.nc'))

        # This is the target file - wwdt acronyms differ (and I'm not changing)
        savepath = os.path.join(data_path, 'data/droughtindices/netcdfs/',
                                index_map[index] + '.nc')

        # This function smooshes everything into one netcdf file
        toNetCDF2(tfiles, ncfiles, savepath, index, epsg=4326, year1=1895,
                  month1=1, year2=todays_date.year, month2=todays_date.month,
                  wmode='w', percentiles=False)

        # We are also including percentiles, so lets build another dataset
        savepath_perc = os.path.join(data_path,
                                     'data/droughtindices/netcdfs/percentiles',
                                     index_map[index] + '.nc')
        toNetCDF2(tfiles, ncfiles, savepath_perc, index, epsg=4326, year1=1895,
                  month1=1, year2=todays_date.year, month2=todays_date.month,
                  wmode='w', percentiles=True)

        # # Now, for areal calculations, we'll need a projected version
        # inpath = savepath
        # outpath = os.path.join(data_path, 'data/droughtindices/netcdfs/albers',
        #                         index_map[index] + '.tif')
        # if os.path.exists(outpath):
        #     os.remove(outpath)
        # ds = gdal.Warp(outpath, inpath, srcSRS='EPSG:4326', dstNodata = -9999,
        #                dstSRS='EPSG:102008')

        # # The format is off, so let's build another netcdf from the tif above
        # tfile = outpath
        # ncfile = savepath
        # savepath = os.path.join(data_path,
        #                         'data/droughtindices/netcdfs/albers',
        #                         index_map[index] + '.nc')
        # toNetCDF3(tfile, ncfile, savepath, index, epsg=102008,
        #           wmode='w', percentiles=False)

print("Update Complete.")
print("####################################################")
print("#######################################")
print("#######################")
print("############")
print("#####")
print("##")
