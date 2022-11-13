#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate the Forest Drought Severity Index. 

For now this will return the average vapor pressure deficit from the min and
max so we can use an NCL script, but eventually:
    
FDSI = 0.44[zscore(ln(PPT_cold_season))] * 0.56[zscore((VPD_warm_season1 + VPD_warm_season2)/2)]
cold-season: November – March
warm-season1: May – July
warm-season2: previous August – October  


Created on Tue Oct  1 10:18:07 2019

@author: travis
"""
import os
import xarray as xr

root = os.path.abspath(os.path.dirname(__file__))
os.chdir(os.path.join(root, '..'))


# Define FDSI
def fdsi(ppt, tmax):
    '''
    At each cell we need all values from Nov - March and the previous Nov -
    March. We also need all values from May-July

    FDSI = 0.44[zscore(ln(PPT_cold_season))] * 0.56[zscore(Tmax_warm_season)]

    sample args:
    
    y = 50; x = 50
    '''
    all_cool = ppt.sel()  # Can I add a month variable?
    all_warm = tmax.sel()


# Precipitation
ppt = xr.open_dataset('data/droughtindices/netcdfs/ppt.nc')

# Max Temperature
tmax = xr.open_dataset('data/droughtindices/netcdfs/tmax.nc')
