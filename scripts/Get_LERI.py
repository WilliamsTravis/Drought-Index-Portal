# -*- coding: utf-8 -*-
"""
Landscape Evaporative Response Index

This script will download all or update existing LERI files used in the app. It
uses the same FTP server as EDDI.

    Production notes:
        - LERI does not usually cover the full grid and only dates back to
            2000, so maybe there would be space to experiment with a
            different resolution?
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
        - I am sharing the temp folder with EDDI, so don't run the two at the
            same time (Get_LERI and Get_EDDI).

Created on Mon Mar 18 09:47:33 2019

@author: User
"""
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
    sys.path.insert(0, 'C:/Users/User/github/Ubuntu-Practice-Machine')
    os.chdir('C:/Users/User/github/Ubuntu-Practice-Machine')
    data_path = 'f:/'
else:
    sys.path.insert(0, '/root/Sync/Ubuntu-Practice-Machine')
    os.chdir('/root/Sync/Ubuntu-Practice-Machine')
    data_path = '/root/Sync'

from functions2 import toNetCDF, toNetCDFAlbers, toNetCDFPercentile, isInt

# These make output logs too noisy to see what happened
gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# There are often missing epsg codes in the gcs.csv file, but proj4 works
proj = ('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 +lon_0=-96 +x_0=0 +y_0=0 ' +
        '+ellps=GRS80 +datum=NAD83 +units=m no_defs')

# Get resolution from file call
try:
    res = float(sys.argv[1])
except:
    res = 0.25

# In[] Data Source and target directories
ftp_path = 'ftp://ftp.cdc.noaa.gov/Projects/LERI/CONUS_archive/data/'
temp_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/leri')
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
    local_file = os.path.join(temp_folder, 'leri.nc')
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
print("\nRunning Get_LERI.py using a " + str(res) + " degree resolution:\n")
print(str(today) + '\n')

