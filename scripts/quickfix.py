# -*- coding: utf-8 -*-
"""
Created on Wed Jan 16 20:03:22 2019

@author: User
"""

x, geom, proj = readRaster("data/tif1.tif", 1, -9999)
x[x==256] = np.nan
x[x==0] = np.nan
x[~np.isnan(x)] = 1

# If its missing a column
col = np.array([np.nan for i in range(120)])
t = col.reshape((col.shape[0],1))
x = np.append(x, t, 1)
grid, geom, proj = readRaster('d:/data/droughtindices/prfgrid.tif', 1, -9999)
toRaster(x, 'data/NA_overlay.tif', geom, proj)

np.savez_compressed("data/NA_overlay.npz", x)
