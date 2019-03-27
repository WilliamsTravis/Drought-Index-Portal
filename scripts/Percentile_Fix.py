# -*- coding: utf-8 -*-
"""
Created on Wed Mar 27 12:55:38 2019

@author: User
"""
import datetime as dt
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

from functions import toNetCDFPercentile

# List indices you want to recalculate here
indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2', 'spei3', 'spei6']

for index in indices:
    nc_path = os.path.join(data_path,
                           'data/droughtindices/netcdfs/' + index + '.nc')
    pc_path = os.path.join(data_path,
                           'data/droughtindices/netcdfs/percentiles/' +
                           index + '.nc')
    print("Recalculating Percentiles for " + index + "...")
    toNetCDFPercentile(nc_path, pc_path)