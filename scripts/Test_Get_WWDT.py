# -*- coding: utf-8 -*-
"""
Here I just want to test the Get_EDDI.py script with crontab. So this will take
each of the eddis and subtract two days. At the time of this writing there are
469 time periods in each file, ending with "2019-01-31". This will simply knock
a few periods off of each.

Use "ncdump -h eddi*.nc" to check this number before and after running
Get_EDDI.py

Created on Tue Feb  5 12:44:03 2019

@author: User
"""
from netCDF4 import Dataset
import numpy as np
import os
import sys
from tqdm import tqdm
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    # os.chdir('Z:/Sync/Ubuntu-Practice-Machine/')
    data_path = 'f:/'
else:
    # os.chdir('/root/Sync/Ubuntu-Practice-Machine/')
    data_path = '/root/Sync'

# The current list of wwdt indices
indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2', 'spei3', 'spei6',
           'pdsi', 'pdsisc', 'pdsiz', 'eddi1', 'eddi2', 'eddi3', 'eddi6']

# Loop through each netcdf file, read it into memory, knock 2 dates off and
# write it back
for index in tqdm(indices, position=0):
    path = os.path.join(data_path, "data/droughtindices/netcdfs/",
                        index + '.nc')
    
    # xarray 
    with xr.open_dataset(path) as data:
        testlist = data.load()
        data.close()
    dates = testlist.time.data
    d1 = dates[0]
    d2 = dates[-3]
    testlist = testlist.sel(time=slice(d1, d2))
    testlist.to_netcdf(path, mode='w')

    # netCDF4
    # nc = Dataset(path)
    # nc = Dataset(path, 'r+')
    # times = nc.variables['time']
    # values = nc.variables['value']
    # n = times.shape[0]
    
    # It does not want to let me remove items, can I add?
    # nc.variables['time'] = times[:n - 2]
    # nc.variables['value'] = values[:n - 2, :, :]
    
    # sample_data = np.random.normal(loc=0.0, scale=1, size=(120, 300))
    # sample_date = np.float64(times[n-1]) + 30.
    # times[n] = sample_date
    # values[n] = sample_data
    # nc.close()

    # yes 