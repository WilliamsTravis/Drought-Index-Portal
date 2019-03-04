# -*- coding: utf-8 -*-
"""

    Updating EDDI on a monthly basis.

    Target Functionality:
    So using either crontab and letting it
    go on the virtual machine, or finding a hybrid approach, every month this
    will pull the asc file from the NOAA's EDDI server, transform it, and
    append it to the netcdf file of original values. It will also need to
    rebuild the entire percentile netcdf because that is rank based. It will
    also need to update the script to allow for new dates.

    Production Notes:
    So this accomplishes the goal, but rather clumsily. If there are no needed
    entries it should skip each index as soon as it knows. This doesn't really
    matter because the script will be run a scheduler set for a few days after
    data is published, but there could be instances where this matters. Also,
    it should be possible to simply append a new entry to the old file on the
    disk and skip the longer process here. That just requires me to get the
    entry dataset to match the netcdf structure. If a new dataset needs to be
    built it applies the same workflow as if only one entry needs to be added.
    I think it may be way quicker to download, or just load, each file to the
    machine at once, then build the xarray dataset all at once, rather than
    perform the whole process file by file.

Created on Fri Feb  1 14:33:38 2019

@author: User
"""
import calendar
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

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    sys.path.extend(['C:/Users/User/github/Ubuntu-Practice-Machine',
                     'C:/Users/travi/github/Ubuntu-Practice-Machine'])
    data_path = 'f:/'
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')
    data_path = '/root/Sync'

from functions import Index_Maps, readRaster, percentileArrays, im, isInt
from netCDF_functions import toNetCDF2, toNetCDF3
# gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# In[] Data source and target directory
ftp_path = 'ftp://ftp.cdc.noaa.gov/Projects/EDDI/CONUS_archive/data'
save_folder = os.path.join(data_path, 'data/droughtindices/temps')
if not os.path.exists(save_folder):
    os.makedirs(save_folder)
# mask = readRaster(os.path.join(data_path, 'data/droughtindices/prfgrid.tif'),
#                   1, -9999)[0]

# In[] Today's date, month, and year
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)
print("##")
print("#####")
print("############")
print("#######################")
print("#######################################")
print("####################################################")
print("\nRunning Get_EDDI.py:")
print(str(today) + '\n')

# In[] Index options
indices = ['eddi1', 'eddi2', 'eddi3', 'eddi6']

# In[] Define scraping routine
def getEDDI(scale, date, save_folder, write=False):
    '''
    These come out daily, but each represents the accumulated conditions of the 
    prior 30 days. Since we want one value per month we are only downloading
    the last day of the month. I'm not sure whether it will be possible to 
    append this directly to an exiting netcdf or if we need to write to a file
    first.
    '''
    year = date.year
    month = date.month
    last_day = calendar.monthrange(year, month)[1]

    if not write:
        memory_file = []
        def appendline(line):
            memory_file.append(line)
        try:
            file_name = 'EDDI_ETrs_{:02d}mn_{}{:02d}{}.asc'.format(scale, year,
                                                               month, last_day)
            ftp.retrlines('RETR ' + file_name, appendline)
        except:
            file_name = 'EDDI_ETrs_{:02d}mn_{}{:02d}{}.asc'.format(scale, year,
                                                             month, last_day-1)
            ftp.retrlines('RETR ' + file_name, appendline)

        return memory_file

    else:
        def writeline(line):
            local_file.write(line + "\n")
        local_file = open(os.path.join(save_folder, 'temp.asc'), 'w')
        try:
            file_name = 'EDDI_ETrs_{:02d}mn_{}{:02d}{}.asc'.format(scale, year,
                                                               month, last_day)
            ftp.retrlines('RETR ' + file_name, writeline)
        except:
            file_name = 'EDDI_ETrs_{:02d}mn_{}{:02d}{}.asc'.format(scale, year,
                                                           month, last_day - 1)
            ftp.retrlines('RETR ' + file_name, writeline)
        local_file.close()
        return os.path.join(save_folder, 'temp.asc')


