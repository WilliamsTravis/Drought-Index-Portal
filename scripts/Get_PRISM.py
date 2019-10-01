# -*- coding: utf-8 -*-
"""
To get temperature and precipitation data directly from PRSIM

Created on Sun May 12 09:36:50 2019

@author: User
"""

import datetime as dt
import ftplib
from glob import glob
import numpy as np
import os
from osgeo import gdal
import pandas as pd
import sys
from tqdm import tqdm
import xarray as xr
import zipfile

# In[] Set up working environment
# I hadn't learned how to do this yet
if sys.platform == 'win32':
    sys.path.insert(0, 'C:/Users/trwi0358/github/Ubuntu-Practice-Machine')
    os.chdir('C:/Users/trwi0358/github/Ubuntu-Practice-Machine')
    data_path = ''
elif 'travis' in os.getcwd():
    sys.path.insert(0, '/home/travis/github/Ubuntu-Practice-Machine')
    os.chdir('/home/travis/github/Ubuntu-Practice-Machine')
    data_path = ''
else:
    sys.path.insert(0, '/root/Sync/Ubuntu-Practice-Machine')
    os.chdir('/root/Sync/Ubuntu-Practice-Machine')
    data_path = '/root/Sync'

from functions import isInt, meanNC, toNetCDF, toNetCDFAlbers
from functions import toNetCDFPercentile

# gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# There are often missing epsg codes in the gcs.csv file, but proj4 works
proj = ('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 +lon_0=-96 +x_0=0 +y_0=0 ' +
        '+ellps=GRS80 +datum=NAD83 +units=m no_defs')

# Get resolution from file call
try:
    res = float(sys.argv[1])
except:
    res = 0.25

# In[] Data source and target directory
# ftp_path = 'ftp://prism.nacse.org'
temp_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/prism')
tif_folder = os.path.join(temp_folder, 'tifs')
pc_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/percentiles')
if not os.path.exists(temp_folder):
    os.makedirs(temp_folder)
if not os.path.exists(tif_folder):
    os.makedirs(tif_folder)
if not os.path.exists(pc_folder):
    os.makedirs(pc_folder)

# In[] Data options
variables = ['tmin', 'tmax', 'tdmean', 'tmean', 'ppt', 'vpdmax', 'vpdmin']

# In[] Define scraping routine
def getPRISM(filename, temp_folder, ftp):
    '''
    These come as BILs (band interleaved by line) in zipped folders. So we
    retrieve them in the same way as ascs, geotiffs, or netcdfs, but then we
    will need to unzip before moving on to the netcdf building steps. Each
    folder contains the monthly files for the year.
    '''
    local_file = open(os.path.join(temp_folder, 'prism.zip'), 'wb')

    def writeline(line):
        local_file.write(line + "\n")
    
    try:
        ftp.retrbinary('RETR ' + filename, local_file.write)
    except Exception as e:
        print(e)
        pass

    local_file.close()

    return os.path.join(temp_folder, 'prism.zip')

# In[] Today's date, month, and year
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)
print("##")
print("#####")
print("############")
print("#######################")
print("#######################################")
print("####################################################")
print("\nRunning Get_PRISM.py using a " + str(res) + " degree resolution:\n")
print(str(today) + '\n')

