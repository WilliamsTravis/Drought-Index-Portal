# -*- coding: utf-8 -*-
"""
Created on Mon Jan  7 14:23:41 2019

@author: User
"""
import numpy as np
import datetime as dt
import os
import gdal
from glob import glob
import netCDF4
# from netCDF4 import date2num, num2date
from tqdm import tqdm

os.chdir('F:/data/droughtindices/netcdfs')
rasterpath = 'F:/data/droughtindices/pdsisc/nad83'

# Titles
# Index dropdown labels
indexnames = {'noaa': 'NOAA CPC-Derived Rainfall Index',  # Bimonthly - fix
              'pdsi': 'Palmer Drought Severity Index',
              'pdsisc': 'Self-Calibrated Palmer Drought Severity Index',
              'pdsiz': 'Palmer Z Index',
              'spi1': 'Standardized Precipitation Index - 1 month',
              'spi2': 'Standardized Precipitation Index - 2 month',
              'spi3': 'Standardized Precipitation Index - 3 month',
              'spi6': 'Standardized Precipitation Index - 6 month',
              'spei1': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 1 month',
              'spei2': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 2 month',
              'spei3': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 3 month',
              'spei6': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 6 month',
              'eddi1': 'Evaporative Demand Drought Index - 1 month',
              'eddi2': 'Evaporative Demand Drought Index - 2 month',
              'eddi3': 'Evaporative Demand Drought Index - 3 month',
              'eddi6': 'Evaporative Demand Drought Index - 6 month'}

indexpaths = {'noaa': 'f:/data/droughtindices/noaa/nad83',
              'pdsi': 'f:/data/droughtindices/pdsi/nad83',
              'pdsisc': 'f:/data/droughtindices/pdsisc/nad83',
              'pdsiz': 'f:/data/droughtindices/pdsiz/nad83',
              'spi1': 'f:/data/droughtindices/spi/nad83/1month',
              'spi2': 'f:/data/droughtindices/spi/nad83/2month',
              'spi3': 'f:/data/droughtindices/spi/nad83/3month',
              'spi6': 'f:/data/droughtindices/spi/nad83/6month',
              'spei1': 'f:/data/droughtindices/spei/nad83/1month',
              'spei2': 'f:/data/droughtindices/spei/nad83/2month',
              'spei3': 'f:/data/droughtindices/spei/nad83/3month',
              'spei6': 'f:/data/droughtindices/spei/nad83/6month',
              'eddi1': 'f:/data/droughtindices/eddi/nad83/1month',
              'eddi2': 'f:/data/droughtindices/eddi/nad83/2month',
              'eddi3': 'f:/data/droughtindices/eddi/nad83/3month',
              'eddi6': 'f:/data/droughtindices/eddi/nad83/6month'}
indexpaths = {key: os.path.join(indexpaths[key], 'percentiles') for
              key in indexpaths.keys()}

def toNetCDF(index, savepath):
    '''
    Take a folder of individual tifs, with the naming convention
        'name_YYYYMM.tif', and combine them into a singular netcdf file.
    '''
    # Get a sample file, the first, and get some info from it
    files = glob(os.path.join(indexpaths[index], "*tif"))
    files.sort()
    sample = files[0]
    name1 = os.path.basename(sample)
    name2 = os.path.splitext(name1)[0]
    year1 = int(name2[-6:-2])
    month1 = int(name2[-2:])
    title = indexnames[index]

    # Read a sample raster for the structure
    ds = gdal.Open(sample)
    a = ds.ReadAsArray()
    nlat, nlon = np.shape(a)

    # Get geometry
    b = ds.GetGeoTransform()  # bbox, interval
    lon = np.arange(nlon)*b[1]+b[0]
    lat = np.arange(nlat)*b[5]+b[3]

    # It doesn't store dates well
    basedate = dt.datetime(year1, month1, 1)

    # create NetCDF file
    try: nco.close()
    except: pass
    nco = netCDF4.Dataset(os.path.join(savepath, '{}.nc'.format(index)),
                          mode='w', clobber=True, format='NETCDF4_CLASSIC')
    nco.title = title
    nco.subtitle = "Monthly Index values since {}-{}-01".format(year1, month1)

    # create dimensions, variables and attributes:
    nco.createDimension('lon', nlon)
    nco.createDimension('lat', nlat)
    nco.createDimension('time', None)

    timeo = nco.createVariable('time', np.float64, ('time',))
    timeo.units = 'days since {}-{:02d}-01'.format(year1, month1)
    timeo.standard_name = 'time'

    lono = nco.createVariable('lon',  np.float32, ('lon',))
    lono.units = 'degrees_east'
    lono.standard_name = 'longitude'

    lato = nco.createVariable('lat',  np.float32, ('lat',))
    lato.units = 'degrees_north'
    lato.standard_name = 'latitude'

    # create container variable for CRS: lon/lat WGS84 datum
    crso = nco.createVariable('crs', 'i4')
    crso.long_name = 'Lon/Lat NAD83'
    crso.grid_mapping_name = 'latitude_longitude'
    crso.longitude_of_prime_meridian = 0.0
    crso.semi_major_axis = 6378137.0
    crso.inverse_flattening = 298.257222101

    # create short integer variable for index data, with chunking
    variable = nco.createVariable('value', np.float64,  ('time', 'lat', 'lon'),
                                  fill_value=-9999)
    variable.units = 'unitless'
    variable.long_name = 'Index Value'
    variable.standard_name = 'index'
    variable.grid_mapping = 'crs'
    variable.set_auto_maskandscale(False)

    nco.Conventions = 'CF-1.6'

    # write lon,lat
    lono[:] = lon
    lato[:] = lat

    # step through data, writing time and data to NetCDF
    itime = 0
    for f in files:
        name = os.path.basename(f)
        name = os.path.splitext(name)[0]
        year = int(name[-6:-2])
        month = int(name[-2:])
        date = dt.datetime(year, month, 1)
        dtime = (date-basedate)
        timeo[itime] = dtime.days
        rast = gdal.Open(f)
        a = rast.ReadAsArray()
        variable[itime, :, :] = a
        itime = itime+1

    nco.close()
    
indexpaths = {key: value for key,value in indexpaths.items() if 'eddi' in key}
indexnames = {key: value for key,value in indexnames.items() if 'eddi' in key}

# for index in tqdm(indexnames.keys(), position=0):
#     toNetCDF(index, 'D:/data/droughtindices/netcdfs')
for index in tqdm(indexnames.keys(), position=0):
    toNetCDF(index, 'D:/data/droughtindices/netcdfs/percentiles')
