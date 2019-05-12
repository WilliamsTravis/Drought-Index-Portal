# -*- coding: utf-8 -*-
"""
Created on Thu May  9 10:04:34 2019

@author: User
"""
import os
import xarray as xr
os.chdir('d:/data/bd_numeric/')

# Dataset
burns = xr.open_dataset('d:/data/bd_numeric/burn_dates.nc', chunks=500,
                        decode_times=False)

# Data Array
arrays = burns.value

# Dimensions
ntime, ny, nx = arrays.shape

# Don't run this yet
for y in range(ny):
    for x in range(nx):
        # Check if anything exists at that point - sample points below
        # y = 735   # known to have values
        # x = 1435  # known to have values
        # y = 50  # known not to have values
        # x = 50  # known not to have values
        if arrays[:, y, x].where(arrays[:, y, x] > 0).any(dim='time'):
            # alwyas true :(
            print("True")
            # if so what are those values
            arrays[:, y, x].where(arrays[:, y, x] > 0).values

# testing
slice1 = arrays[0, :, :].values  # all y all x, first time slice
slice2 = arrays[5, :, :].values  # all y all x, 6th time slice
