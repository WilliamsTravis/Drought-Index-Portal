# -*- coding: utf-8 -*-
"""

    Updating EDDI on a monthly basis.

    Run this using crontab once a month this to pull netcdf files from the
    NOAA's PSD FTP server, transform them to fit in the app, and either
    append them to an existing file, or build the data set from scratch. This
    also rebuilds each percentile netcdf entirely because those are rank based.

    For more information check Get_WWDT.py

Created on Fri Feb  10 14:33:38 2019

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
    sys.path.insert(0, 'C:/Users/User/github/Ubuntu-Practice-Machine')
    os.chdir('C:/Users/User/github/Ubuntu-Practice-Machine')
    data_path = 'f:/'
elif 'travis' in os.getcwd():
    os.chdir('/home/travis/github/Ubuntu-Practice-Machine')
    data_path = ''
else:
    sys.path.insert(0, '/root/Sync/Ubuntu-Practice-Machine')
    os.chdir('/root/Sync/Ubuntu-Practice-Machine')
    data_path = '/root/Sync'

from functions import isInt, toNetCDF, toNetCDFAlbers, toNetCDFPercentile

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
ftp_path = 'ftp://ftp.cdc.noaa.gov/Projects/EDDI/CONUS_archive/data'
temp_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/eddi')
pc_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/percentiles')
if not os.path.exists(temp_folder):
    os.makedirs(temp_folder)
if not os.path.exists(pc_folder):
    os.makedirs(pc_folder)

# In[] Index options
indices = ['eddi1', 'eddi2', 'eddi3', 'eddi4', 'eddi5', 'eddi6', 'eddi7',
           'eddi8', 'eddi9', 'eddi10', 'eddi11', 'eddi12']

# In[] Define scraping routine
def getEDDI(scale, date, temp_folder, write=False):
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
        local_file = open(os.path.join(temp_folder, 'eddi.asc'), 'w')
        try:
            file_name = 'EDDI_ETrs_{:02d}mn_{}{:02d}{}.asc'.format(scale, year,
                                                               month, last_day)
            ftp.retrlines('RETR ' + file_name, writeline)
        except:
            file_name = 'EDDI_ETrs_{:02d}mn_{}{:02d}{}.asc'.format(scale, year,
                                                           month, last_day - 1)
            ftp.retrlines('RETR ' + file_name, writeline)
        local_file.close()
        return os.path.join(temp_folder, 'eddi.asc')


# In[] Today's date, month, and year
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)
print("##")
print("#####")
print("############")
print("#######################")
print("#######################################")
print("####################################################")
print("\nRunning Get_EDDI.py using a " + str(res) + " degree resolution:\n")
print(str(today) + '\n')

# In[] Get time series of currently available values
# Connect to FTP 
ftp = ftplib.FTP('ftp.cdc.noaa.gov', 'anonymous', 'anonymous@cdc.noaa.gov')
for index in indices:
    ftp.cwd('/Projects/EDDI/CONUS_archive/data/')
    print('\n' + index)
    original_path = os.path.join(data_path, "data/droughtindices/netcdfs/",
                                 index + '.nc')
    albers_path = os.path.join(data_path, "data/droughtindices/netcdfs/albers",
                               index + '.nc')
    percentile_path = os.path.join(data_path,
                                   "data/droughtindices/netcdfs/percentiles",
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

        # get needed dates
        needed_dates = [a for a in available_dates if
                        a not in existing_dates]

        # Download new files
        if len(needed_dates) > 0:
            print_statement = '{} missing file(s) since {}...\n'
            print(print_statement.format(len(needed_dates),
                                         needed_dates[0]))

            for date in tqdm(needed_dates, position=0):
                ftp.cwd(os.path.join('/Projects/EDDI/CONUS_archive/data/',
                                     str(date.year)))

                # This returns the filename of the downloaded asc file
                in_path = getEDDI(scale, date, temp_folder, write=True)

                # Save each to a geotiff to use the netcdf builders
                file_name = ('eddi_' + str(date.year) +
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
            in_path = getEDDI(scale, date, temp_folder, write=True)

            # We will save each to a geotiff so we can use the netcdf builders
            file_name = ('temp_' + str(date.year) +
                         '{:02d}'.format(date.month) + '.tif')
            out_path = os.path.join(temp_folder, file_name)
            tif_path = out_path

            # Resample each, working from disk
            ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326',
                           xRes=res, yRes=res,outputBounds=[-130, 20,
                                                            -55,50])
            del ds

            # Reproject output from above
            in_path = out_path
            out_path = os.path.join(temp_folder, 'proj_' + file_name)
            tif_path_proj = out_path
            ds = gdal.Warp(out_path, in_path, dstSRS=proj)
            del ds

        # Now, run toNetCDF using the file name dates.
        tfiles = glob(os.path.join(temp_folder, 'temp_*'))
        tfiles_proj = glob(os.path.join(temp_folder, 'proj_*'))
        nc_path = os.path.join(data_path, "data/droughtindices/netcdfs/",
                               index + ".nc")
        nc_path_proj = os.path.join(data_path,
                                    "data/droughtindices/netcdfs/albers",
                                    index + ".nc")
        toNetCDF(tfiles=tfiles, ncfiles=None, savepath=nc_path, index=index,
                 proj=4326, year1=1980, month1=1, year2=todays_date.year,
                 month2=12, wmode='w', percentiles=False)
        toNetCDFAlbers(tfiles=tfiles_proj, ncfiles=None, savepath=nc_path_proj,
                       index=index, proj=proj, year1=1980, month1=1,
                       year2=todays_date.year, month2=12, wmode='w',                 # I subtracted one to go back and check the update mode
                       percentiles=False)

        # Now lets get the percentile values
        pc_path = os.path.join(data_path, "data/droughtindices/netcdfs/" +
                               "percentiles", index + ".nc")
        toNetCDFPercentile(nc_path, pc_path)

# Close connection with FTP server
ftp.quit()

print("Update Complete.")
print("####################################################")
print("#######################################")
print("#######################")
print("############")
print("#####")
print("##")
