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
import pathlib
import sys
from tqdm import tqdm
import xarray as xr

# Refactor all of this
pwd = str(pathlib.Path(__file__).parent.absolute())
data_path = os.path.join(pwd, "..")
sys.path.insert(0, data_path)

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