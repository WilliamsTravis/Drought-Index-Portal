# -*- coding: utf-8 -*-
"""
Created on Thu May  9 10:04:34 2019

@author: User
"""
import os
import xarray as xr
os.chdir('d:/data/bd_numeric/')

burns = xr.open_dataset('d:/data/bd_numeric/burn_dates.nc', chunks=500,
                        decode_times=False)

arrays = burns.value
ntime, ny, nx = arrays.shape
# for t in range(ntime):
for y in range(ny):
    for x in range(nx):
        # Check if anything exists at that point
        y = 735
        x = 1435
        y = 50
        x = 50
        if arrays[:, y, x].where(arrays[:, y, x] > 0).any(dim='time'):
            print("True")
            # if so where do these things exist?
            arrays[:, y, x].where(arrays[:, y, x] > 0).values

# testing
slice1 = arrays[0, :, :].values
slice2 = arrays[5, :, :].values

# More testing
if arrays[:, y, x].where(arrays[:, y, x] > 0).any(dim='time'):
    vals = arrays[:, y, x].where(arrays[:, y, x] > 0).compute()
