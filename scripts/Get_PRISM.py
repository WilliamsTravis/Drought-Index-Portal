# -*- coding: utf-8 -*-
"""
To get temperature and precipitation data directly from PRSIM

Created on Sun May 12 09:36:50 2019

@author: User
"""

import datetime as dt
import os
import pathlib
import sys
import zipfile

import ftplib
import numpy as np
import pandas as pd
import xarray as xr

from glob import glob
from osgeo import gdal
from netCDF4 import Dataset
from tqdm import tqdm


# In[] Set up working environment
PWD = str(pathlib.Path('__file__').parent.absolute())
DATA_PATH = os.path.abspath(os.path.join(PWD, ".."))
sys.path.insert(0, DATA_PATH)

from functions import isInt, toNetCDF, toNetCDFAlbers, toNetCDFPercentile

# gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'

# There are often missing epsg codes in the gcs.csv file, but proj4 works
PROJ = ('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 +lon_0=-96 +x_0=0 +y_0=0 ' +
        '+ellps=GRS80 +datum=NAD83 +units=m no_defs')

# Get resolution from file call
try:
    res = float(sys.argv[1])
except:
    res = 0.25


# We'll need todays date
TODAYS_DATE = dt.datetime.today()
TODAY = np.datetime64(TODAYS_DATE)


# In[] Data source and target directory
TEMP_FOLDER = os.path.join(DATA_PATH, 'data/droughtindices/netcdfs/prism')
TIF_FOLDER = os.path.join(TEMP_FOLDER, 'tifs')

os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(TIF_FOLDER, exist_ok=True)

# In[] Data options
VARIABLES = ['tmin', 'tmax', 'tdmean', 'tmean', 'ppt', 'vpdmax', 'vpdmin']

# In[] Define scraping routine
def getPRISM(filename, TEMP_FOLDERz, ftp):
    '''
    These come as BILs (band interleaved by line) in zipped folders. So we
    retrieve them in the same way as ascs, geotiffs, or netcdfs, but then we
    will need to unzip before moving on to the netcdf building steps. Each
    folder contains the monthly files for the year.
    '''
    local_file = open(os.path.join(TEMP_FOLDER, 'prism.zip'), 'wb')

    def writeline(line):
        local_file.write(line + "\n")
    
    try:
        ftp.retrbinary('RETR ' + filename, local_file.write)
    except Exception as e:
        print(e)
        pass

    local_file.close()

    return os.path.join(TEMP_FOLDER, 'prism.zip')


