# -*- coding: utf-8 -*-
"""
Support functions for Ubunut-Practice-Machine

Created on Tue Jan 22 18:02:17 2019

@author: User
"""

# In[]: Environment
import datetime as dt
from dash.exceptions import PreventUpdate
import dask.array as da
from dateutil.relativedelta import relativedelta
import gc
from glob import glob
import json
from collections import OrderedDict
import os
from osgeo import gdal, ogr, osr
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
from netCDF4 import Dataset
from numba import jit
import numpy as np
import pandas as pd
from pyproj import Proj
import salem
from scipy.stats import rankdata
from tqdm import tqdm
import sys
import warnings
import xarray as xr

# Check if windows or linux
if sys.platform == 'win32':
    data_path = 'f:/'
else:
    home_path = '/root/Sync'
    data_path = '/root/Sync'

warnings.filterwarnings("ignore")

# In[]: Variables
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
             'eddi6': 'Evaporative Demand Drought Index - 6 month',
             'leri1': 'Landscape Evaporative Response Index - 1 month',
             'leri3': 'Landscape Evaporative Response Index - 3 month'}


# In[]: Functions
@jit(nopython=True)
def correlationField(ts, arrays):
    '''
    Create a 2d array of pearson correlation coefficient between the time
    series at the location of the grid id and every other grid in a 3d array
    '''
    # Apply that to each cell
    one_field = np.zeros((arrays.shape[1], arrays.shape[2]))
    for i in range(arrays.shape[1]):
        for j in range(arrays.shape[2]):
            lst = arrays[:, i, j]
            cor = np.corrcoef(ts, lst)[0, 1]
            one_field[i, j] = cor
    return one_field


def datePrint(y1, y2, m1, m2, month_filter, monthmarks):
    if y1 != y2:
        if len(month_filter) == 12:
            if m1 == 1 and m2 == 12:
                date_print = '{} - {}'.format(y1, y2)
            elif m1 != 1 or m2 != 12:
                date_print = (monthmarks[m1] + ' ' + str(y1) + ' - ' +
                              monthmarks[m2] + ' ' + str(y2))
        else:
            letters = "".join([monthmarks[m][0] for m in month_filter])
            date_print =  '{} - {}'.format(y1, y2) + ' ' + letters            
    elif y1 == y2:
        if len(month_filter) == 12:
            if m1 == 1 and m2 == 12:
                date_print = '{}'.format(y1)
            elif m1 != 1 or m2 != 12:
                date_print = (monthmarks[m1] + ' - ' +
                              monthmarks[m2] + ' ' + str(y2))
        else:
            letters = "".join([monthmarks[m][0] for m in month_filter])
            date_print =  '{}'.format(y1) + ' ' + letters
    return date_print


def im(array):
    '''
    This just plots an array as an image
    '''
    fig = plt.imshow(array)
    fig.figure.canvas.raise_()


def isInt(string):
    try:
        int(string)
        return True
    except:
        return False


def movie(array, titles=None, axis=0, na=-9999):
    '''
    This takes a three dimensional numpy array and animates it. If the time
    axis is not 0, specify which it is. Just a heads up, some functions
    organize along different axes; consider np.dstack vs np.array. 
    '''
    if 'netCDF' in str(type(array)):
        if titles is None:
            titles = array.variables['time']
        key = list(array.variables.keys())[3]  # I am guessing it's always 3
        array = array.variables[key][:]
        if na in array:
            array[array==na] = np.nan
    elif 'xarray' in str(type(array)):
        if titles is None:
            titles = array.time
        array = array.value
        if na in array:
            array.data[array.data==na] = np.nan
    else:
        if titles is None:
            titles = ["" for t in range(len(array))]
        elif type(titles) is str:
            titles = [titles + ': ' + str(t) for t in range(len(array))]
        if na in array:
            array[array==na] = np.nan


    fig, ax = plt.subplots()

    ax.set_ylim((array.shape[1], 0))
    ax.set_xlim((0, array.shape[2]))

    im = ax.imshow(array[0, :, :], cmap='viridis_r')

    def init():
        if axis == 0:
            im.set_data(array[0, :, :])
        elif axis == 1:
            im.set_data(array[:, 0, :])
        else:
            im.set_data(array[:, :, 0])
        return im,

    def animate(i):
        if axis == 0:
            data_slice = array[i, :, :]
        elif axis == 1:
            data_slice = array[:, i, :]
        else:
            data_slice = array[:, :, i]
        im.set_data(data_slice)
        ax.set_title(titles[i])
        return im,

    anim = FuncAnimation(fig, animate, init_func=init, blit=False, repeat=True)

    return anim


# For making outlines...move to css, maybe
def outLine(color, width):
    string = ('-{1}px -{1}px 0 {0}, {1}px -{1}px 0 {0}, ' +
              '-{1}px {1}px 0 {0}, {1}px {1}px 0 {0}').format(color, width)
    return string


def percentileArrays(arrays):
    '''
    arrays = a list of 2d numpy arrays or one 3d numpy array
    '''
    def percentiles(lst):
        '''
        lst = single time series of numbers as a list
        '''
        import scipy.stats
        scipy.stats.moment(lst, 1)

        pct = (rankdata(lst)/len(lst)) * 100
        return pct

    pcts = np.apply_along_axis(percentiles, axis=0, arr=arrays)

    return pcts


def readRaster(rasterpath, band, navalue=-9999):
    """
    rasterpath = path to folder containing a series of rasters
    navalue = a number (float) for nan values if we forgot
                to translate the file with one originally

    This converts a raster into a numpy array along with spatial features
    needed to write any results to a raster file. The return order is:

      array (numpy), spatial geometry (gdal object),
                                      coordinate reference system (gdal object)
    """
    raster = gdal.Open(rasterpath)
    geometry = raster.GetGeoTransform()
    arrayref = raster.GetProjection()
    array = np.array(raster.GetRasterBand(band).ReadAsArray())
    del raster
    array = array.astype(float)
    if np.nanmin(array) < navalue:
        navalue = np.nanmin(array)
    array[array==navalue] = np.nan
    return(array, geometry, arrayref)


