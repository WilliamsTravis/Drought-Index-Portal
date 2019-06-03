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
elif 'travis' in os.getcwd():
    sys.path.insert(0, '/home/travis/github/Ubuntu-Practice-Machine')
    os.chdir('/home/travis/github/Ubuntu-Practice-Machine')
    data_path = '/media/travis/My Passport/'
else:
    sys.path.insert(0, '/root/Sync/Ubuntu-Practice-Machine')
    os.chdir('/root/Sync/Ubuntu-Practice-Machine')
    data_path = '/root/Sync'

from functions import isInt, readRaster, toNetCDF, toNetCDFAlbers
from functions import toNetCDFPercentile, toRaster


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
temp_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/leri')
pc_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/percentiles')
if not os.path.exists(temp_folder):
    os.makedirs(temp_folder)
if not os.path.exists(pc_folder):
    os.makedirs(pc_folder)

# In[] Index Options
indices = ['leri1', 'leri3']

# In[] Define scraping routine
def getLERI(file_name, temp_folder):
    '''
    The date in the file name always uses the first day of the month.
    '''
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
    try:
        ftp.cwd('/Projects/LERI/CONUS_archive/data/time_series/LERI_INDEX/')
    except:
        ftp = ftplib.FTP('ftp.cdc.noaa.gov', 'anonymous',
                         'anonymous@cdc.noaa.gov')
        ftp.cwd('/Projects/LERI/CONUS_archive/data/time_series/LERI_INDEX/')
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

        # Not ready yet
        print("Update mode not available yet")


    ############## If we need to start over ###################################
    else:
        ftp.cwd('/Projects/LERI/CONUS_archive/data/time_series/LERI_INDEX/')
        print(original_path + " not detected, building new dataset...\n")

        # Get all available files
        files = ftp.nlst()

        # Filter for the desired time-scale
        files = [f for f in files if int(f[-12:-10]) == scale]

        # Loop through these files, download and transform data
        for file in tqdm(files, position=0):
            try:
                in_path = getLERI(file, temp_folder)
            except:
                ftp = ftplib.FTP('ftp.cdc.noaa.gov', 'anonymous',
                                 'anonymous@cdc.noaa.gov')
                ftp.cwd('/Projects/LERI/CONUS_archive/data/time_series/LERI_INDEX/')
                in_path = getLERI(file, temp_folder)
            year = file[-7: -3]

            # The are rather large files, this could take a while
            out_file = 'temp_' + year + '.tif'
            out_path = os.path.join(temp_folder, out_file)

            # Resample each, working from disk
            ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326', xRes=res,
                           yRes=res, outputBounds=[-130, 20, -55, 50],
                           dstNodata=9999)
            del ds
            os.remove(in_path)

            # Resample
            in_path = out_path
            out_file = 'proj_' + out_file
            out_path = os.path.join(temp_folder, out_file)            
            ds = gdal.Warp(out_path, in_path, dstSRS=proj)
            del ds

        # Now that we have all of the tif files, we can split them into months
        tfiles = glob(os.path.join(temp_folder, 'temp*'))
        pfiles = glob(os.path.join(temp_folder, 'proj*')) 
        for f in tfiles:
            year = f[-8: -4]
            for i in range(1, 13):
                month = '{:02d}'.format(i)
                new_name = 'temp_' + year + month + '.tif'
                new_file = os.path.join(temp_folder, new_name)
                band, geom, proj = readRaster(f, i)
                band[band == 9999.] = -9999
                toRaster(band, new_file, geom, proj)

            # As we're finished we can remove the larger tifs
            os.remove(f)

        for f in pfiles:
            year = f[-8: -4]
            for i in range(1, 13):
                month = '{:02d}'.format(i)
                new_name = 'proj_temp_' + year + month + '.tif'
                new_file = os.path.join(temp_folder, new_name)
                band, geom, proj = readRaster(f, i)
                band[band > 9000.] = -9999
                toRaster(band, new_file, geom, proj)
            os.remove(f)

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
                 month2=todays_date.month, proj=4326, percentiles=False,
                 wmode='w')

        # Save another projected version
        toNetCDFAlbers(tfiles=tfiles_proj, ncfiles=None, savepath=ncdir_proj,
                       index=index, year1=1980, month1=1,
                       year2=todays_date.year, month2=todays_date.month,
                       proj=proj, percentiles=False, wmode='w')

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
