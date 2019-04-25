# -*- coding: utf-8 -*-
"""
It might be possible to speed this up using netcdf4 instead of xarray. It would
require adjusting several functions in the Index_Maps class, but may be worth
it. Also check sizes.

It turns out that netcdf4 uses about 200 mb (~20%) less memory for the mean
function than does xarray! Even better, if we convert that into a dask array
the mean calculation is almost twice as fast!

Created on Thu Apr 25 08:26:41 2019

@author: User
"""

import dask.array as da
import datetime as dt
from dateutil.relativedelta import relativedelta
import dateutil.parser as dprs
import netCDF4 as nc
from memory_profiler import profile
import numpy as np
import sys
import warnings
import xarray as xr

sys.path.insert(0, 'c:/users/user/github/ubuntu-practice-machine')
warnings.simplefilter("ignore", category=RuntimeWarning)
from functions import im

path = 'f:/data/droughtindices/netcdfs/pdsi.nc'
d1 = dt.datetime(1948, 1, 1)
d2 = dt.datetime(2018, 12, 1)
d2 = d2 + relativedelta(months=+1) - relativedelta(days=+1)
month_filter = [3, 4, 5, 6, 7, 8]

@profile
def xds(path, d1, d2):
    with xr.open_dataset(path) as data:
        data = data.sel(time=slice(d1, d2))
        data = data.sel(time=np.in1d(data['time.month'], month_filter))
        mean = data.mean('time').value.data
    return mean, data


@profile
def xdds(path, d1, d2, chunks):
   with xr.open_dataset(path) as data:
       data = data.sel(time=slice(d1, d2))
       data = data.sel(time=np.in1d(data['time.month'], month_filter))
       darray = da.from_array(data.variables['value'], chunks=(chunks, 120, 300))
       mean = darray.mean(axis=0).compute()
       mean[mean==-9999] = np.nan
   return mean, darray

@profile
def xdds2(path, d1, d2, chunks):
   with xr.open_dataset(path, chunks={'time': chunks}) as data:
       data = data.sel(time=slice(d1, d2))
       data = data.sel(time=np.in1d(data['time.month'], month_filter))
       mean = data.mean('time').value.data
   return mean, data


# %timeit xm = xds(path, d1, d2)
# %timeit dm = dds(path, d1, d2)
# %timeit xdm = xdds(path, d1, d2, 100)
# %timeit xdm = xdds2(path, d1, d2, 10**2)
# %timeit xdm = xdds2(path, d1, d2, 12**2)
# %timeit xdm = xdds2(path, d1, d2, 15**2)
# %timeit xdm = xdds2(path, d1, d2, 20**2)
# %timeit xdm = xdds2(path, d1, d2, 25**2)


xm, data = xds(path, d1, d2)
xdm, data = xdds(path, d1, d2, 256)
xdm, data = xdds2(path, d1, d2, 256)
