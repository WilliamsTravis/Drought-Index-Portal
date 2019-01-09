# -*- coding: utf-8 -*-
"""
Increasing I/O speed with PyTables?

Created on Mon Jan  7 13:48:22 2019

@author: User
"""
import datetime as dt
import netCDF4 as nc4
import numpy as np
import os
import time
import xarray as xr

os.chdir(r'C:\users\user\github\Ubuntu-Practice-Machine')
from functions import readRasters2, npzIn


# Simple timing function
def timing(function, *args, **kwargs):
    start = time.time()
    function(*args, **kwargs)
    end = time.time()
    print(function.__name__, 'took', end - start, 'time')


# I want to recreate these process:
# timing(readRasters2, 'D:/data/droughtindices/pdsisc/nad83', -9999)  # 30 sec 1st time, 1.5 seconds 2nd time
# timing(npzIn, 'D:/data/droughtindices/npz/pdsisc_arrays.npz', 
#               'D:/data/droughtindices/npz/pdsisc_arrays.npz')   # 4 sec
# timing(xr.open_dataset, "D:/data/droughtindices/netcdfs/test.nc")  # 0.01 sec!


# Recreating the entire process
# read in full netcdf time series
arrays = xr.open_dataset("D:/data/droughtindices/netcdfs/pdsi.nc")

# Filter by a date range
year_range = [2000, 2017]
y1 = dt.datetime(year_range[0], 1, 1)
y2 = dt.datetime(year_range[1], 12, 1)
array = arrays.sel(time=slice(y1, y2))
data = array.mean('time')
data = data.value.data
data[data==0] = np.nan

# Apply operations over dimensions by name: x.sum('time').
source = xr.open_dataarray("D:/data/droughtindices/source_array.nc")
source = xr.open_dataset("D:/data/droughtindices/netcdfs/test.nc")

# get coordinate-array index dictionaries data!
source.data[0] = data

# Now all this
dfs = xr.DataArray(source, name="data")
pdf = data.to_dataframe()
step = res
to_bin = lambda x: np.floor(x / step) * step
pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
pdf['gridx'] = pdf['lonbin'].map(londict)
pdf['gridy'] = pdf['latbin'].map(latdict)
# grid2 = np.copy(grid)
# grid2[np.isnan(grid2)] = 0
# pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
# pdf['grid'] = pdf['grid'].apply(int).apply(str)
# pdf['data'] = pdf['data'].astype(float).round(3)
# pdf['printdata'] = "GRID #: " + pdf['grid'] + "<br>Data: " + pdf['data'].apply(str)

df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
df = df_flat[np.isfinite(df_flat['data'])]