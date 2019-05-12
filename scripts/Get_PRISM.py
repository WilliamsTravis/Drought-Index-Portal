# -*- coding: utf-8 -*-
"""
To get temperature and precipitation data directly from PRSIM

Created on Sun May 12 09:36:50 2019

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
ftp_path = 'ftp://prism.nacse.org'
temp_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/prism')
pc_folder = os.path.join(data_path, 'data/droughtindices/netcdfs/percentiles')
if not os.path.exists(temp_folder):
    os.makedirs(temp_folder)
if not os.path.exists(pc_folder):
    os.makedirs(pc_folder)

# In[] Data options
# It looks like they have temperature, precipitation, and vapor pressure,
# though not often in means (min/max)
# Samples from each: 
# ppt: PRISM_ppt_provisional_4kmM3_201901_bil.zip
# tmean: PRISM_tmean_provisional_4kmM2_201901_bil.zip
# vpdmax: PRISM_vpdmax_provisional_4kmM1_201904_bil.zip

indices = ['ppt', '']

# In[] Get time series of currently available values
# Connect to FTP 
ftp = ftplib.FTP('prism.nacse.org', 'anonymous', 'anonymous@prism.nacse.org')
