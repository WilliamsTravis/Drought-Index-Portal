# -*- coding: utf-8 -*-
"""
Created on Wed May  8 16:02:14 2019

@author: User
"""      
import datetime as dt
from functions import readRasters
from glob import glob
from netCDF4 import Dataset
import numpy as np
# import os
from osgeo import gdal, osr
import pandas as pd

# These were originally named differently: title_daynumberoffirstmonthday.tif
# files = glob(r'D:\data\bd_numeric\tif_converted\*tif')
# for f in files:
#     date_str = f[44:-4]
#     year = int(date_str[:4])
#     day = int(date_str[5:])
#     date = dt.datetime(year, 1, 1) + dt.timedelta(days=day)
#     month = "{:02d}".format(date.month)
#     yyyymm = str(year) + str(month)
#     new_name = f[:44] + yyyymm + '.tif'
#     os.rename(f, new_name)

# Read in files as arrays with geometry and projection information
files = glob(r'D:\data\bd_numeric\tif_converted\*tif')
arrays, geom, proj = readRasters(files)
arrays.sort()
names = [a[0] for a in arrays]
arrays = np.array([a[1] for a in arrays])
crs = osr.SpatialReference()
crs.ImportFromWkt(proj)

# There may be an issue with transformations with this proj4 string
proj4 = crs.ExportToProj4()  
# if so try '+proj=sinu +R=6371007.181 +nadgrids=@null +wktext'

# Todays date for attributes
todays_date = dt.datetime.today()
today = np.datetime64(todays_date)

# Use one tif (one array) for spatial attributes
res = abs(geom[1])
ntime, ny, nx = np.shape(arrays)
xs = np.arange(nx) * geom[1] + geom[0]
ys = np.arange(ny) * geom[5] + geom[3]

# use osr for more spatial attributes
refs = osr.SpatialReference()
if type(proj) is int:
    refs.ImportFromEPSG(proj)
elif '+' in proj:
    refs.ImportFromProj4(proj)

# Create Dataset
nco = Dataset('D:/data/bd_numeric/burn_dates2.nc', mode='w', format='NETCDF4')

# Dimensions
nco.createDimension('y', ny)
nco.createDimension('x', nx)
nco.createDimension('time', None)

# Variables
y = nco.createVariable('y',  'f4', ('y',))
x = nco.createVariable('x',  'f4', ('x',))
times = nco.createVariable('time', 'f8', ('time',))
# Comrpession: https://unidata.github.io/netcdf4-python/netCDF4/index.html#section9
variable = nco.createVariable('value', 'f4', ('time', 'y', 'x'),
                              fill_value=-9999, zlib=True)
variable.standard_name = 'day'
variable.units = 'days'
variable.long_name = 'Burn Days'

# Appending the CRS information - "https://cf-trac.llnl.gov/trac/ticket/77"
crs = nco.createVariable('crs', 'c')
variable.setncattr('grid_mapping', 'crs')
crs.spatial_ref = proj
if type(crs) is int:
    crs.epsg_code = "EPSG:" + str(proj)
elif '+' in proj:
    crs.proj4 = proj
crs.geo_transform = geom
crs.grid_mapping_name = "sinusoidal"
crs.false_easting = 0.0
crs.false_northing = 0.0
crs.longitude_of_central_meridian = 0.0
crs.longitude_of_prime_meridian = 0.0
crs.semi_major_axis = 6371007.181
crs.inverse_flattening = 0.0

# Coordinate attributes
x.standard_name = "projection_x_coordinate"
x.long_name = "x coordinate of projection"
x.units = "m"
y.standard_name = "projection_y_coordinate"
y.long_name = "y coordinate of projection"
y.units = "m"

# Other attributes  # <-------------------------------------------------------- Ask Lise what she wants
nco.title = "Burn Days"
nco.subtitle = "Burn Days Detection by MODIS since 2000."
nco.description = 'The day that a fire is detected.'
nco.date = pd.to_datetime(str(today)).strftime('%Y-%m-%d')
nco.projection = 'MODIS Sinusoidal'
nco.Conventions = 'CF-1.6'

# Variable Attrs
times.units = 'days since 2000-01-01'
times.standard_name = 'time'
times.calendar = 'gregorian'

datestrings = [f[-6:] for f in names]
dates = [dt.datetime(year=int(d[:4]), month=int(d[4:]), day=1) for
          d in datestrings]
deltas = [d - dt.datetime(2000, 1, 1) for d in dates]
days = np.array([d.days for d in deltas])

# Xarray is not able to decode integers suddenlyte
# days2 = pd.date_range('2000-11-01', periods=len(days), freq='M')

# Write - set this to write one or multiple
x[:] = xs
y[:] = ys
times[:] = days
# times[:] = days2
variable[:, :, :] = arrays

# Done
nco.close()