def shapeReproject(src, dst, src_epsg, dst_epsg):
    '''
    There doesn't appear to be an ogr2ogr analog in Python's OGR module.
    This simply reprojects a shapefile from the file.
    
    src = source file path
    dst = destination file path
    src_epsg = the epsg coordinate reference code for the source file
    dst_epsg = the epsg coordinate reference code for the destination file
    
    src = 'data/shapefiles/temp/temp.shp'
    dst = 'data/shapefiles/temp/temp.shp'
    src_epsg = 102008
    dst_epsg = 4326

    '''
    # Get the shapefile driver
    driver = ogr.GetDriverByName('ESRI Shapefile')

    # If dst and src match, overwrite is true, set a temporary dst name
    if dst == src:
        overwrite = True
        base, filename = os.path.split(dst)
        name, ext = os.path.splitext(filename)
        dst = os.path.join(base, name + '2' + ext)
    else:
        overwrite = False

    # Establish Coordinate Reference Systems
    src_crs = osr.SpatialReference()
    dst_crs = osr.SpatialReference()
    src_crs.ImportFromEPSG(src_epsg)
    dst_crs.ImportFromEPSG(dst_epsg)

    # Create the tranformation method
    transformation = osr.CoordinateTransformation(src_crs, dst_crs)

    # Get/Generate layers
    src_dataset = driver.Open(src)
    src_layer = src_dataset.GetLayer()
    if os.path.exists(dst):
        driver.DeleteDataSource(dst)
    dst_dataset = driver.CreateDataSource(dst)
    dst_file_name = os.path.basename(dst)
    dst_layer_name = os.path.splitext(dst_file_name)[0]
    dst_layer = dst_dataset.CreateLayer(dst_layer_name,
                                        geom_type=ogr.wkbMultiPolygon)

    # add Fields
    src_layer_defn = src_layer.GetLayerDefn()
    for i in range(0, src_layer_defn.GetFieldCount()):
        field_defn = src_layer_defn.GetFieldDefn(i)
        dst_layer.CreateField(field_defn)

    # Get Destination Layer Feature Definition
    dst_layer_defn = dst_layer.GetLayerDefn()

    # Project Features
    src_feature = src_layer.GetNextFeature()
    while src_feature:
        geom = src_feature.GetGeometryRef()
        geom.Transform(transformation)
        dst_feature = ogr.Feature(dst_layer_defn)
        dst_feature.SetGeometry(geom)
        for i in range(0, dst_layer_defn.GetFieldCount()):
            dst_feature.SetField(dst_layer_defn.GetFieldDefn(i).GetNameRef(),
                                 src_feature.GetField(i))
        dst_layer.CreateFeature(dst_feature)
        dst_feature = None
        src_feature = src_layer.GetNextFeature()

    # Set coordinate extents?
    dst_layer.GetExtent()
    
    # Save and close
    src_dataset = None
    dst_dataset = None

    # Overwrite if needed
    if overwrite is True:
        src_files = glob('data/shapefiles/temp/temp.*')
        dst_files = glob('data/shapefiles/temp/temp2.*')
        for sf in src_files:
            os.remove(sf)
        for df in dst_files:
            os.rename(df, df.replace('2', ''))


def standardize(indexlist):
    '''
    Min/max standardization
    '''
    def single(array, mins, maxes):
        newarray = (array - mins)/(maxes - mins)
        return(newarray)

    if type(indexlist[0][0]) == str:
        arrays = [a[1] for a in indexlist]
        mins = np.nanmin(arrays)
        maxes = np.nanmax(arrays)
        standardizedlist = [[indexlist[i][0],
                             single(indexlist[i][1],
                                    mins,
                                    maxes)] for i in range(len(indexlist))]

    else:
        mins = np.nanmin(indexlist)
        maxes = np.nanmax(indexlist)
        standardizedlist = [single(indexlist[i],
                                   mins, maxes) for i in range(len(indexlist))]
    return(standardizedlist)


def toNetCDFSingle(file, ncfile, savepath, index, epsg=4326, wmode='w'):
    '''
    Take an individual tif and either write or append to netcdf.
    '''
    # For attributes
    todays_date = dt.datetime.today()
    today = np.datetime64(todays_date)

    # Create data set
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


def toNetCDF(tfiles, ncfiles, savepath, index, year1, month1, year2, month2,
             epsg=4326, percentiles=False, wmode='w'):
    '''
    Take multiple multiband netcdfs with unordered dates and multiple tiffs
    with desired geometries and write to a single netcdf as a single time
    series. This has a lot of options and is only meant for the app.

    As an expediency, if there isn't an nc file it defaults to reading dates
    from the file names.

    I need to go back and parameterize the subtitle to reflect the actual dates
    used in each dataset.

    Test parameters for toNetCDF2
        tfiles = glob('f:/data/droughtindices/netcdfs/wwdt/tifs/temp*')
        ncfiles = glob('f:/data/droughtindices/netcdfs/wwdt/*nc')
        savepath = 'testing.nc'
        index = 'spi1'
        year1=1948
        month1=1
        year2=2019
        month2=12
        epsg=4326
        percentiles=False
        wmode='w'
    '''
    # For attributes
    todays_date = dt.datetime.today()
    today = np.datetime64(todays_date)

    # Use one tif (one array) for spatial attributes
    data = gdal.Open(tfiles[0])
    geom = data.GetGeoTransform()
    res = abs(geom[1])
    proj = data.GetProjection()
    array = data.ReadAsArray()
    if len(array.shape) == 3:
        ntime, nlat, nlon = np.shape(array)
    else:
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
    nco.subtitle = "Monthly Index values since 1895-01-01"
    nco.description = ('Monthly gridded data at '+ str(res) + 
                       'decimal degree (15 arc-minute resolution, ' +
                       'calibrated to 1895-2010 for the continental ' +
                       'United States.'),
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
    try:
        tfiles.sort()
        ncfiles.sort()
        test = Dataset(ncfiles[0])
        test.close()
        date_tifs = {}
        for i in range(len(ncfiles)):
            nc = Dataset(ncfiles[i])
            days = nc.variables['day'][:]
            rasters = gdal.Open(tfiles[i])
            arrays = rasters.ReadAsArray()
            for y in range(len(arrays)):
                date_tifs[days[y]] = arrays[y]
    
        # okay, that was just in case the dates wanted to bounce around
        date_tifs = OrderedDict(sorted(date_tifs.items()))
    
        # Now that everything is in the right order, split them back up
        days = np.array(list(date_tifs.keys()))
        arrays = np.array(list(date_tifs.values()))

    except Exception as e:
        print(str(e))
        tfiles.sort()

        # print('Combining data using filename dates...')
        datestrings = [f[-10:-4] for f in tfiles if isInt(f[-10:-4])]
        dates = [dt.datetime(year=int(d[:4]), month=int(d[4:]), day=15) for
                  d in datestrings]
        deltas = [d - dt.datetime(1900, 1, 1) for d in dates]
        days = np.array([d.days for d in deltas])
        arrays = []
        for t in tfiles:
            data = gdal.Open(t)
            array = data.ReadAsArray()
            arrays.append(array)
        arrays = np.array(arrays)

    # Filter out dates
    base = dt.datetime(1900, 1, 1)
    start = dt.datetime(year1, month1, 1)
    day1 = start - base
    day1 = day1.days
    end = dt.datetime(year2, month2, 1)
    day2 = end - base
    day2 = day2.days
    idx = len(days) - len(days[np.where(days >= day1)])
    idx2 = len(days[np.where(days < day2)])
    days = days[idx:idx2]
    arrays = arrays[idx:idx2]

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


