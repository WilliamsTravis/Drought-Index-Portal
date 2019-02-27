# -*- coding: utf-8 -*-
"""
Created on Mon Feb 25 19:53:32 2019

@author: User
"""
from collections import OrderedDict
import datetime as dt
from osgeo import gdal
from osgeo import osr
from netCDF4 import Dataset
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import sys

# Where to put this?
title_map = {'noaa': 'NOAA CPC-Derived Rainfall Index',
             'pdsi': 'Palmer Drought Severity Index',
             'scpdsi': 'Self-Calibrated Palmer Drought Severity Index',
             'pzi': 'Palmer Z-Index',
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


def percentileArrays(arrays):
    '''
    returns ranked percentiles of a list of 2d numpy arrays or a single 3d numpy array
    '''
    def percentiles(lst):
        '''
        lst = single time series of numbers as a list
        '''
        import scipy.stats
        scipy.stats.moment(lst, 1)

        pct = rankdata(lst)/len(lst)
        return pct

    mask = arrays[0] * 0 + 1
    pcts = np.apply_along_axis(percentiles, axis=0, arr=arrays)
    pcts = pcts * mask

    return pcts


# Write single geotiff to netcdf using attributes of original netcdf file
def toNetCDF(file, ncfile, savepath, index, epsg=4326, wmode='w'):
    '''
    Take an individual tif and either write or append to netcdf.
    '''
    # For attributes
    todays_date = dt.datetime.today()
    today = np.datetime64(todays_date)

    nco = Dataset(savepath, mode=wmode, format='NETCDF4')

    # We need some things from the old nc file
    data = Dataset(ncfile)
    days = data.variables['day'][0]  # This is in days since 1900

    # Read raster for the structure
    data = gdal.Open(file)
    geom = data.GetGeoTransform()
    proj = data.GetProjection()
    array = data.ReadAsArray()
    array[array==-9999.] = np.nan
    nlat, nlon = np.shape(array)
    lons = np.arange(nlon) * geom[1] + geom[0]
    lats = np.arange(nlat) * geom[5] + geom[3]
    del data

    # Dimensions
    nco.createDimension('lat', nlat)
    nco.createDimension('lon', nlon)
    nco.createDimension('time', None)

    # Variables
    latitudes = nco.createVariable('lat',  'f4', ('lat',))
    longitudes = nco.createVariable('lon',  'f4', ('lon',))
    times = nco.createVariable('time', 'f8', ('time',))
    variable = nco.createVariable('value', 'f4', ('time', 'lat', 'lon'),
                                  fill_value=-9999)
    variable.standard_name = 'index'
    variable.units = 'unitless'
    variable.long_name = 'Index Value'

    # Appending the CRS information
    # EPSG information
    refs = osr.SpatialReference()
    refs.ImportFromEPSG(epsg)    
    crs = nco.createVariable('crs', 'c')
    variable.setncattr('grid_mapping', 'crs')
    crs.geographic_crs_name = 'WGS 84'  # is this buried in refs anywhere?
    crs.spatial_ref = proj
    crs.epsg_code = "EPSG:4326"  # How about this?
    crs.GeoTransform = geom
    crs.long_name = 'Lon/Lat WGS 84'
    crs.grid_mapping_name = 'latitude_longitude'
    crs.longitude_of_prime_meridian = 0.0
    crs.semi_major_axis = refs.GetSemiMajor()
    crs.inverse_flattening = refs.GetInvFlattening()

    # Attributes
    # Global Attrs
    nco.title = title_map[index]
    nco.subtitle = "Monthly Index values since 1948-01-01"
    nco.description = ('Monthly gridded data at 0.25 decimal degree' +
                       ' (15 arc-minute resolution, calibrated to 1895-2010 ' +
                       ' for the continental United States.'),
    nco.original_author = 'John Abatzoglou - University of Idaho'
    nco.date = pd.to_datetime(str(today)).strftime('%Y-%m-%d')
    nco.projection = 'WGS 1984 EPSG: 4326'
    nco.citation = ('Westwide Drought Tracker, ' +
                    'http://www.wrcc.dri.edu/monitor/WWDT')
    nco.Conventions = 'CF-1.6'  # Should I include this if I am not sure?

    # Variable Attrs
    times.units = 'days since 1900-01-01'
    times.standard_name = 'time'
    times.calendar = 'gregorian'
    latitudes.units = 'degrees_north'
    latitudes.standard_name = 'latitude'
    longitudes.units = 'degrees_east'
    longitudes.standard_name = 'longitude'

    # Write - set this to write one or multiple
    latitudes[:] = lats
    longitudes[:] = lons
    times[:] = int(days)
    variable[0, :,] = array

    # Done
    nco.close()


def toNetCDF2(tfiles, ncfiles, savepath, index, year1=1948, month1=1,
              year2=2019, month2 = 2, epsg=4326, percentiles=False,
              wmode='w'):
    '''
    Take multiple multiband netcdfs with messed up dates, multiple tiffs with
    desired geometries and writes to a single netcdf as a single time series. This
    has a lot of options, only meant for the app.
    '''
    # For attributes
    todays_date = dt.datetime.today()
    today = np.datetime64(todays_date)

    # Use one tif (one array) for spatial attributes
    data = gdal.Open(tfiles[0])
    geom = data.GetGeoTransform()
    proj = data.GetProjection()
    array = data.ReadAsArray()[0]
    nlat, nlon = np.shape(array)
    lons = np.arange(nlon) * geom[1] + geom[0]
    lats = np.arange(nlat) * geom[5] + geom[3]
    del data

    # use osr for more spatial attributes
    refs = osr.SpatialReference()
    refs.ImportFromEPSG(epsg)

    # Create Dataset
    nco = Dataset(savepath, mode=wmode, format='NETCDF4')

    # Dimensions
    nco.createDimension('lat', nlat)
    nco.createDimension('lon', nlon)
    nco.createDimension('time', None)

    # Variables
    latitudes = nco.createVariable('lat',  'f4', ('lat',))
    longitudes = nco.createVariable('lon',  'f4', ('lon',))
    times = nco.createVariable('time', 'f8', ('time',))
    variable = nco.createVariable('value', 'f4', ('time', 'lat', 'lon'),
                                  fill_value=-9999)
    variable.standard_name = 'index'
    variable.units = 'unitless'
    variable.long_name = 'Index Value'

    # Appending the CRS information
    crs = nco.createVariable('crs', 'c')
    variable.setncattr('grid_mapping', 'crs')
    crs.spatial_ref = proj
    crs.epsg_code = "EPSG:" + str(epsg)
    crs.GeoTransform = geom
    crs.grid_mapping_name = 'latitude_longitude'
    crs.longitude_of_prime_meridian = 0.0
    crs.semi_major_axis = refs.GetSemiMajor()
    crs.inverse_flattening = refs.GetInvFlattening()

    # Attributes
    # Global Attrs
    nco.title = title_map[index]
    nco.subtitle = "Monthly Index values since 1948-01-01"
    nco.description = ('Monthly gridded data at 0.25 decimal degree' +
                       ' (15 arc-minute resolution, calibrated to 1895-2010 ' +
                       ' for the continental United States.'),
    nco.original_author = 'John Abatzoglou - University of Idaho'
    nco.date = pd.to_datetime(str(today)).strftime('%Y-%m-%d')
    nco.projection = 'WGS 1984 EPSG: 4326'
    nco.citation = ('Westwide Drought Tracker, ' +
                    'http://www.wrcc.dri.edu/monitor/WWDT')
    nco.Conventions = 'CF-1.6'  # Should I include this if I am not sure?

    # Variable Attrs
    times.units = 'days since 1900-01-01'
    times.standard_name = 'time'
    times.calendar = 'gregorian'
    latitudes.units = 'degrees_south'
    latitudes.standard_name = 'latitude'
    longitudes.units = 'degrees_east'
    longitudes.standard_name = 'longitude'

    # Now getting the data, which is not in order because of how wwdt does it
    # We need to associate each day with its array
    date_tifs = {}
    for i in range(len(ncfiles)):
        nc = Dataset(ncfiles[i])
        days = nc.variables['day'][:]  # This is in days since 1900
        rasters = gdal.Open(tfiles[i])
        arrays = rasters.ReadAsArray()
        for y in range(len(arrays)):
            date_tifs[days[y]] = arrays[y]

    # okay, that was just in case the dates wanted to bounce around
    date_tifs = OrderedDict(sorted(date_tifs.items()))

    # Now that everything is in the right order, split them back up
    days = np.array(list(date_tifs.keys()))
    arrays = np.array(list(date_tifs.values()))

    # Filter out dates before 1948 <-------------------------------------------Also, filter days after year2, month2 for custom netcdfs
    start = dt.datetime(1900, 1, 15)
    end = dt.datetime(1948, 1, 15)
    cutoff_day = end - start
    cutoff_day = cutoff_day.days
    idx = len(days) - len(days[np.where(days > cutoff_day)])
    days = days[idx:]
    arrays = arrays[idx:]

    # This allows the option to store the data as percentiles
    if percentiles:
        arrays[arrays==-9999] = np.nan
        arrays = percentileArrays(arrays)

    # Write - set this to write one or multiple
    latitudes[:] = lats
    longitudes[:] = lons
    times[:] = days.astype(int)
    variable[:, :, :] = arrays

    # Done
    nco.close()


def toNetCDF3(tfile, ncfile, savepath, index, epsg=102008, percentiles=False,
              wmode='w'):
    '''
    Unlike toNetCDF2, this takes a multiband netcdf with  correct dates and a
    single tiff with desired geometry to write to a single projected netcdf as a
    single time series.

    Still need to parameterize grid mapping and coordinate names.
    '''
    # For attributes
    todays_date = dt.datetime.today()
    today = np.datetime64(todays_date)

    # Use one tif (one array) for spatial attributes
    data = gdal.Open(tfile)
    geom = data.GetGeoTransform()
    proj = data.GetProjection()
    arrays = data.ReadAsArray()
    ntime, nlat, nlon = np.shape(arrays)
    lons = np.arange(nlon) * geom[1] + geom[0]
    lats = np.arange(nlat) * geom[5] + geom[3]
    del data

    # use osr for more spatial attributes
    refs = osr.SpatialReference()
    refs.ImportFromEPSG(epsg)

    # Create Dataset
    nco = Dataset(savepath, mode=wmode, format='NETCDF4')

    # Dimensions
    nco.createDimension('lat', nlat)
    nco.createDimension('lon', nlon)
    nco.createDimension('time', None)

    # Variables
    latitudes = nco.createVariable('lat', 'f4', ('lat',))
    longitudes = nco.createVariable('lon', 'f4', ('lon',))
    times = nco.createVariable('time', 'f8', ('time',))
    variable = nco.createVariable('value', 'f4', ('time', 'lat', 'lon'),
                                  fill_value=-9999)
    variable.standard_name = 'index'
    variable.units = 'unitless'
    variable.long_name = 'Index Value'

    # Appending the CRS information
    crs = nco.createVariable('crs', 'c')
    variable.setncattr('grid_mapping', 'crs')
    crs.spatial_ref = proj
    crs.epsg_code = "EPSG:" + str(epsg)
    crs.GeoTransform = geom
    crs.grid_mapping_name = 'albers_conical_equal_area'
    crs.standard_parallel = [20.0, 60.0]
    crs.longitude_of_central_meridian = -32.0
    crs.latitude_of_projection_origin = 40.0
    crs.false_easting = 0.0
    crs.false_northing = 0.0

    # Attributes
    # Global Attrs
    nco.title = title_map[index]
    nco.subtitle = "Monthly Index values since 1948-01-01"
    nco.description = ('Monthly gridded data at 0.25 decimal degree' +
                       ' (15 arc-minute resolution, calibrated to 1895-2010 ' +
                       ' for the continental United States.'),
    nco.original_author = 'John Abatzoglou - University of Idaho'
    nco.date = pd.to_datetime(str(today)).strftime('%Y-%m-%d')
    nco.projection = 'WGS 1984 EPSG: 4326'
    nco.citation = ('Westwide Drought Tracker, ' +
                    'http://www.wrcc.dri.edu/monitor/WWDT')
    nco.Conventions = 'CF-1.6'  # Should I include this if I am not sure?

    # Variable Attrs
    times.units = 'days since 1900-01-01'
    times.standard_name = 'time'
    times.calendar = 'gregorian'
    latitudes.units = 'meters'
    latitudes.standard_name = 'projection_y_coordinate'
    longitudes.units = 'meters'
    longitudes.standard_name = 'projection_x_coordinate'

    # Now getting the data, which is not in order because of how wwdt does it
    # We need to associate each day with its array
    nc = Dataset(ncfile)

    # Make sure there are the same number of time steps
    if ntime != len(nc.variables['time']):
        print("Time lengths don't match.")
        sys.exit(1)

    days = nc.variables['time'][:]  # This is in days since 1900

    # This allows the option to store the data as percentiles
    if percentiles:
        arrays = percentileArrays(arrays)

    # Write - set this to write one or multiple
    latitudes[:] = lats
    longitudes[:] = lons
    times[:] = days.astype(int)
    variable[:, :, :] = arrays

    # Done
    nco.close()

