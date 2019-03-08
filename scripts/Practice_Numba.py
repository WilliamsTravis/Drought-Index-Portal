# -*- coding: utf-8 -*-
"""
Created on Fri Mar  8 07:09:41 2019

@author: User
"""
import numpy as np
from numba import njit, prange
from functions import *
import warnings
warnings.filterwarnings('ignore')


# We want to speed up the area calculation step. The boolean masking part of
# this step is the slowest. Here is an example ndarray used in the app.
time_range = [[1950, 2019], [1, 12]]
colorscale = 'Viridis'
reverse_override = 'no'
maps = Index_Maps(time_range, colorscale, reverse_override, 'pdsi')
data = maps.meanOriginal()
ndarray = data[1]

# Let's start which one time period
array = ndarray[0]
im(array)

# We want to mask all cell that are between -5 and -4, say.
a = array.copy()
ax = ndarray.copy()
%timeit a[(a<-5) | (a>-4)] = np.nan # ~50 microseconds for one
%timeit ax[(ax<-5) | (ax>-4)] = np.nan # ~150 milliseconds for all

# With this function?
# For single array
def func(array, l1=-5, l2=-4):
    mask = (array.ravel()>l1) & (array.ravel()<l2)
    return array.ravel()[mask]

# For each array
def outer_func(arrays, l1=-5, l2=-4):
    values = [func(arrays[i], l1, l2) for i in range(len(arrays))]
    return values

# For one
%timeit test = func(array, -5, -4)  # ~80 micro seconds :/

# For each
%timeit tests = outer_func(ndarray, -5, -4)  # ~80 milliseconds :)

# With numba?
# set parallel for the outer function
pnjit = njit(parallel=True)

# Overwrite inner function
func = njit(func)

# outr_func with jit
pouter_func = pnjit(outer_func)
%timeit test = pouter_func(ndarray, -5, -4)  # 104 milliseconds :/