def toNetCDFAlbers(tfiles, ncfiles, savepath, index, year1, month1,
                   year2, month2, epsg=4326, percentiles=False, wmode='w'):
    '''
    This does the same as above but is specific to the north american
    albers equal area conic projection

    Test parameters for toNetCDF2
        tfiles = glob('f:/data/droughtindices/netcdfs/wwdt/tifs/proj*')
        ncfiles = glob('f:/data/droughtindices/netcdfs/wwdt/temp_*[0-9]*.nc')
        savepath = 'f:/data/droughtindices/netcdfs/wwdt/testing.nc'
        index = 'spi1'
        year1=1895
        month1=1
        year2=2019
        month2=12
        epsg=102008
        percentiles=False
        wmode='w'
    '''
    # For attributes
    todays_date = dt.datetime.today()
    today = np.datetime64(todays_date)

    # Use one tif (one array) for spatial attributes
    data = gdal.Open(tfiles[0])
    geom = data.GetGeoTransform()
    res = abs(geom[1])
    proj = data.GetProjection()
    array = data.ReadAsArray()
    if len(array.shape) == 3:
        ntime, nlat, nlon = np.shape(array)
    else:
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
    crs.grid_mapping_name = 'albers_conical_equal_area'
    crs.standard_parallel = [20.0, 60.0]
    crs.longitude_of_central_meridian = -32.0
    crs.latitude_of_projection_origin = 40.0
    crs.false_easting = 0.0
    crs.false_northing = 0.0

    # Attributes
    # Global Attrs
    nco.title = title_map[index]
    nco.subtitle = "Monthly Index values since 1895-01-01"
    nco.description = ('Monthly gridded data at '+ str(res) + 
                       'decimal degree (15 arc-minute resolution, ' +
                       'calibrated to 1895-2010 for the continental ' +
                       'United States.'),
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
    # We need to associate each day with its array, let's sort files to start
    
    # Dates may be gotten from either the original nc files or tif filenames
    try:
        ncfiles.sort()
        tfiles.sort()   
        test = Dataset(ncfiles[0])
        test.close()
        date_tifs = {}
        for i in range(len(ncfiles)):
            nc = Dataset(ncfiles[i])
            days = nc.variables['day'][:]
            rasters = gdal.Open(tfiles[i])
            arrays = rasters.ReadAsArray()
            for y in range(len(arrays)):
                date_tifs[days[y]] = arrays[y]
    
        # okay, that was just in case the dates wanted to bounce around
        date_tifs = OrderedDict(sorted(date_tifs.items()))
    
        # Now that everything is in the right order, split them back up
        days = np.array(list(date_tifs.keys()))
        arrays = np.array(list(date_tifs.values()))

    except Exception as e:
        tfiles.sort()   
        datestrings = [f[-10:-4] for f in tfiles if isInt(f[-10:-4])]
        dates = [dt.datetime(year=int(d[:4]), month=int(d[4:]), day=15) for
                  d in datestrings]
        deltas = [d - dt.datetime(1900, 1, 1) for d in dates]
        days = np.array([d.days for d in deltas])
        arrays = []
        for t in tfiles:
            data = gdal.Open(t)
            array = data.ReadAsArray()
            arrays.append(array)
        arrays = np.array(arrays)

    # Filter out dates
    base = dt.datetime(1900, 1, 1)
    start = dt.datetime(year1, month1, 1)
    day1 = start - base
    day1 = day1.days
    end = dt.datetime(year2, month2, 1)
    day2 = end - base
    day2 = day2.days
    idx = len(days) - len(days[np.where(days >= day1)])
    idx2 = len(days[np.where(days < day2)])
    days = days[idx:idx2]
    arrays = arrays[idx:idx2]

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
    Unlike toNetCDF2, this takes a multiband netcdf with correct dates and a
    single tiff with desired geometry to write to a single netcdf as
    a single time series projected to the North American Albers Equal Area
    Conic Projection.

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
    nco.subtitle = "Monthly Index values since 1895-01-01"
    nco.description = ('Monthly gridded data at 0.25 decimal degree' +
                       ' (15 arc-minute resolution, calibrated to 1895-2010 ' +
                       ' for the continental United States.'),
    nco.original_author = 'John Abatzoglou - University of Idaho'
    nco.date = pd.to_datetime(str(today)).strftime('%Y-%m-%d')
    nco.projection = 'WGS 1984 EPSG: 4326'
    nco.citation = ('Westwide Drought Tracker, ' +
                    'http://www.wrcc.dri.edu/monitor/WWDT')
    nco.Conventions = 'CF-1.6'

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

    days = nc.variables['time'][:]

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


def toNetCDFPercentile(src_path, dst_path):
    '''
    Take an existing netcdf file and simply transform the data into percentile
    space

    Sample arguments:
    src_path = 'f:/data/droughtindices/netcdfs/spi2.nc'
    dst_path = 'f:/data/droughtindices/netcdfs/percentiles/spi2.nc'
    
    src = Dataset(src_path)
    dst = Dataset(dst_path, 'w')
    '''
    with Dataset(src_path) as src, Dataset(dst_path, 'w') as dst:

        # copy attributes
        for name in src.ncattrs():
            dst.setncattr(name, src.getncattr(name))

        # Some attributes need to change
        dst.setncattr('subtitle', 'Monthly percentile values ' +
                                  'since 1895')
        dst.setncattr('standard_name', 'percentile')

        # set dimensions
        nlat = src.dimensions['lat'].size
        nlon = src.dimensions['lon'].size
        dst.createDimension('lat', nlat)
        dst.createDimension('lon', nlon)
        dst.createDimension('time', None)

        # set variables
        latitudes = dst.createVariable('lat',  'f4', ('lat',))
        longitudes = dst.createVariable('lon',  'f4', ('lon',))
        times = dst.createVariable('time', 'f8', ('time',))
        variable = dst.createVariable('value', 'f4',
                                      ('time', 'lat', 'lon'),
                                      fill_value=-9999)
        crs = dst.createVariable('crs', 'c')
        variable.setncattr('grid_mapping', 'crs')
        
        # Set coordinate system attributes
        src_crs = src.variables['crs']
        for name in src_crs.ncattrs():
            crs.setncattr(name, src_crs.getncattr(name))   

        # Variable Attrs
        times.units = 'days since 1900-01-01'
        times.standard_name = 'time'
        times.calendar = 'gregorian'
        latitudes.units = 'degrees_north'
        latitudes.standard_name = 'latitude'
        longitudes.units = 'degrees_east'
        longitudes.standard_name = 'longitude'

        # Set most values
        latitudes[:] = src.variables['lat'][:]
        longitudes[:] =  src.variables['lon'][:]
        times[:] =  src.variables['time'][:]

        # finally rank and transform values into percentiles
        values = src.variables['value'][:]
        percentiles = percentileArrays(values)
        variable[:] = percentiles


def toRaster(array, path, geometry, srs, navalue=-9999):
    """
    Writes a single array to a raster with coordinate system and geometric
    information.

    path = target path
    srs = spatial reference system
    """
    xpixels = array.shape[1]    
    ypixels = array.shape[0]
    path = path.encode('utf-8')
    image = gdal.GetDriverByName("GTiff").Create(path, xpixels, ypixels,
                                1, gdal.GDT_Float32)
    image.SetGeoTransform(geometry)
    image.SetProjection(srs)
    image.GetRasterBand(1).WriteArray(array)
    image.GetRasterBand(1).SetNoDataValue(navalue)
      

def toRasters(arraylist, path, geometry, srs):
    """
    Writes a list of 2d arrays, or a 3d array, to a series of tif files.

    Arraylist format = [[name,array],[name,array],....]
    path = target path
    geometry = gdal geometry object
    srs = spatial reference system object
    """
    if path[-2:] == "\\":
        path = path
    else:
        path = path + "\\"
    sample = arraylist[0][1]
    ypixels = sample.shape[0]
    xpixels = sample.shape[1]
    for ray in  tqdm(arraylist):
        image = gdal.GetDriverByName("GTiff").Create(os.path.join(path,
                                                              ray[0] + ".tif"),
                                    xpixels, ypixels, 1, gdal.GDT_Float32)
        image.SetGeoTransform(geometry)
        image.SetProjection(srs)
        image.GetRasterBand(1).WriteArray(ray[1])
          