# In[] Get time series of currently available values
# Connect to FTP 
ftp = ftplib.FTP('ftp.cdc.noaa.gov', 'anonymous', 'anonymous@cdc.noaa.gov')
for index in indices:
    ftp.cwd('/Projects/LERI/CONUS_archive/data/')
    print('\n' + index)
    original_path = os.path.join(data_path, "data/droughtindices/netcdfs/",
                                 index + ".nc")
    percentile_path = os.path.join(data_path,
                                   "data/droughtindices/netcdfs/percentiles",
                                   index + '.nc')
    albers_path = os.path.join(data_path, "data/droughtindices/netcdfs/albers",
                               index + '.nc')
    scale = index[-2:]
    scale = int("".join([s for s in scale if isInt(s)]))

    # Delete existing contents of temporary folder
    temps = glob(os.path.join(temp_folder, "*"))
    for t in temps:
        os.remove(t)

    ####### If we are only missing some dates #################################
    if os.path.exists(original_path):
        with xr.open_dataset(original_path) as data:
            dates = pd.DatetimeIndex(data.time.data)
            data.close()
        
        # Extract dates
        d1 = dates[0]
        d2 = dates[-1]

        # Get a list of the dates already in the netcdf file
        existing_dates = pd.date_range(d1, d2, freq="M")

        # Get all of the last day of month files for the index
        ftp_years = ftp.nlst()
        ftp_years = [f for f in ftp_years if isInt(f)]

        # First Date
        ftp.cwd(os.path.join('/Projects/LERI/CONUS_archive/data/',
                             ftp_years[0]))
        ftp_files = ftp.nlst()
        ftp_files = [f for f in ftp_files
                     if f[-16:-12] == "{:02d}mn".format(scale)]
        ftp_first = ftp_files[0]
        first_date = pd.to_datetime(ftp_first[-11:-3], format='%Y%m%d')

        # Last Date
        ftp.cwd(os.path.join('/Projects/LERI/CONUS_archive/data/',
                             ftp_years[-1]))
        ftp_files = ftp.nlst()
        ftp_files = [f for f in ftp_files
                     if f[-16:-12] == "{:02d}mn".format(scale)]
        ftp_last = ftp_files[-1]
        last_date = pd.to_datetime(ftp_last[-11:-3], format='%Y%m%d')

        # All dates available
        available_dates = pd.date_range(first_date, last_date, freq='M')

        # Get needed dates
        needed_dates = [a for a in available_dates if
                        a not in existing_dates]

        # Download missing files
        if len(needed_dates) > 0:
            print_statement = '{} missing file(s) since {}...\n'
            print(print_statement.format(len(needed_dates),
                                         needed_dates[0]))

            for date in tqdm(needed_dates, position=0):
                ftp.cwd(os.path.join('/Projects/LERI/CONUS_archive/data/',
                                     str(date.year)))

                # This returns the filename of the downloaded asc file
                in_path = getLERI(scale, date, temp_folder)

                # Save each to a geotiff to use the netcdf builders
                file_name = ('leri_' + str(date.year) +
                             '{:02d}'.format(date.month) + '.tif')
                out_path = os.path.join(temp_folder, file_name)
                tif_path = out_path

                # Resample each, working from disk
                ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326',
                               xRes=res, yRes=res, outputBounds=[-130, 20,
                                                                 -55, 50])
                del ds

                # Reproject the output from above
                in_path = out_path
                out_path = os.path.join(temp_folder, 'proj_' + file_name)
                tif_path_proj = out_path
                ds = gdal.Warp(out_path, in_path, dstSRS=proj)
                del ds

                # Open old data sets
                old = Dataset(original_path, 'r+')
                old_proj = Dataset(albers_path, 'r+')
                times = old.variables['time']
                times_proj = old_proj.variables['time']
                values = old.variables['value']
                values_proj = old_proj.variables['value']
                n = times.shape[0]

                # Convert new date to days
                date = dt.datetime(date.year, date.month, day=15)
                days = date - dt.datetime(1900, 1, 1)
                days = np.float64(days.days)

                # Convert new data to array
                base_data = gdal.Open(tif_path)
                base_data_proj = gdal.Open(tif_path_proj)
                array = base_data.ReadAsArray()
                array_proj = base_data_proj.ReadAsArray()
                del base_data
                del base_data_proj

                # Write changes to file and close
                times[n] = days
                times_proj[n] = days
                values[n] = array
                values_proj[n] = array_proj
                old.close()
                old_proj.close()

            # Now recreate the entire percentile data set
            print('Reranking percentiles...')
            pc_path = os.path.join(pc_folder, index + '.nc')    
            os.remove(pc_path)
            toNetCDFPercentile(original_path, pc_path)  

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
        available_dates = pd.date_range(date1, date2, freq='M')

        # Loop through these, download and transform data
        for date in tqdm(available_dates, position=0):
            ftp.cwd(os.path.join('/Projects/LERI/CONUS_archive/data/',
                                 str(date.year)))
            in_path = getLERI(scale, date, temp_folder)

            # The are rather large files, this could take a while
            out_file = ('temp_' + str(date.year) +
                        '{:02d}'.format(date.month) + '.tif')
            out_path = os.path.join(temp_folder, out_file)
            tif_path = out_path

            # Resample each, working from disk
            ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326', xRes=res,
                           yRes=res, outputBounds=[-130, 20, -55, 50])
            del ds
            os.remove(in_path)

            # Resample
            in_path = tif_path
            out_file = ('proj_temp_' + str(date.year) +
                        '{:02d}'.format(date.month) + '.tif')
            out_path = os.path.join(temp_folder, out_file)            
            ds = gdal.Warp(out_path, in_path, dstSRS=proj)
            del ds

        # Merge individual tif files into a single netcdf file
        tfiles = glob(os.path.join(temp_folder, 'temp_*'))
        tfiles_proj = glob(os.path.join(temp_folder, 'proj_*'))
        ncdir = os.path.join(data_path, "data/droughtindices/netcdfs/",
                              index + ".nc")
        ncdir_proj = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/albers",
                                  index + ".nc")

        # Finally save to file
        toNetCDF(tfiles=tfiles, ncfiles=None, savepath=ncdir, index=index,
                 year1=1980, month1=1, year2=todays_date.year,
                 month2=todays_date.month, epsg=4326, percentiles=False,
                 wmode='w')

        # Save another projected version
        toNetCDFAlbers(tfiles=tfiles_proj, ncfiles=None, savepath=ncdir_proj,
                       index=index, year1=1980, month1=1,
                       year2=todays_date.year, month2=todays_date.month,
                       epsg=proj, percentiles=False, wmode='w')

        # Now lets get the percentile values
        pc_path = os.path.join(data_path, "data/droughtindices/netcdfs/" +
                               "percentiles", index + ".nc")
        toNetCDFPercentile(ncdir, pc_path)

# Close connection with FTP server
ftp.quit()

print("Update Complete.")
print("####################################################")
print("#######################################")
print("#######################")
print("############")
print("#####")
print("##")