# In[] Get time series of currently available values
# Connect to FTP 
ftp = ftplib.FTP('ftp.cdc.noaa.gov', 'anonymous', 'anonymous@cdc.noaa.gov')
for index in indices:
    ftp.cwd('/Projects/EDDI/CONUS_archive/data/')  # sample
    print('\n' + index)
    original_path = os.path.join(data_path,
                                 "data/droughtindices/netcdfs/",
                                 index + '.nc')
    percentile_path = os.path.join(data_path,
                                   "data/droughtindices/netcdfs/percentiles",
                                   index + '.nc')
    scale = int(index[-1:])

    if os.path.exists(original_path):   # Create a netcdf and append to file
        with xr.open_dataset(original_path) as data:
            indexlist = data.load()
            data.close()
        
        # Extract dates
        dates = pd.DatetimeIndex(indexlist.time.data)
        d1 = dates[0]
        d2 = dates[-1]
    
        # Get a list of the dates already in the netcdf file
        existing_dates = pd.date_range(d1, d2, freq="M")
        
        # Now break the old dataset apart
        old = [indexlist.value[i] for i in range(len(indexlist.value))]
        
        # Is this a new or old data set?
        new_file = False

    else:
        ############## If we need to start over #######################
        print(original_path + " not detected, building new dataset...\n")

        # Get all of the last day of month files for the index
        ftp_years = ftp.nlst()
        ftp_years = [f for f in ftp_years if isInt(f)]

        # First Date
        ftp.cwd(os.path.join('/Projects/EDDI/CONUS_archive/data/',
                             ftp_years[0]))
        ftp_files = ftp.nlst()
        ftp_files = [f for f in ftp_files
                     if f[-17:-13] == "{:02d}mn".format(scale)]
        ftp_first = ftp_files[0]
        first_date = pd.to_datetime(ftp_first[-12:-4], format='%Y%m%d')

        # Last Date
        ftp.cwd(os.path.join('/Projects/EDDI/CONUS_archive/data/',
                             ftp_years[-1]))
        ftp_files = ftp.nlst()
        ftp_files = [f for f in ftp_files
                     if f[-17:-13] == "{:02d}mn".format(scale)]
        ftp_last = ftp_files[-1]
        last_date = pd.to_datetime(ftp_last[-12:-4], format='%Y%m%d')

        # All dates available
        available_dates = pd.date_range(first_date, last_date, freq='M')

        
        # Loop through these dates, build the query and download data
        for date in tqdm(available_dates, position=0):
            ftp.cwd(os.path.join('/Projects/EDDI/CONUS_archive/data/',
                                 str(date.year)))
            file_path = getEDDI(scale, date, save_folder,
                           write=True)

            # We will save each to a geotiff so we can use the netcdf builders
            # These will be overwritten for space
            file_name = ('eddi_' + str(date.year) +
                         '{:02d}'.format(date.month) + '.tif')
            tif_path = os.path.join(save_folder, file_name)

            # Resample each, working from disk
            ds = gdal.Warp(tif_path, file_path,
                           dstSRS='EPSG:4326',
                           xRes=0.25, yRes=0.25,
                           outputBounds=[-130, 20, -55, 50])
            del ds

        # There are over four hundred of those, this will take a minute. Run it
        # After Get_WWDT.py just in case. If either of these break I should
        # have a contingency exception. 

        # Now, run a toNetCDF using the available dates instead of an existing
        # netcdf file. I should tweak toNetCDF2 to accept either I think.
        # Pardon this expediency
        tfiles = glob(os.path.join(save_folder, '*tif'))
        ncdir = os.path.join(data_path, "data/droughtindices/netcdfs/",
                              index + '.nc')
        toNetCDF2(tfiles=tfiles, ncfiles=None, savepath=ncdir, index=index,
                  year1=1980, month1=1, year2=todays_date.year, month2=12,
                  epsg=4326, percentiles=False, wmode='w')

        # Now lets get the percentile values
        ncdir_perc = os.path.join(data_path, "data/droughtindices/netcdfs/" +
                                   "percentiles", index + '.nc')
        toNetCDF2(tfiles=tfiles, ncfiles=None, savepath=ncdir_perc,
                  index=index, year1=1980, month1=1, year2=todays_date.year,
                  month2=12, epsg=4326, percentiles=True, wmode='w')

        # Now we need projected rasters, we can do this from the nc above
        # Warp to albers equal area conic as a geotiff because ncdf flips axis
        # inpath = ncdir
        # outpath = os.path.join(data_path, 'data/droughtindices/netcdfs/albers',
        #                        index + '.tif')
        # if os.path.exists(outpath):
        #     os.remove(outpath)
        # ds = gdal.Warp(outpath, inpath, srcSRS='EPSG:4326', dstNodata = -9999,
        #                dstSRS='EPSG:102008')
        # del ds

        # # The format is off, so let's build another netcdf from the tif above
        # tfile = outpath
        # ncfile = ncdir
        # savepath = os.path.join(
        #         data_path, 'data/droughtindices/netcdfs/albers', index + '.nc')
        # toNetCDF3(tfile, ncfile, savepath, index, epsg=102008, wmode='w',
        #           percentiles=False)

# Close connection with FTP server
ftp.quit()

print("Update Complete.")
print("####################################################")
print("#######################################")
print("#######################")
print("############")
print("#####")
print("##")