def wgsToAlbers(arrays, crdict, proj_sample):
    '''
    Takes an xarray dataset in WGS 84 (epsg: 4326) with a specified mask and
    returns that mask projected to Alber's North American Equal Area Conic
    (epsg: 102008).
    '''
    # dates = range(len(arrays.time))
    wgs_proj = Proj(init='epsg:4326')
    geom = crdict.source.transform
    wgrid = salem.Grid(nxny=(crdict.x_length, crdict.y_length),
                       dxdy=(crdict.res, -crdict.res),
                       x0y0=(geom[0], geom[3]), proj=wgs_proj)
    lats = np.unique(wgrid.xy_coordinates[1])
    lats = lats[::-1]
    lons = np.unique(wgrid.xy_coordinates[0])
    data_array = xr.DataArray(data=arrays.value[0],  # <-------------------------- I'm not sure what this does yet
                              coords=[lats, lons],
                              dims=['lat', 'lon'])
    wgs_data = xr.Dataset(data_vars={'value': data_array})

    # Albers Equal Area Conic North America (epsg not working)
    albers_proj = Proj('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 \
                        +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 \
                        +datum=NAD83 +units=m +no_defs')

    # Create an albers grid
    geom = proj_sample.crs.GeoTransform
    array = proj_sample.value[0].values
    res = geom[1]
    x_length = array.shape[1]
    y_length = array.shape[0]
    agrid = salem.Grid(nxny=(x_length, y_length), dxdy=(res, -res),
                       x0y0=(geom[0], geom[3]), proj=albers_proj)
    lats = np.unique(agrid.xy_coordinates[1])
    lats = lats[::-1]
    lons = np.unique(agrid.xy_coordinates[0])
    data_array = xr.DataArray(data=array,
                              coords=[lats, lons],
                              dims=['lat', 'lon'])
    data_array = data_array
    albers_data = xr.Dataset(data_vars={'value': data_array})
    albers_data.salem.grid._proj = albers_proj
    projection = albers_data.salem.transform(wgs_data, 'linear')
    proj_mask = projection.value.data
    proj_mask = proj_mask * 0 + 1

    # Set up grid info from coordinate dictionary
    nlat, nlon = proj_mask.shape   
    xs = np.arange(nlon) * geom[1] + geom[0]
    ys = np.arange(nlat) * geom[5] + geom[3]


    # Create mask xarray
    proj_mask = xr.DataArray(proj_mask,
                              coords={'lat': ys.astype(np.float32),
                                      'lon': xs.astype(np.float32)},
                              dims={'lat': len(ys),
                                    'lon': len(xs)})
    return(proj_mask)


