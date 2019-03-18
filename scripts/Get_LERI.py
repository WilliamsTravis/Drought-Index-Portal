# -*- coding: utf-8 -*-
"""
Landscape Evaporative Response Index

This script will download all or update existing LERI files used in the app. It
uses the same FTP server as EDDI.

    Production notes:
        - LERI does not cover the full grid, and so maybe there would be space
            to experiment with a different resolution?
        - Also, LERI is not available for the same time periods as EDDI, SPI,
            and SPEI. The monthly values are available for 1, 3, 7 and 12
            month-windows.
        - The 1- and 3-month files come out every month, the 7-month files only
            once per year (January), and the 12-month files twice per year
            (September and December). Not sure why this is, and it would throw
            the time-period selection system off. Perhaps we start with just
            the 1- and 3-month LERIs then brainstorm how to fit the others in.
        - Also, these are netcdf files, so the process will be a blend of
            Get_EDDI.py and Get_WWDT.py.

Created on Mon Mar 18 09:47:33 2019

@author: User
"""
import calendar
import datetime as dt
import ftplib
from glob import glob
from netCDF4 import Dataset
import numpy as np
import os
from osgeo import gdal
import pandas as pd
import sys
from tqdm import tqdm
import xarray as xr

if sys.platform == 'win32':
    os.chdir('C:/Users/User/github/Ubuntu-Practice-Machine')
    data_path = 'f:/'
else:
    sys.path.insert(0, '/root/Sync/Ubuntu-Practice-Machine')
    os.chdir('/root/Sync/Ubuntu-Practice-Machine')
    data_path = '/root/Sync'

from functions import toNetCDF2, isInt, toNetCDFPercentile

# gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# In[] Data Source and target directories
ftp_path = 'ftp://ftp.cdc.noaa.gov/Projects/LERI/CONUS_archive/data/'
temp_folder = os.path.join(data_path, 'data/droughtindices/temps')
pc_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/percentiles')
if not os.path.exists(temp_folder):
    os.makedirs(temp_folder)
if not os.path.exists(pc_folder):
    os.makedirs(pc_folder)

# In[] Index Options
indices = ['leri1', 'leri3']

# In[] Define scraping routine
def getLERI(scale, date, temp_folder):
    '''
    The date in the file name always uses the first day of the month.
    '''
    year = date.year
    month = date.month
    file_name = 'LERI_{:02d}mn_{}{:02d}01.nc'.format(scale, year, month)
    local_file = os.path.join(temp_folder, 'temp.nc')
    with open(local_file, 'wb') as dst:
        ftp.retrbinary('RETR %s' % file_name, dst.write)

    return local_file

# In[] Today's date, month, and year
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)
print("##")
print("#####")
print("############")
print("#######################")
print("#######################################")
print("####################################################")
print("\nRunning Get_LERI.py:")
print(str(today) + '\n')

# In[] Get time series of currently available values
# Connect to FTP 
ftp = ftplib.FTP('ftp.cdc.noaa.gov', 'anonymous', 'anonymous@cdc.noaa.gov')
for index in indices:
    ftp.cwd('/Projects/LERI/CONUS_archive/data/')
    print('\n' + index)
    original_path = os.path.join(data_path,
                                 "data/droughtindices/netcdfs/",
                                 index + '.nc')
    percentile_path = os.path.join(data_path,
                                   "data/droughtindices/netcdfs/percentiles",
                                   index + '.nc')
    scale = index[-2:]
    scale = int("".join([s for s in scale if isInt(s)]))

    ####### If we are only missing some dates #################################
    if os.path.exists(original_path):
        with xr.open_dataset(original_path) as data:
            dates = pd.DatetimeIndex(data.time.data)
            data.close()
        
        # Extract dates
        d1 = dates[0]
        d2 = dates[-1]

        # ...

        print('Appending not available yet...')
    ############## If we need to start over ###################################
    else:
        print(original_path + " not detected, building new dataset...\n")

        # Get all available years
        ftp_years = ftp.nlst()
        ftp_years = [f for f in ftp_years if isInt(f)]

        # Find the most recently available month
        max_year = max(ftp_years)
        ftp.cwd(os.path.join('/Projects/LERI/CONUS_archive/data/', max_year))
        files = ftp.nlst()
        files = [f for f in files if int(f[5:7]) == scale]
        months = [int(f[-7:-5]) for f in files]
        max_year = int(max_year)
        max_month = max(months)

        # available dates
        date1 = dt.datetime(int(min(ftp_years)), 1, 1)
        date2 = dt.datetime(max_year, max_month, 1)
        available_dates = pd.date_range(date1, date2, period='M')

        # Loop through these, download and transform data
        for date in tqdm(available_dates, position=0):
            ftp.cwd(os.path.join('/Projects/LERI/CONUS_archive/data/',
                                 str(date.year)))
            file_path = getLERI(scale, date, temp_folder)

            # The are rather large files, this could take a while
            file_name = ('temp_' + str(date.year) +
                         '{:02d}'.format(date.month) + '.tif')
            tif_path = os.path.join(temp_folder,'a' + file_name)

            # Resample each, working from disk
            ds = gdal.Warp(tif_path, file_path,
                           dstSRS='EPSG:4326',
                           xRes=0.125, yRes=0.125,
                           outputBounds=[-130, 20, -55, 50])
            del ds

        # Merge individual tif files into a single netcdf file
        tfiles = glob(os.path.join(temp_folder, '*tif'))
        ncdir = os.path.join(data_path, "data/droughtindices/netcdfs/",
                              index + '.nc')
        toNetCDF2(tfiles=tfiles, ncfiles=None, savepath=ncdir, index=index,  # these are two years short to test append mode above
                  year1=1980, month1=1, year2=todays_date.year, month2=12,
                  epsg=4326, percentiles=False, wmode='w')

        # Now lets get the percentile values
        ncdir_perc = os.path.join(data_path, "data/droughtindices/netcdfs/" +
                                   "percentiles", index + '.nc')
        toNetCDF2(tfiles=tfiles, ncfiles=None, savepath=ncdir_perc,
                  index=index, year1=1980, month1=1, year2=todays_date.year,
                  month2=12, epsg=4326, percentiles=True, wmode='w')

# Close connection with FTP server
ftp.quit()

print("Update Complete.")
print("####################################################")
print("#######################################")
print("#######################")
print("############")
print("#####")
print("##")