def build(variable, ftp):
    """
    Build a new set of netcdf datasets with entries from its FTP server.

    Parameters
    ----------
    variable : str
        Name of the dataset variable to be updated.
    ftp : ftplib.FTP
        An FTP connection to the PRISM data server.

    Returns
    -------
    None.
    """

    # Get all three data et paths
    original_path = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/",
                                 variable + '.nc')
    albers_path = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/albers",
                               variable + '.nc')
    percentile_path = os.path.join(DATA_PATH,
                                   "data/droughtindices/netcdfs/percentiles",
                                   variable + '.nc')    

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
            temp_path = getPRISM(filename, TEMP_FOLDER, ftp)

            # Unzip
            zref = zipfile.ZipFile(temp_path, 'r')
            zref.extractall(TEMP_FOLDER)                
            zref.close()

            # Transform BILS
            bils = glob(os.path.join(TEMP_FOLDER, '*bil'))
            bils = [b for b in bils if '_' + year + '_' not in b] # monthly
            for b in bils:
                in_path = b
                month = b[-10: -8]
                tif_file = variable + '_' + year + month + '.tif'
                out_path = os.path.join(TIF_FOLDER, tif_file)
                ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326',
                               xRes=res, yRes=res, outputBounds=[-130, 20,
                                                                 -55,50])
                ds = None

            # Delete existing contents of temporary folder
            temps = glob(os.path.join(TEMP_FOLDER, "*"))
            for t in temps:
                if t != TIF_FOLDER:
                    os.remove(t)

        else:
            files = [f for f in files if '_' + year + '_' not in f]
            for f in files:
                temp_path = getPRISM(f, TEMP_FOLDER, ftp)

                # Unzip
                zref = zipfile.ZipFile(temp_path, 'r')
                zref.extractall(TEMP_FOLDER)                
                zref.close()

                # Transform                    
                in_path = glob(os.path.join(TEMP_FOLDER, '*bil'))[0]
                month = in_path[-10: -8]
                tif_file = variable + '_' + year + month + '.tif'
                out_path = os.path.join(TIF_FOLDER, tif_file)
                ds = gdal.Warp(out_path, in_path, dstSRS='EPSG:4326',
                               xRes=res, yRes=res, outputBounds=[-130, 20,
                                                                 -55,50])
                ds = None

            # Delete existing contents of temporary folder
            temps = glob(os.path.join(TEMP_FOLDER, "*"))
            for t in temps:
                if t != TIF_FOLDER:
                    os.remove(t)

    # Now we can use the folder of tifs, first create projections
    for f in glob(os.path.join(TIF_FOLDER, '*tif')):
        filename = os.path.split(f)[-1]
        in_path = f
        out_path = os.path.join(TIF_FOLDER, 'proj_' + filename)
        ds = gdal.Warp(out_path, in_path, dstSRS=PROJ)
        ds = None

    # Now create the three netcdf files
    tfiles = glob(os.path.join(TIF_FOLDER, variable + '*'))
    tfiles_proj = glob(os.path.join(TIF_FOLDER, 'proj_*'))

    # Original
    toNetCDF(tfiles=tfiles, ncfiles=None, savepath=original_path,
             index=variable, proj=4326, year1=1895, month1=1,
             year2=TODAYS_DATE.year - 2,  month2=12, wmode='w',
             percentiles=False)
    toNetCDFAlbers(tfiles=tfiles_proj, ncfiles=None,
                   savepath=albers_path, index=variable, proj=PROJ,
                   year1=1895, month1=1, year2=TODAYS_DATE.year - 2, # <--- for testing update mode
                   month2=12, wmode='w', percentiles=False) 
    toNetCDFPercentile(original_path, percentile_path)

    # Empty tif folder
    for t in glob(os.path.join(TIF_FOLDER, '*')):
        os.remove(t)