# In[]:Classes
class Admin_Elements:
    def __init__(self, resolution):
        self.resolution = resolution

    def buildAdmin(self):
        resolution = self.resolution
        res_str = str(round(resolution, 3))
        res_ext = '_' + res_str.replace('.', '_')
        county_path = 'data/rasters/us_counties' + res_ext + '.tif'
        state_path = 'data/rasters/us_states' + res_ext + '.tif'
        
        # Use the shapefile for just the county, it has state and county fips
        src_path = 'data/shapefiles/contiguous_counties.shp' 
    
        # And rasterize
        self.rasterize(src_path, county_path, attribute='COUNTYFP',
                       extent=[-130, 50, -55, 20])
        self.rasterize(src_path, state_path, attribute='STATEFP',
                       extent=[-130, 50, -55, 20])

    def buildAdminDF(self):
        resolution = self.resolution
        res_str = str(round(resolution, 3))
        res_ext = '_' + res_str.replace('.', '_')
        grid_path = 'data/rasters/grid' + res_ext + '.tif'
        gradient_path = 'data/rasters/gradient' + res_ext + '.tif'
        county_path = 'data/rasters/us_counties' + res_ext + '.tif'
        state_path = 'data/rasters/us_states' + res_ext + '.tif'
        admin_path = 'data/tables/admin_df' + res_ext + '.csv'
    
        # There are several administrative elements used in the app
        fips = pd.read_csv('data/tables/US_FIPS_Codes.csv', skiprows=1,
                           index_col=0)
        res_ext = '_' + str(resolution).replace('.', '_')
        states = pd.read_table('data/tables/state_fips.txt', sep='|')
        states = states[['STATE_NAME', 'STUSAB', 'STATE']]
    
        # Read, mask and flatten the arrays
        def flttn(array_path):
            '''
            Mask and flatten the grid array
            '''
            grid = gdal.Open(array_path).ReadAsArray()
            grid = grid.astype(np.float64)
            na = grid[0, 0]
            grid[grid == na] = np.nan
            return grid.flatten()
    
        grid = flttn(grid_path)
        gradient = flttn(gradient_path)
        carray = flttn(county_path)
        sarray = flttn(state_path)
    
        # Associate county and state fips with grid ids
        cdf = pd.DataFrame(OrderedDict({'grid': grid, 'county_fips': carray,
                                        'state_fips': sarray,
                                        'gradient': gradient}))
        cdf = cdf.dropna()
        cdf = cdf.astype(int)

        # Create the full county fips (state + county)
        def frmt(number):
            return '{:03d}'.format(number)
        fips['fips'] = (fips['FIPS State'].map(frmt) +
                        fips['FIPS County'].map(frmt))
        cdf['fips'] = (cdf['state_fips'].map(frmt) +
                       cdf['county_fips'].map(frmt))    
        df = cdf.merge(fips, left_on='fips', right_on='fips', how='inner')
        df = df.merge(states, left_on='state_fips', right_on='STATE',
                      how='inner')
        df['place'] = df['County Name'] + ' County, ' + df['STUSAB']
        df = df[['County Name', 'STATE_NAME', 'place', 'grid', 'gradient',
                 'county_fips', 'state_fips', 'fips', 'STUSAB']]
        df.columns = ['county', 'state', 'place', 'grid', 'gradient',
                      'county_fips','state_fips', 'fips', 'state_abbr']

        df.to_csv(admin_path, index=False)

    def buildGrid(self):
        '''
        Use the county raster to build this.
        '''
        resolution = self.resolution
        res_str = str(round(resolution, 3))
        res_ext = '_' + res_str.replace('.', '_')
        array_path = 'data/rasters/us_counties' + res_ext + '.tif'
        if not os.path.exists(array_path):
            self.buildAdmin()
        source = gdal.Open(array_path)
        geom = source.GetGeoTransform()
        proj = source.GetProjection()
        array = source.ReadAsArray()
        array = array.astype(np.float64)
        na = array[0, 0]
        mask = array.copy()
        mask[mask == na] = np.nan
        mask = mask * 0 + 1
        gradient = mask.copy()
        for i in range(gradient.shape[0]):
            for j in range(gradient.shape[1]):
                gradient[i, j] = i * j
        gradient = gradient * mask
        grid = mask.copy()
        num = grid.shape[0] * grid.shape[1]
        for i in range(gradient.shape[0]):
            for j in range(gradient.shape[1]):
                num -= 1
                grid[i, j] = num
        grid = grid * mask
        toRaster(grid, 'data/rasters/grid' + res_ext + '.tif', geom, proj,
                 -9999)
        toRaster(gradient, 'data/rasters/gradient' + res_ext + '.tif',
                 geom, proj, -9999)
        return grid, gradient

    def buildNA(self):
        '''
        For when there isn't any data I am printing NA across the screen. So
        all this will do is reproject an existing 'NA' raster to the specified
        resolution.
        '''
        res = self.resolution
        res_print = str(res).replace('.', '_')
        src_path = 'data/rasters/na_banner.tif'
        out_path = 'data/rasters/na_banner_' + res_print + '.tif'
        ds = gdal.Warp(out_path, src_path, dstSRS='EPSG:4326',
                       xRes=res, yRes=res, outputBounds=[-130, 20, -55, 50])
        del ds
    
    def buildSource(self):
        '''
        take a single band raster and convert it to a data array for use as a
        source. Make one of these for each resolution you might need.
        '''
        resolution = self.resolution
        res_str = str(round(resolution, 3))
        res_ext = '_' + res_str.replace('.', '_')
        array_path = 'data/rasters/us_counties' + res_ext + '.tif'
        if not os.path.exists(array_path):
            self.buildAdmin(resolution)
        data = gdal.Open(array_path)
        geom = data.GetGeoTransform()
        array = data.ReadAsArray()
        array = np.array([array])
        if len(array.shape) == 3:
            ntime, nlat, nlon = np.shape(array)
        else:
            nlat, nlon = np.shape(array)
        lons = np.arange(nlon) * geom[1] + geom[0]
        lats = np.arange(nlat) * geom[5] + geom[3]
        del data
    
        attributes = OrderedDict({'transform': geom,
                                  'res': (geom[1], geom[1])})
    
        data = xr.DataArray(data=array,
                            name=('A ' + str(resolution) + ' resolution grid' +
                                  ' used as a source array'),
                            coords=(('band', np.array([1])),
                                    ('y', lats),
                                    ('x', lons)),
                            attrs=attributes)
        wgs_path = 'data/rasters/source_array' + res_ext + '.nc'
        data.to_netcdf(wgs_path)

        # We also need a source data set for Alber's projection geometry
        grid_path = 'data/rasters/grid' + res_ext + '.tif'
        albers_path = 'data/rasters/source_albers' + res_ext + '.tif'
        ds = gdal.Warp(albers_path, grid_path, dstSRS='EPSG:102008')
        del ds

    def getElements(self):
        '''
        I want to turn this into a class that handles all resolution dependent
        objects, but for now I'm just tossing this together for a meeting.
        '''
        # Get paths
        [grid_path, gradient_path, county_path, state_path,
         source_path, albers_path, admin_path] = self.pathRequest()
    
        # Read in/create objects  # <------------------------------------------ We could create xarray masks here (xMask)
        states = gdal.Open(state_path).ReadAsArray()
        states[states==-9999] = np.nan
        cnty = gdal.Open(county_path).ReadAsArray()
        cnty[cnty==-9999] = np.nan
        grid = gdal.Open(grid_path).ReadAsArray()
        grid[grid == -9999] = np.nan
        mask = grid * 0 + 1
        cd = Coordinate_Dictionaries(source_path, grid)
        admin_df = pd.read_csv(admin_path)
        albers_source = gdal.Open(albers_path)
        with xr.open_dataarray(source_path) as data:
            source = data.load()

        # We actually want full state-county fips for counties
        state_counties = np.stack([states, cnty])

        # Format fips as 3-digit strings with leading zeros
        def formatFIPS(lst):
            try:
                fips1 = '{:03d}'.format(int(lst[0]))
                fips2 = '{:03d}'.format(int(lst[1]))
                fips = float(fips1 + fips2)
            except:
                fips = np.nan
            return fips

        # Get a field of full fips to use as location ids
        cnty = np.apply_along_axis(formatFIPS, 0, state_counties)

        return states, cnty, grid, mask, source, albers_source, cd, admin_df

    def pathRequest(self):
        # Set paths to each element then make sure they exist
        resolution = self.resolution
        res_str = str(round(resolution, 3))
        res_ext = '_' + res_str.replace('.', '_')
        grid_path = 'data/rasters/grid' + res_ext + '.tif'
        gradient_path = 'data/rasters/gradient' + res_ext + '.tif'
        county_path = 'data/rasters/us_counties' + res_ext + '.tif'
        state_path = 'data/rasters/us_states' + res_ext + '.tif'
        source_path = 'data/rasters/source_array' + res_ext + '.nc'
        albers_path = 'data/rasters/source_albers' + res_ext + '.tif'
        admin_path = 'data/tables/admin_df' + res_ext + '.csv'
        na_path = 'data/rasters/na_banner' + res_ext + '.tif'

        if not os.path.exists(county_path) or not os.path.exists(state_path):
            self.buildAdmin()
        if not os.path.exists(grid_path) or not os.path.exists(gradient_path):
            self.buildGrid()
        if not os.path.exists(source_path) or not os.path.exists(albers_path):
            self.buildSource()
        if not os.path.exists(admin_path):
            self.buildAdminDF()
        if not os.path.exists(na_path):
            self.buildNA()

        # Return everything at once
        path_package = [grid_path, gradient_path, county_path, state_path,
                        source_path, albers_path, admin_path]
    
        return path_package

    def rasterize(self, src, dst, attribute, all_touch=False,
                  epsg=4326, na=-9999):
        '''
        It seems to be unreasonably involved to do this in Python compared to
        the command line.
        ''' 
        resolution = self.resolution

        # Open shapefile, retrieve the layer
        src_data = ogr.Open(src)
        layer = src_data.GetLayer()
        extent = layer.GetExtent()  # This is wrong

        # Create the target raster layer
        xmin, xmax, ymin, ymax = extent
        cols = int((xmax - xmin)/resolution)
        rows = int((ymax - ymin)/resolution)
        trgt = gdal.GetDriverByName('GTiff').Create(dst, cols, rows, 1,
                                   gdal.GDT_Float32)
        trgt.SetGeoTransform((xmin, resolution, 0, ymax, 0, -resolution))
    
        # Add crs
        refs = osr.SpatialReference()
        refs.ImportFromEPSG(epsg)
        trgt.SetProjection(refs.ExportToWkt())
    
        # Set no value
        band = trgt.GetRasterBand(1)
        band.SetNoDataValue(na)
    
        # Set options
        if all_touch is True:
            ops = ['-at', 'ATTRIBUTE=' + attribute]
        else:
            ops = ['ATTRIBUTE=' + attribute]

        # Finally rasterize
        gdal.RasterizeLayer(trgt, [1], layer, options=ops)

        # Close target an source rasters
        del trgt
        del src_data

    
class Cacher:
    '''
    A simple stand in cache for storing objects in memory.
    '''
    def __init__(self, key):
        self.cache={}
        self.key=key
    def memoize(self, function):
        def cacher(*args):
            arg = [a for a in args]
            key = json.dumps(arg)
            if key not in self.cache.keys():
                print("Generating/replacing dataset...")
                if self.cache:
                    del self.cache[list(self.cache.keys())[0]]
                self.cache.clear()
                gc.collect()
                self.cache[key] = function(*args)
            else:
                print("Returning existing dataset...")
            return self.cache[key]
        return cacher


