# -*- coding: utf-8 -*-
"""
I think I can get solar radiation and wind parameters, these are also variables
that some of the more complex drought indices incorporate.

Created on Sat Aug 10 18:41:24 2019

@author: trwi0358
"""
import warnings
warnings.filterwarnings("ignore")
import datetime as dt
import numpy as np
import os
from osgeo import gdal
import sys
import xarray as xr
import rasterio
from rasterio.enums import Resampling

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
temp_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/gridmet')
day_folder = os.path.join(temp_folder, 'temp')
pc_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/percentiles')
if not os.path.exists(temp_folder):
    os.makedirs(temp_folder)
if not os.path.exists(day_folder):
    os.makedirs(day_folder)
if not os.path.exists(pc_folder):
    os.makedirs(pc_folder)

# In[] Today's date, month, and year
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)
thisyear = todays_date.year
print("##")
print("#####")
print("############")
print("#######################")
print("#######################################")
print("####################################################")
print("\nRunning Get_PRISM.py using a " + str(res) + " degree resolution:\n")
print(str(today) + '\n')

# In[]
# This dataset starts in 1979
years = range(1979, thisyear + 1)

# We can get lots of things, lets just get a few
parameters = ['srad', 'vs', 'th']

# Loop through and get each year through openDAP
for param in parameters:
    param_months = {}
    for year in years:
        print(param + ": " + str(year))
        url = ("http://thredds.northwestknowledge.net:8080/thredds/dodsC/MET/" +
               param + "/" + param + "_" + str(year) + ".nc#fillmismatch")
        data = xr.open_dataset(url)
        varname = list(data.data_vars.items())[0][0]

        # We are going to average by month and flatten all months into one
        data = data.resample(day='M').mean()

        # I'll learn in memory resolution resampling later
        out_path = os.path.join(day_folder, str(year) + "_highres.nc")
        data.to_netcdf(path=out_path)

        # Resample from disk
        new_path = os.path.join(day_folder, str(year) + "_lowres.nc")
        ds = gdal.Warp(new_path, out_path, dstSRS='EPSG:4326',
                        xRes=res, yRes=res, outputBounds=[-130, 20, -55,50])
        del ds
        os.remove(out_path)
      
      
