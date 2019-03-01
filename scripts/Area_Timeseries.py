# -*- coding: utf-8 -*-
"""
Building a class that will reproject selections
 in memory for area calculations

Created on Tue Jan 22 18:02:17 2019

@author: User
"""

import matplotlib.pyplot as plt
from netCDF4 import Dataset
import numpy as np
import os
from osgeo import gdal
import pandas as pd
from pyproj import Proj
import salem
import sys
import xarray as xr

# Check if windows or linux
if sys.platform == 'win32':
    data_path = 'f:/'
    sys.path.extend(['Z:/Sync/Ubuntu-Practice-Machine/',
                     'C:/Users/travi/github/Ubuntu-Practice-Machine',
                     'C:/Users/User/github/Ubuntu-Practice-Machine'])
else:
    home_path = '/root/Sync'
    data_path = '/root/Sync'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))

grid = np.load("data/npy/prfgrid.npz")["grid"]

####### Variables #############################################################
state_array = gdal.Open('data/rasters/us_states.tif').ReadAsArray()

######## Functions ############################################################
def im(array):
    '''
    This just plots an array as an image
    '''
    plt.imshow(array)


# Sample dataset
data = Dataset('f:/data/droughtindices/netcdfs/spi1.nc')
arrays = data.variables['value'][:].data

# Sample "dates"
dates = pd.date_range('2000-01-01', periods=arrays.shape[0], freq='M')
dates = np.array([pd.to_datetime(str(d)) for d in dates])

# Sample area query
location = [[4, 4, 4, 5, 5, 5], [62, 63, 64, 62, 63, 64], 'Flathead County, MT', 4]
# location = [39, 97, 'Boulder County, CO', 2]

# Alternately, sample state query (by Fips)
states = [8, 56]
state_mask = state_array.copy()
state_mask[~np.isin(state_mask, states)] = np.nan
state_mask = state_mask * 0 + 1
arrays = arrays * state_mask
array = arrays[0]




# Now, I believe that we need to create a referenced data set out of our arrays  # <------ get these from source arrays
#WGS
wgs_proj = Proj(init='epsg:4326')
wgrid = salem.Grid(nxny=(300, 120), dxdy=(0.25, -0.25),
                   x0y0=(-130, 50), proj=wgs_proj)
lats = np.unique(wgrid.xy_coordinates[1])
lats = lats[::-1]
lons = np.unique(wgrid.xy_coordinates[0])
data_array = xr.DataArray(data=arrays,
                          coords=[dates, lats, lons],
                          dims=['time',  'lat', 'lon'])
wgs_data = xr.Dataset(data_vars={'value': data_array})

# Albers Equal Area Conic North America
albers_proj = Proj('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 \
                   +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 \
                   +datum=NAD83 +units=m +no_defs')
with salem.open_xr_dataset('f:/data/droughtindices/netcdfs/albers/spi1.nc') as data:
    albers_grid = data.salem.grid
    albers = data
    albers.salem.grid._proj = albers_proj  # To make sure, it's here
    data.close()

projection = albers.salem.transform(wgs_data, 'linear')
arrays = projection.value.data