class Coordinate_Dictionaries:
    '''
    This translates cartesian coordinates to geographic coordinates and back.
    It also provides information about the coordinate system used in the
    source data set, and methods to translate grid ids to plotly point objects
    and back. 
    '''
    def __init__(self, source_path, grid):
        # Source Data Array
        self.source = xr.open_dataarray(source_path)

        # Geometry
        self.x_length = self.source.shape[2]
        self.y_length = self.source.shape[1]
        self.res = self.source.res[0]
        self.lon_min = self.source.transform[0]
        self.lat_max = self.source.transform[3]
        self.xs = range(self.x_length)
        self.ys = range(self.y_length)
        self.lons = [self.lon_min + self.res*x for x in self.xs]
        self.lats = [self.lat_max - self.res*y for y in self.ys]

        # Dictionaires with coordinates and array index positions
        self.grid = grid
        self.londict = dict(zip(self.lons, self.xs))
        self.latdict = dict(zip(self.lats, self.ys))
        self.londict_rev = {y: x for x, y in self.londict.items()}
        self.latdict_rev = {y: x for x, y in self.latdict.items()}

    def pointToGrid(self, point):
        '''
        Takes in a plotly point dictionary and outputs a grid ID
        '''
        lon = point['points'][0]['lon']
        lat = point['points'][0]['lat']
        x = self.londict[lon]
        y = self.latdict[lat]
        gridid = self.grid[y, x]
        return gridid

    # Let's say we also a list of gridids
    def gridToPoint(self, gridid):
        '''
        Takes in a grid ID and outputs a plotly point dictionary
        '''
        y, x = np.where(self.grid == gridid)
        lon = self.londict_rev[int(x[0])]
        lat = self.latdict_rev[int(y[0])]
        point = {'points': [{'lon': lon, 'lat': lat}]}
        return point


