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
from osgeo import gdal
from inspect import currentframe, getframeinfo
import numpy as np
import os
import pandas as pd
import sys
import scipy
from tqdm import tqdm
import xarray as xr

# Set working directory. Where should this go?
f = getframeinfo(currentframe()).filename
p = os.path.dirname(os.path.abspath(f))  # Not working consistently

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    sys.path.extend(['Z:/Sync/Ubuntu-Practice-Machine/',
                     'C:/Users/travi/github/Ubuntu-Practice-Machine'])
    data_path = 'f:/'
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')
    data_path = '/root/Sync'

import functions
from functions import Index_Maps, readRaster, percentileArrays

# In[] Data source and target directory
ftp_path = 'ftp://ftp.cdc.noaa.gov/Projects/EDDI/CONUS_archive/data'
save_folder = os.path.join(data_path, 'data/droughtindices/ascs')
if not os.path.exists(save_folder):
    os.makedirs(save_folder)
mask = readRaster(os.path.join(data_path, 'data/droughtindices/prfgrid.tif'),
                  1, -9999)[0]

# In[] Today's date, month, and year
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)

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
    print(index)
    original_path = os.path.join(data_path,
                                 "data/droughtindices/netcdfs/",
                                 index + '.nc')
    percentile_path = os.path.join(data_path,
                                   "data/droughtindices/netcdfs/percentiles",
                                   index + '.nc')
    scale = int(index[-1:])
    try:
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
        
    except:  # There is a quicker qay to do this surely
        print(original_path + " not detected, building new dataset...")
        lons = np.linspace(-130.0, -55.25, 300, dtype=np.float32)
        lats = np.linspace(50.0, 20.25, 120, dtype=np.float32)
        old = [xr.DataArray(data=mask,  # It may also be possible to append
                            coords={'lat': lats,
                                    'lon': lons,                                        
                                    'time': today},
                             dims=('lat', 'lon'),
                             attrs={'units': 'unitless',
                                    'long_name': 'Index Value',
                                    'standard_name': 'index'})]
        existing_dates = []
        new_file = True

    # 2: Get a list of the dates available for download
    def isInt(string):
        try:
            int(string)
            return True
        except:
            return False

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
    available_dates = pd.date_range(first_date,
                                    last_date,
                                    freq='M')

    # 3: Get the list of dates we don't yet have
    needed_dates = [d for d in available_dates if d not in existing_dates]
    if len(needed_dates) > 0:
        print_statement = '{} missing file(s) since {}, adding data now...'
        print(print_statement.format(len(needed_dates), needed_dates[0]))
    else:
        print('No missing files.')

    # Loop through these dates, build the query and download data
    for date in tqdm(needed_dates, position=0):
        ftp.cwd(os.path.join('/Projects/EDDI/CONUS_archive/data/',
                             str(date.year)))
        file_path = getEDDI(scale, date, save_folder,
                       write=True)
        
        # Resample, working from disk
        temp_path = os.path.join(save_folder, 'temp.tif')
        ds = gdal.Warp(temp_path, file_path,
                       dstSRS='EPSG:4269',
                       xRes=0.25, yRes=0.25,
                       outputBounds=[-130, 20, -55, 50])
        del ds

        # Okay, read the new data from the raster made above
        array = readRaster(temp_path, 1, -9999)[0]
        
        # Use one of the old data arrays as a template
        new = old[-1].copy()

        # Assign new value and date to the template
        new.data = array
        new.time.data = date

        # Add the new to the old
        old.append(new)

    # If it is a new file, knock off the sample
    if new_file:
        old.pop(0)

    # And concatenate everything back together
    new = xr.concat(old, dim='time')
    
    # Before we package this up, create a title
    title = 'Evaporative Demand Drought Index - {} month'.format(scale)
    subtitle = 'Monthly Index Values since 1980-01-31'
    new = xr.Dataset(data_vars={'value': new},
                     attrs={'title': title, 'subtitle': subtitle})

    # Write this back to a netcdf file
    new.to_netcdf(original_path, mode='w')

    # It appears to be possible to append data to the file itself, 
    # though that probably requires an exact structure match
    # Appending * to the existing dataset would look like this:
    # *.to_netcdf(original_path, mode='a')

    # Now, recalculate percentiles for the new dataset. 
    arraylist = new.value.data
    percentiles = new.copy()    
    arraylist = percentileArrays(arraylist)    
    percentiles.value.data = arraylist
    percentiles.to_netcdf(percentile_path, mode='w')

# Close connection with FTP server
ftp.quit()

