# -*- coding: utf-8 -*-
"""
Practice for dask, masking, and calculating on disk.

for Masking:
https://regionmask.readthedocs.io/en/stable/_static/notebooks/mask_xarray.html

Created on Sat Apr 27 11:41:11 2019

@author: User
"""
import dask.array as da
import datetime as dt
from dateutil.relativedelta import relativedelta
from memory_profiler import profile
import numpy as np
from osgeo import gdal
import sys
import xarray as xr

sys.path.insert(0, 'C:/users/user/github/ubuntu-practice-machine')
from functions2 import im, Index_Maps, movie

array_path = 'f:/data/droughtindices/netcdfs/pdsi.nc'
state_path = 'C:/Users/User/github/Ubuntu-Practice-Machine/data/rasters/us_states_0_25.tif'
month_filter = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
year1 = 2000
year2 = 2018
month1 = 1
month2 = 12

# Get data
@profile
def getData(array_path):
    '''
    The challenge is to read as little as possible into memory without
    slowing the app down. We need to slice by month and year first, then
    filter by the month filter.
    '''
    # Get time series of values and filter by date and location
    d1 = dt.datetime(year1, month1, 1)
    d2 = dt.datetime(year2, month2, 1)
    d2 = d2 + relativedelta(months=+1) - relativedelta(days=+1)

    with xr.open_dataset(array_path, chunks={'time': 100}) as data:
        res = data.crs.GeoTransform[1]
        data = data.sel(time=slice(d1, d2))
        indexlist = data.sel(time=np.in1d(data['time.month'],
                                          month_filter))
        data.close()

    return indexlist, res


# create time series out of a mask
@profile
def stateMask(state_path):
    '''
    perhaps we should save this to an nc file, though we'll have to create a
    mask like this for the custom selections anyway. 
    '''
    states = gdal.Open(state_path)
    array = states.ReadAsArray()
    geom = states.GetGeoTransform()
    nlat, nlon = np.shape(array)    
    lons = np.arange(nlon) * geom[1] + geom[0]
    lats = np.arange(nlat) * geom[5] + geom[3]
    mask = xr.DataArray(states.ReadAsArray(),
                        coords={'lat': lats,
                                'lon': lons},
                        dims={'lat': len(lats),
                              'lon': len(lons)})
    return mask


# Use the mask and a specified state fips (in this case) to filter the
#  data set and generate a time series of average values.
@profile
def regionTS(indexlist, mask, fips):
    '''
    fips is a list of state identifiers
    '''
    ts = indexlist.where(mask.isin(fips))
    ts_mean = ts.mean(dim=('lat', 'lon'))
    return ts, ts_mean

mask = stateMask(state_path)
indexlist, res = getData(array_path)
fips = [int(i) for i in range(100)]
ts, ts_mean = regionTS(indexlist, mask, fips)
movie(ts.value, ts.time.data)

# Okay, thats neat
ones = da.ones((1000, 4000), chunks=(1000, 1000))
ones.compute()
ones.visualize()