class Index_Maps():
    '''
    This class creates a singular map as a function of some timeseries of
    rasters for use in the Ubuntu-Practice-Machine index comparison app.
    It also returns information needed for rendering.
    
    I think I could also incorporate the location data into this, include the
    correlation and area series functions, and simplify the logic built into
    the call backs.

    Initializing arguments:
            time_data (list)    = [[Year1, Year2], Month1, Month2,
                                   Month_Filter]
            function (string)   = 'mean_perc': 'Average Percentiles',
                                  'max': 'Maxmium Percentile',
                                  'min': 'Minimum Percentile',
                                  'mean_original': 'Mean Original Values',
                                  'omax': 'Maximum Original Value',
                                  'omin': 'Minimum Original Value',
                                  'ocv': 'Coefficient of Variation - Original'
            choice (string)     = 'noaa', 'pdsi', 'pdsisc', 'pdsiz', 'spi1',
                                  'spi2', 'spi3', 'spi6', 'spei1', 'spei2',
                                  'spei3', 'spei6', 'eddi1', 'eddi2', 'eddi3',
                                  'eddi6'
    '''
    # Create Initial Values
    def __init__(self, choice='pdsi', choice_type='original',
                 time_data=[[2000, 2018], [1, 12], list(range(1, 13))],
                 color_class='Default'):
        self.choice = choice  # This does not yet update information
        self.choice_type = choice_type
        self.color_class = color_class
        self.setData()
        self.index_ranges = pd.read_csv('data/tables/index_ranges.csv')
        self.time_data = time_data # This updates info but cannot be accessed  # <-- Help

    @property
    def time_data(self):
        return self.time_data

    @property
    def color_class(self):
        return self.color_class

    @time_data.setter
    def time_data(self, time_data):
        '''
        To avoid reading in a new dataset when only changing dates, this
        method is separate. It sets the beginning and end dates and months used
        in all of the calculations and updates an xarray reference called
        "dataset_interval".
        '''
        # Get the full data set
        dataset = self.dataset

        # Split up time information
        year1 = time_data[0][0]
        year2 = time_data[0][1]
        month1 = time_data[1][0]
        month2 = time_data[1][1]
        month_filter = time_data[2]

        # Filter the dataset by date and location
        d1 = dt.datetime(year1, month1, 1)
        d2 = dt.datetime(year2, month2, 1)
        d2 = d2 + relativedelta(months=+1) - relativedelta(days=+1)
        data = dataset.sel(time=slice(d1, d2))
        data = data.sel(time=np.in1d(data['time.month'], month_filter))

        # If this filters all of the data out, return a special "NA" data set
        if len(data.time) == 0:

            # Get the right resolution file
            res = data.crs.GeoTransform[1]
            res_print = str(res).replace('.', '_')
            na_path = 'data/rasters/na_banner_' + res_print + '.tif'

            # The whole data set just says "NA" using the value -9999
            today = dt.datetime.now()
            # base = dt.datetime(1900, 1, 1)
            na = readRaster(na_path, 1, -9999)[0]
            na = na * 0 - 9999
            # date_range = ((today.year - 1) - start.year) * 12 + today.month
            arrays = np.repeat(na[np.newaxis, :, :], 2, axis=0)
            arrays = da.from_array(arrays, chunks=100)
            # days = (today - base).days
            days = [today - dt.timedelta(30), today]

            lats = data.coords['lat'].data
            lons = data.coords['lon'].data
            array = xr.DataArray(arrays,
                                 coords={'time': days,
                                         'lat': lats,
                                         'lon': lons},
                                 dims={'time': 2,
                                       'lat': len(lats),
                                       'lon': len(lons)})
            data = xr.Dataset({'value': array})

        self.dataset_interval = data

        # I am also setting index ranges from the full data sets
        if self.choice_type =='percentile' or 'leri' in self.choice:
            self.data_min = 0
            self.data_max = 100
        else:
            ranges = self.index_ranges
            minimum = ranges['min'][ranges['index'] == self.choice].values[0]
            maximum = ranges['max'][ranges['index'] == self.choice].values[0]

            # For index value we want to be centered on zero
            limits = [abs(minimum), abs(maximum)]
            self.data_max = max(limits)
            self.data_min = self.data_max * -1

    @color_class.setter
    def color_class(self, value):
        '''
        This is tricky because the color can be a string pointing to
        a predefined plotly color scale, or an actual color scale, which is
        a list.
        '''
        options = {'Blackbody': 'Blackbody', 'Bluered': 'Bluered',
                   'Blues': 'Blues', 'Default': 'Default', 'Earth': 'Earth',
                   'Electric': 'Electric', 'Greens': 'Greens',
                   'Greys': 'Greys', 'Hot': 'Hot', 'Jet': 'Jet',
                   'Picnic': 'Picnic', 'Portland': 'Portland',
                   'Rainbow': 'Rainbow', 'RdBu': 'RdBu',  'Viridis': 'Viridis',
                   'Reds': 'Reds',
                   'RdWhBu': [[0.00, 'rgb(115,0,0)'],
                              [0.10, 'rgb(230,0,0)'],
                              [0.20, 'rgb(255,170,0)'],
                              [0.30, 'rgb(252,211,127)'],
                              [0.40, 'rgb(255, 255, 0)'],
                              [0.45, 'rgb(255, 255, 255)'],
                              [0.55, 'rgb(255, 255, 255)'],
                              [0.60, 'rgb(143, 238, 252)'],
                              [0.70, 'rgb(12,164,235)'],
                              [0.80, 'rgb(0,125,255)'],
                              [0.90, 'rgb(10,55,166)'],
                              [1.00, 'rgb(5,16,110)']],
                   'RdWhBu (Extreme Scale)':  [[0.00, 'rgb(115,0,0)'],
                                               [0.02, 'rgb(230,0,0)'],
                                               [0.05, 'rgb(255,170,0)'],
                                               [0.10, 'rgb(252,211,127)'],
                                               [0.20, 'rgb(255, 255, 0)'],
                                               [0.30, 'rgb(255, 255, 255)'],
                                               [0.70, 'rgb(255, 255, 255)'],
                                               [0.80, 'rgb(143, 238, 252)'],
                                               [0.90, 'rgb(12,164,235)'],
                                               [0.95, 'rgb(0,125,255)'],
                                               [0.98, 'rgb(10,55,166)'],
                                               [1.00, 'rgb(5,16,110)']],
                   'RdYlGnBu':  [[0.00, 'rgb(124, 36, 36)'],
                                  [0.25, 'rgb(255, 255, 48)'],
                                  [0.5, 'rgb(76, 145, 33)'],
                                  [0.85, 'rgb(0, 92, 221)'],
                                   [1.00, 'rgb(0, 46, 110)']],
                   'BrGn':  [[0.00, 'rgb(91, 74, 35)'],
                             [0.10, 'rgb(122, 99, 47)'],
                             [0.15, 'rgb(155, 129, 69)'],
                             [0.25, 'rgb(178, 150, 87)'],
                             [0.30, 'rgb(223,193,124)'],
                             [0.40, 'rgb(237, 208, 142)'],
                             [0.45, 'rgb(245,245,245)'],
                             [0.55, 'rgb(245,245,245)'],
                             [0.60, 'rgb(198,234,229)'],
                             [0.70, 'rgb(127,204,192)'],
                             [0.75, 'rgb(62, 165, 157)'],
                             [0.85, 'rgb(52,150,142)'],
                             [0.90, 'rgb(1,102,94)'],
                             [1.00, 'rgb(0, 73, 68)']]}

        # Default color schemes
        defaults = {'percentile': options['RdWhBu'],
                    'original':  options['BrGn'],
                    'area': options['RdWhBu'],
                    'correlation_o': 'Viridis',
                    'correlation_p': 'Viridis'}

        if value == 'Default':
            scale = defaults[self.choice_type]
        else:
            scale = options[value]

        self.color_scale = scale

    def setData(self):
        '''
        The challenge is to read as little as possible into memory without
        slowing the app down. So xarray and dask are lazy loaders, which means
        we can access the full dataset hear without worrying about that.
        '''
        # There are three types of datsets
        type_paths = {'original': 'data/droughtindices/netcdfs/',
                      'area': 'data/droughtindices/netcdfs/',
                      'correlation_o': 'data/droughtindices/netcdfs/',
                      'correlation_p':
                          'data/droughtindices/netcdfs/percentiles',
                      'percentile': 'data/droughtindices/netcdfs/percentiles',
                      'projected': 'data/droughtindices/netcdfs/albers'}

        # Build path and retrieve the data set
        netcdf_path =  type_paths[self.choice_type]
        file_path = os.path.join(data_path, netcdf_path, self.choice + '.nc')
        dataset = xr.open_dataset(file_path, chunks=100)  # <------------------ Best chunk size/shape?

        # Leri is the only dataset that has missing information
        if 'leri' in self.choice:
            dataset.value.data[dataset.value.data < 0] = np.nan

        # Set this as an attribute for easy retrieval
        self.dataset = dataset

    def setMask(self, location, crdict):
        '''
        Take a location object and the coordinate dictionary to create an
        xarray for masking the dask datasets without pulling into memory.
        
        location = location from Location_Builder or 1d array
        crdict = coordinate dictionary
        '''
        # Get x, y coordinates from location
        flag, y, x, label, idx = location
        mask = crdict.grid.copy()

        # Create mask array
        if flag != 'all':
            y = json.loads(y)
            x = json.loads(x)
            gridids = crdict.grid[y, x]
            mask[~np.isin(crdict.grid, gridids)] = np.nan
            mask = mask * 0 + 1
        else:
            mask = mask * 0 + 1

        # Set up grid info from coordinate dictionary
        geom = crdict.source.transform
        nlat, nlon = mask.shape   
        lons = np.arange(nlon) * geom[1] + geom[0]
        lats = np.arange(nlat) * geom[5] + geom[3]


        # Create mask xarray
        xmask = xr.DataArray(mask,
                             coords={'lat': lats,
                                     'lon': lons},
                             dims={'lat': len(lats),
                                   'lon': len(lons)})
        self.mask = xmask

    def getTime(self):
        # Now read in the corrollary albers data set
        dates = pd.DatetimeIndex(self.dataset_interval.time[:].values)
        year1 = min(dates.year)
        year2 = max(dates.year)
        month1 = min(dates.month)
        month2 = max(dates.month)
        month_filter = list(pd.unique(dates.month))
        time_data = [[year1, year2], [month1, month2], month_filter]

        return time_data        

    def getMean(self):
        return self.dataset_interval.mean('time').value.data

    def getMin(self):
        return self.dataset_interval.min('time').value.data

    def getMax(self):
        return self.dataset_interval.max('time').value.data

    def getSeries(self, location, crdict):
        '''
        This uses the mask to get a monthly time series of values at a
        specified location.
        '''
        # Get filtered dataset
        data = self.dataset_interval

        # Get the location coordinates
        flag, y, x, label, idx = location

        # Filter if needed and generate timeseries
        if flag == 'all':
            timeseries = data.mean(dim=('lat', 'lon'))
            timeseries = timeseries.value.values
        else:
            y = json.loads(y)
            x = json.loads(x)
            if flag == 'grid':
                timeseries = data.value[:, y, x].values
            else:
                self.setMask(location, crdict)
                data = data.where(self.mask == 1)
                timeseries = data.mean(dim=('lat', 'lon'))
                timeseries = timeseries.value.values

        # print("Area fitlering complete.")
        return timeseries

    def getCorr(self, location, crdict):
        '''
        Create a field of pearson's correlation coefficients with any one
        selection.
        '''
        ts = self.getSeries(location, crdict)
        arrays = self.dataset_interval.value.values
        one_field = correlationField(ts, arrays)

        return one_field

    def getArea(self, crdict):
        '''
        This will take in a time series of arrays and a drought severity
        category and mask out all cells with values above or below the category
        thresholds. If inclusive is 'True' it will only mask out all cells that
        fall above the chosen category.
    
        For now this requires original values, percentiles even out too quickly
        '''
        # Specify choice in case it needs to be inverse for eddi
        choice = self.choice
        data = self.dataset_interval

        # Now read in the corrollary albers data set
        time_data = self.getTime()
        choice_type = 'projected'
        proj_data = Index_Maps(choice, choice_type, time_data, 'RdWhBu')

        # Filter data by the mask (should be set already)
        masked_arrays = data.where(self.mask == 1)
        albers_mask = wgsToAlbers(masked_arrays, crdict, proj_data.dataset)
        arrays = proj_data.dataset_interval.where(albers_mask == 1).value

        # Flip if this is EDDI  # <-------------------------------------------- left off here
        if 'eddi' in choice:
            arrays = arrays*-1
    
        # Drought Categories
        # print("calculating drought area...")
        drought_cats = {'sp': {0: [-0.5, -0.8],
                               1: [-0.8, -1.3],
                               2: [-1.3, -1.5],
                               3: [-1.5, -2.0],
                               4: [-2.0, -999]},
                        'eddi': {0: [-0.5, -0.8],
                                 1: [-0.8, -1.3],
                                 2: [-1.3, -1.5],
                                 3: [-1.5, -2.0],
                                 4: [-2.0, -999]},
                        'pdsi': {0: [-1.0, -2.0],
                                 1: [-2.0, -3.0],
                                 2: [-3.0, -4.0],
                                 3: [-4.0, -5.0],
                                 4: [-5.0, -999]},
                        'leri': {0: [30, 20],
                                 1: [20, 10],
                                 2: [10, 5],
                                 3: [5, 2],
                                 4: [2, 0]}}
    
        # Choose a set of categories
        cat_key = [key for key in drought_cats.keys() if key in choice][0]
        cats = drought_cats[cat_key]
    
        def singleFilter(arrays, d, inclusive=False):
            '''
            There is some question about the Drought Severity Coverage Index. The
            NDMC does not use inclusive drought categories though NIDIS appeared to
            in the "Historical Character of US Northern Great Plains Drought"
            study. In an effort to match NIDIS' sample chart, we are using the
            inclusive method for now. It would be fine either way as long as the
            index is compared to other values with the same calculation, but we
            should really defer to NDMC. We could also add an option to display
            inclusive vs non-inclusive drought severity coverages.
            '''
            if inclusive:
                totals = arrays.where(~np.isnan(arrays)).count(dim=('lat', 'lon'))
                counts = arrays.where(arrays<d[0]).count(dim=('lat', 'lon'))
                ratios = counts / totals
                pcts = ratios.compute().data * 100
                return pcts
            else:
                totals = arrays.where(~np.isnan(arrays)).count(
                                                            dim=('lat', 'lon'))
                counts = arrays.where((arrays<d[0]) &
                                      (arrays>=d[1])).count(dim=('lat', 'lon'))
                ratios = counts / totals
                pcts = ratios.compute().data * 100
                return pcts

        # For each array
        def filter(arrays, d, inclusive=False):
            ps = singleFilter(arrays, d, inclusive)
            return ps
    
        # print("starting offending loops...")
        pnincs = np.array([filter(arrays, cats[i],
                                  inclusive=False)for i in range(5)])

        DSCI = np.nansum(np.array([pnincs[i]*(i+1) for i in range(5)]), axis=0)
        pincs = np.array([filter(arrays, cats[i],
                                 inclusive=True)for i in range(5)]) 

        # Return the list of five layers
        return pincs, pnincs, DSCI

    def getFunction(self, function):
        '''
        To choose which function to return using a string from a dropdown app. 
        '''
        functions = {"omean": self.getMean,
                     "omin": self.getMin,
                     "omax": self.getMax,
                     "pmean": self.getMean,
                     "pmin": self.getMin,
                     "pmax": self.getMax,
                     "oarea": self.getMean,  # <------------------------------- Note that this is returning the mean for now
                     "ocorr": self.getMean
                     }
        function = functions[function]

        return function()