# In[] Get time series of currently available values
# Connect to FTP 
ftp = ftplib.FTP('prism.nacse.org', 'anonymous', 'anonymous@prism.nacse.org')
for variable in variables:
    print('\n' + variable)
    ftp.cwd('/monthly/' + variable)
    original_path = os.path.join(data_path, "data/droughtindices/netcdfs/",
                                 variable + '.nc')
    albers_path = os.path.join(data_path, "data/droughtindices/netcdfs/albers",
                               variable + '.nc')
    percentile_path = os.path.join(data_path,
                                   "data/droughtindices/netcdfs/percentiles",
                                   variable + '.nc')

    # Delete existing contents of temporary folder
    temps = glob(os.path.join(temp_folder, "*"))
    for t in temps:
        if t != tif_folder:
            os.remove(t)

    # Empty tif folder
    for t in glob(os.path.join(tif_folder, '*')):
        os.remove(t)

    ####### If we are only missing some dates #################################
    if os.path.exists(original_path):
        with xr.open_dataset(original_path) as data:
            dates = pd.DatetimeIndex(data.time.data)
            data.close()

        print('Update mode is not available yet, del file and start over...')

    ############## If we need to start over ###################################
    else:
        print(original_path + " not detected, building new dataset...\n")
        ftp.cwd('/monthly/' + variable)

        # Get all of the last day of month files for the index
        ftp_years = ftp.nlst()
        ftp_years = [f for f in ftp_years if isInt(f)]
        ftp_years.sort()

        # For each file download, unzip, and transform
        for year in tqdm(ftp_years, position=0):
            ftp.cwd('/monthly/' + variable + '/' + year)
            files = ftp.nlst()

            # Earlier years have everything in one 'all' folder
            if any('all' in f for f in files):
                filename = [f for f in files if 'all' in f][0]
                temp_path = getPRISM(filename, temp_folder, ftp)

                # Unzip
                zref = zipfile.ZipFile(temp_path, 'r')
                zref.extractall(temp_folder)                
                zref.close()

                # Transform BILS
                bils = glob(os.path.join(temp_folder, '*bil'))
                bils = [b for b in bils if '_' + year + '_' not in b] # monthly
                for b in bils:
                    in_path = b
                    month = b[-10: -8]
                    tif_file = variable + '_' + year + month + '.tif'
                    out_path = os.path.join(tif_folder, tif_file)
                    ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326',
                                   xRes=res, yRes=res, outputBounds=[-130, 20,
                                                                     -55,50])
                    ds = None

                # Delete existing contents of temporary folder
                temps = glob(os.path.join(temp_folder, "*"))
                for t in temps:
                    if t != tif_folder:
                        os.remove(t)

            else:
                files = [f for f in files if '_' + year + '_' not in f]
                for f in files:
                    temp_path = getPRISM(f, temp_folder, ftp)

                    # Unzip
                    zref = zipfile.ZipFile(temp_path, 'r')
                    zref.extractall(temp_folder)                
                    zref.close()


                    # Transform                    
                    in_path = glob(os.path.join(temp_folder, '*bil'))[0]
                    month = in_path[-10: -8]
                    tif_file = variable + '_' + year + month + '.tif'
                    out_path = os.path.join(tif_folder, tif_file)
                    ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326',
                                   xRes=res, yRes=res, outputBounds=[-130, 20,
                                                                     -55,50])
                    ds = None

                # Delete existing contents of temporary folder
                temps = glob(os.path.join(temp_folder, "*"))
                for t in temps:
                    if t != tif_folder:
                        os.remove(t)

        # Now we can use the folder of tifs, first create projections
        for f in glob(os.path.join(tif_folder, '*tif')):
            filename = os.path.split(f)[-1]
            in_path = f
            out_path = os.path.join(tif_folder, 'proj_' + filename)
            ds = gdal.Warp(out_path, in_path, dstSRS=proj)
            ds = None

        # Now create the three netcdf files
        tfiles = glob(os.path.join(tif_folder, variable + '*'))
        tfiles_proj = glob(os.path.join(tif_folder, 'proj_*'))

        # Original
        toNetCDF(tfiles=tfiles, ncfiles=None, savepath=original_path,
                 index=variable, proj=4326, year1=1895, month1=1,
                 year2=todays_date.year,  month2=12, wmode='w',
                 percentiles=False)
        toNetCDFAlbers(tfiles=tfiles_proj, ncfiles=None,
                       savepath=albers_path, index=variable, proj=proj,
                       year1=1895, month1=1, year2=todays_date.year,
                       month2=12, wmode='w', percentiles=False)
        toNetCDFPercentile(original_path, percentile_path)

        # Empty tif folder
        for t in glob(os.path.join(tif_folder, '*')):
            os.remove(t)

# One last thing, we only have min and max vapor pressure deficit
meanNC(minsrc='data/droughtindices/netcdfs/albers/vpdmin.nc',
       maxsrc='data/droughtindices/netcdfs/albers/vpdmax.nc',
       dst='data/droughtindices/netcdfs/albers/vpdmean.nc')
meanNC(minsrc='data/droughtindices/netcdfs/percentiles/vpdmin.nc',
       maxsrc='data/droughtindices/netcdfs/percentiles/vpdmax.nc',
       dst='data/droughtindices/netcdfs/percentiles/vpdmean.nc')
meanNC(minsrc='data/droughtindices/netcdfs/vpdmin.nc',
       maxsrc='data/droughtindices/netcdfs/vpdmax.nc',
       dst='data/droughtindices/netcdfs/vpdmean.nc')