def update(variable, ftp):  # <------------------------------------------------ Somethings broken
    """
    Update an existing netcdf dataset with new entries from its FTP server.

    Parameters
    ----------
    variable : str
        Name of the dataset variable to be updated.
    ftp : ftplib.FTP
        An FTP connection to the PRISM data server.

    Returns
    -------
    None.
    """       

    # Get all three data et paths
    original_path = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/",
                                 variable + '.nc')
    albers_path = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/albers",
                               variable + '.nc')
    percentile_path = os.path.join(DATA_PATH,
                                   "data/droughtindices/netcdfs/percentiles",
                                   variable + '.nc')

    # Make sure we're in the right ftp directory
    ftp.cwd('/monthly/' + variable)

    # Open the original
    with xr.open_dataset(original_path) as data:
        dates = pd.DatetimeIndex(data.time.data)

    # Get all available years
    ftp_years = ftp.nlst()
    ftp_years = [f for f in ftp_years if isInt(f)]
    ftp_years.sort()

    # Find the most recently available ftp file
    ftp.cwd('/monthly/' + variable + '/' + max(ftp_years))
    ftp_files = ftp.nlst()
    ftp_dates = [f[-14:-8] for f in ftp_files] 
    most_recent = dt.datetime.strptime(max(ftp_dates), "%Y%m")
    most_recent = pd.Timestamp(most_recent)
    first = dates[-1] + pd.DateOffset(months=1)
    needed_dates = pd.date_range(first, most_recent, freq="MS")
    needed_years = np.unique([d.year for d in needed_dates])
    needed_years.sort()
    needed = {}
    for y in needed_years:
        months = [t.month for t in needed_dates if t.year == y]
        needed[y] = months

    for year, months in needed.items():
        syear = str(year)
        smonths = ["{:02d}".format(m) for m in months]
        smonths.sort()
        ftp.cwd('/monthly/' + variable + '/' + syear)
        files = ftp.nlst()
        files = [f for f in files if '_' + syear + '_' not in f]
        sorted_files = []
        for m in smonths:
            for f in files:
                if f[-10:-8] == m:
                    sorted_files.append(f)

        for f in sorted_files:
            for e in glob(os.path.join(TEMP_FOLDER, "*bil")):
                os.remove(e)
    
            temp_path = getPRISM(f, TEMP_FOLDER, ftp)

            # Unzip
            zref = zipfile.ZipFile(temp_path, 'r')
            zref.extractall(TEMP_FOLDER)                
            zref.close()

            # Transform                    
            in_path = glob(os.path.join(TEMP_FOLDER, '*bil'))[0]
            month = in_path[-10: -8]
            tif_file = variable + '_' + syear + month + '.tif'
            wgs_path_temp = os.path.join(TIF_FOLDER, tif_file)
            ds = gdal.Warp(wgs_path_temp, in_path, dstSRS='EPSG:4326', xRes=res,
                           yRes=res, outputBounds=[-130, 20, -55,50])
            ds = None

            albers_path_temp = wgs_path_temp.replace(".tif", "_albers.tif")
            ds = gdal.Warp(albers_path_temp, wgs_path_temp, dstSRS=PROJ)
            ds = None

            # Update WGS
            with Dataset(original_path, 'r+') as old:
                times = old.variables['time']
                values = old.variables['value']
                n = times.shape[0]
                base_data = gdal.Open(wgs_path_temp)
                array = base_data.ReadAsArray()
                del base_data

                # Catch the day                    
                date = dt.datetime(year, int(month), day=15)
                days = date - dt.datetime(1900, 1, 1)
                days = np.float64(days.days)

                # Write changes to file and close
                times[n] = days
                values[n] = array

            # Open old data sets
            with Dataset(albers_path, 'r+') as old:
                times = old.variables['time']
                values = old.variables['value']
                n = times.shape[0]
                base_data = gdal.Open(albers_path_temp)
                array = base_data.ReadAsArray()
                del base_data

                # Catch the day                    
                date = dt.datetime(year, int(month), day=15)
                days = date - dt.datetime(1900, 1, 1)
                days = np.float64(days.days)

                # Write changes to file and close
                times[n] = days
                values[n] = array

    # Reset the percentiles file
    toNetCDFPercentile(original_path, percentile_path)


def main():

    # Do I really want to print all of the out?
    print("##")
    print("#####")
    print("############")
    print("#######################")
    print("#######################################")
    print("####################################################")
    print("\nRunning Get_PRISM.py using a " + str(res) +
          " degree resolution:\n")
    print(str(TODAY) + '\n')

    # Connect to FTP 
    ftp = ftplib.FTP('prism.nacse.org', 'anonymous',
                     'anonymous@prism.nacse.org')

    # One variable at a time for now
    for variable in VARIABLES:
        print('\n' + variable)

        # Delete existing contents of temporary folder
        temps = glob(os.path.join(TEMP_FOLDER, "*"))
        for t in temps:
            if t != TIF_FOLDER:
                os.remove(t)

        # Empty tif folder
        for t in glob(os.path.join(TIF_FOLDER, '*')):
            os.remove(t)

        # The first resulting file path
        original_path = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/",
                                     variable + '.nc')

        # If we are only missing some dates
        if os.path.exists(original_path):
            print(original_path + " detected, checking for updates ...\n")
            try:
                update(variable, ftp)
            except TimeoutError:
                print("Timeout error, try again later...")
                pass

        # If we need to start over
        else:
            print(original_path + " not detected, building new dataset...\n")
            try:
                build(variable, ftp)
            except TimeoutError:
                print("Timeout error, try again later... ")
                pass


    # Close FTP connection
    ftp.close()

    print("\n Get_PRISM.py completed.")
    print("####################################################")
    print("#######################################")
    print("#######################")
    print("############")
    print("#####")
    print("##")


if __name__ == "__main__":
    main()