class Location_Builder:
    '''
    This takes a location selection determined to be the triggering choice,
    decides what type of location it is, and builds the appropriate location
    list object needed further down the line. To do so, it holds county, 
    state, grid, and other administrative information.
    '''

    def __init__(self, trig_id, trig_val, coordinate_dictionary, admin_df,
                 state_array, county_array):
        self.trig_id = trig_id
        self.trig_val = trig_val
        self.cd = coordinate_dictionary
        self.admin_df = admin_df
        self.states_df = admin_df[['state', 'state_abbr',
                                   'state_fips']].drop_duplicates().dropna()
        self.state_array = state_array  
        self.county_array = county_array

    def chooseRecent(self):
        '''
        Check the location for various features to determine what type of
        selection it came from. Return a list with some useful elements.

        Possible triggering elements:

            'map_1.clickData',
            'map_2.clickData',
            'map_1.selectedData',
            'map_2.selectedData',
            'county_1.value',
            'county_2.value',
            'state_1.value',
            'state_2.value'
        '''
        trig_id = self.trig_id
        trig_val = self.trig_val
        admin_df = self.admin_df
        states_df = self.states_df
        cd = self.cd
        county_array = self.county_array
        state_array = self.state_array

        # print("Location Picker Trigger: " + str(trig_id))
        # print("Location Picker Value: " + str(trig_val))

        # 1: Selection is a county selection
        if 'county' in trig_id:
            county = admin_df['place'][admin_df.fips == trig_val].unique()[0]
            y, x = np.where(county_array == trig_val)
            location = ['county', str(list(y)), str(list(x)), county]

        # 2: Selection is a single grid IDs
        elif 'clickData' in trig_id:
            lon = trig_val['points'][0]['lon']
            lat = trig_val['points'][0]['lat']
            x = cd.londict[lon]
            y = cd.latdict[lat]
            gridid = cd.grid[y, x]
            counties = admin_df['place'][admin_df.grid == gridid]
            county = counties.unique()
            label = county[0] + ' (Grid ' + str(int(gridid)) + ')'
            location = ['grid', str(y), str(x), label]        

        # 3: Selection is a set of grid IDs
        elif 'selectedData' in trig_id:
            if trig_val is not None:
                selections = trig_val['points']
                y = list([cd.latdict[d['lat']] for d in selections])
                x = list([cd.londict[d['lon']] for d in selections])
                try:
                    counties = np.array([d['text'][:d['text'].index(' (')] for
                                     d in selections])
                except:
                    counties = np.array([d['text'][:d['text'].index(':')] for
                                     d in selections])
                local_df = admin_df[admin_df['place'].isin(
                                    list(np.unique(counties)))]
    
                # Use gradient to print NW and SE most counties as a range
                NW = local_df['place'][
                    local_df['gradient'] == min(local_df['gradient'])].item()
                SE = local_df['place'][
                    local_df['gradient'] == max(local_df['gradient'])].item()
                label = NW + " to " + SE
                location = ['grids', str(y), str(x), label]        
            else:
                raise PreventUpdate

        # 2: location is a list of states
        elif 'update' in trig_id:
            # Selection is the default 'all'
            if type(trig_val) is str:
                location = ['all',  'y', 'x', 'Contiguous United States']
        
            # Empty list, default to CONUS
            elif len(trig_val) == 0:
                location = ['all',  'y', 'x', 'Contiguous United States']

            # A selection of 'all' within a list
            elif len(trig_val) == 1 and trig_val[0] == 'all':
                location = ['all',  'y', 'x', 'Contiguous United States']

            # Single or multiple, not 'all' or empty, state or list of states
            elif len(trig_val) >= 1:
                # Return the mask, a flag, and the state names
                state = list(states_df['state_abbr'][
                             states_df['state_fips'].isin(trig_val)])

                if len(state) < 4:  # Spell out full state name in title
                    state = [states_df['state'][
                             states_df['state_abbr']==s].item() for s in state]
                states = ", ".join(state)
                y, x = np.where(np.isin(state_array, trig_val))

                # And return the location information
                location = ['state', str(list(y)), str(list(x)), states]

        # 3: location is the basename of a shapefile saved as temp.shp
        elif 'shape' in trig_id:
            # We don't have the x,y values just yet
            try:
                shp = gdal.Open('data/shapefiles/temp/temp.tif').ReadAsArray()
                shp[shp==-9999] = np.nan
                y, x = np.where(~np.isnan(shp))
                location = ['shape', str(list(y)), str(list(x)), trig_val]
            except:
                location = ['all', 'y', 'x', 'Contiguous United States']

        return location
