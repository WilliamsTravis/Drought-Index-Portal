# -*- coding: utf-8 -*-
"""
Support functions for Ubunut-Practice-Machine
Created on Tue Jan 22 18:02:17 2019

@author: User
"""
import datetime as dt
from dash.exceptions import PreventUpdate
from dateutil.relativedelta import relativedelta
import gc
from glob import glob
import json
from collections import OrderedDict
import os
from osgeo import gdal, ogr, osr  # pcjericks.github.io/py-gdalogr-cookbook/index.html
import matplotlib.pyplot as plt
from netCDF4 import Dataset
from numba import jit
import numpy as np
import pandas as pd
from pyproj import Proj
import salem
from scipy.stats import rankdata
import time
from tqdm import tqdm
import sys
import xarray as xr

# Check if windows or linux
if sys.platform == 'win32':
    data_path = 'f:/'
else:
    home_path = '/root/Sync'
    data_path = '/root/Sync'


####### Variables #############################################################
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


######## Functions ############################################################
def areaSeries(location, arrays, dates, mask, state_array, albers_source, cd,
               reproject=False):
    '''
    location = list output from app.callback function 'locationPicker'
    arrays = a time series of arrays falling into each of 5 drought categories
    inclusive = whether or to categorize drought by including all categories
    '''
    if len(location) > 4:
        flag, y, x, label, idx = location
        y = json.loads(y)
        x = json.loads(x)
        if type(y) is not list:
            timeseries = np.array([round(a[y, x], 4) for a in arrays])
        else:
            gridids = cd.grid[y, x]
            area_mask = cd.grid.copy()
            area_mask[~np.isin(cd.grid, gridids)] = np.nan
            area_mask = area_mask * 0 + 1
            arrays = arrays  * area_mask
            timeseries = np.array([round(np.nanmean(a), 4) for a in arrays])

    else:
        arrays = arrays * mask
        flag, states, label, idx = location
        timeseries = np.array([round(np.nanmean(a), 4) for a in arrays])

    # If we are sending the output to the drought area function  # < ---------- Why not just put that in the drought area function? Because this could be useful here later.
    if reproject:
        arrays = wgsToAlbers(arrays, cd, albers_source)

    # print("Area fitlering complete.")
    return [timeseries, arrays, label]


def calculateCV(indexlist):
    '''
     A single array showing the distribution of coefficients of variation
         throughout the time period represented by the chosen rasters
    '''
    # is it a named list or not?
    if type(indexlist[0]) is list:
        # Get just the arrays from this
        indexlist = [a[1] for a in indexlist]
    else:
        indexlist = indexlist

    # Adjust for outliers
    sd = np.nanstd(indexlist)
    thresholds = [-3*sd, 3*sd]
    for a in indexlist:
        a[a <= thresholds[0]] = thresholds[0]
        a[a >= thresholds[1]] = thresholds[1]

    # Standardize Range
    indexlist = standardize(indexlist)

    # Simple Cellwise calculation of variance
    sds = np.nanstd(indexlist, axis=0)
    avs = np.nanmean(indexlist, axis=0)
    covs = sds/avs

    return covs

def coordinateDictionaries(source):
        # Geometry
        x_length = source.shape[2]
        y_length = source.shape[1]
        res = source.res[0]
        lon_min = source.transform[0]
        lat_max = source.transform[3] - res
        xs = range(x_length)
        ys = range(y_length)
        lons = [lon_min + res*x for x in xs]
        lats = [lat_max - res*y for y in ys]

        # Dictionaires with coordinates and array index positions
        londict = dict(zip(lons, xs))
        latdict = dict(zip(lats, ys))

        return londict, latdict, res


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
            cor = np.corrcoef(ts, lst)[0,1]
            one_field[i, j] = cor

    return one_field


def droughtArea(arrays, choice, inclusive=False):
    '''
    This will take in a time series of arrays and a drought severity
    category and mask out all cells with values above or below the category
    thresholds. If inclusive is 'True' it will only mask out all cells that
    fall above the chosen category.

    For now this requires original values, percentiles even out too quickly
    '''
    # Flip if this is EDDI
    if 'eddi' in choice:
        arrays = arrays*-1

    # Drought Categories
    print("calculating drought area...")
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

    # Total number of pixels
    mask = arrays[0] * 0 + 1  # <---------------------------------------------- With Leri, NA values change the total area for each time step
    total_area = np.nansum(mask)

    def singleFilter(array, d, inclusive=False):
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
            mask = array<d[0]
        else:
            mask = (array<d[0]) & (array>=d[1])
        return array[mask]

    # For each array
    def filter(arrays, d, inclusive=False):
        values = np.array([singleFilter(a, d, inclusive=inclusive) for
                            a in arrays])
        totals = [len(a[~np.isnan(a)]) for a in arrays]  # <------------------- Because the available area for LERI changes, this adjust the total area for each time step
        ps = np.array([(len(values[i])/totals[i]) * 100 for
                       i in range(len(values))])
        return ps

    print("starting offending loops...")
    pnincs = np.array([filter(arrays, cats[i]) for i in range(5)])
    DSCI = np.nansum(np.array([pnincs[i]*(i+1) for i in range(5)]), axis=0)
    pincs = [np.sum(pnincs[i:], axis=0) for i in range(5)]  # <---------------- ~60 microseconds with 18 year record (compare to 150 milliseconds to start over :)

    # Return the list of five layers
    print("drought area calculations complete.")
    return pincs, pnincs, DSCI


def im(array):
    '''
    This just plots an array as an image
    '''
    # plt.close()
    # window = plt.get_current_fig_manager()
    # window.canvas.manager.window.raise_()
    # plt.close()
    fig = plt.imshow(array)
    fig.figure.canvas.raise_()


def isInt(string):
    try:
        int(string)
        return True
    except:
        return False


def makeMap(maps, function):
    '''
    To choose which function to return from Index_Maps

    Production Notes:

    '''
    gc.collect()
    if function == "omean":
        data = maps.meanOriginal()
    if function == "omax":
        data = maps.maxOriginal()
    if function == "omin":
        data = maps.minOriginal()
    if function == "pmean":
        data = maps.meanPercentile()
    if function == "pmax":
        data = maps.maxPercentile()
    if function == "pmin":
        data = maps.minPercentile()
    if function == "ocv":
        data = maps.coefficientVariation()
    if function == "oarea":
        data = maps.meanOriginal()
    if function == "ocorr":
        data = maps.meanOriginal()
    if function == "pcorr":
        data = maps.meanPercentile()
    return data


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

        pct = rankdata(lst)/len(lst)
        return pct

    # mask = arrays[-10, :, :] * 0 + 1  # Don't use the first or last (if empty)
    pcts = np.apply_along_axis(percentiles, axis=0, arr=arrays)
    # pcts = pcts*mask
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


############ Construction Zone ###############################################
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

############ Construction Zone ###############################################

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


def toNetCDF2(tfiles, ncfiles, savepath, index, year1, month1,
              year2, month2, epsg=4326, percentiles=False,
              wmode='w'):
    '''
    Take multiple multiband netcdfs with unordered dates and multiple tiffs
    with desired geometries and write to a single netcdf as a single time
    series. This has a lot of options and is only meant for the app.

    As an expediency, if there isn't an nc file it defaults to reading dates
    from the file names.

    Test parameters for toNetCDF2
        tfiles = glob('f:/data/droughtindices/netcdfs/wwdt/tifs/*tif')
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
    try:
        test = Dataset(ncfiles[0])
        test.close()
        print("Combining data using netcdf dates..")
        date_tifs = {}
        for i in range(len(ncfiles)):
            nc = Dataset(ncfiles[i])
            days = nc.variables['day'][:]  # This is in days since 1900
            rasters = gdal.Open(tfiles[i])
            arrays = rasters.ReadAsArray()
            for y in range(len(arrays)):
                date_tifs[days[y]] = arrays[y]  # <-------------------------------- I believe this is whats breaking the WWDT script, different length arrays.
    
        # okay, that was just in case the dates wanted to bounce around
        date_tifs = OrderedDict(sorted(date_tifs.items()))
    
        # Now that everything is in the right order, split them back up
        days = np.array(list(date_tifs.keys()))
        arrays = np.array(list(date_tifs.values()))

    except Exception as e:
        print(str(e))
        print('Combininb data using filename dates...')
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
    start = dt.datetime(year1, month1, 1) # <--------------------------------- Careful about this day figure
    day1 = start - base
    day1 = day1.days
    end = dt.datetime(year2, month2, 1)  # <---------------------------------- This is also important because of empty slots in the wwdt data, specify the current date in the call
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


def toNetCDFPercentile(src_path, dst_path):
    '''
    This causes memory problems in less powerful computers.
    
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
      

def toRasters(arraylist,path,geometry,srs):
    """
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
          

# WGS
def wgsToAlbers(arrays, cd, albers_source):
    dates = range(len(arrays))
    wgs_proj = Proj(init='epsg:4326')
    geom = cd.source.transform
    wgrid = salem.Grid(nxny=(cd.x_length, cd.y_length), dxdy=(cd.res, -cd.res),
                       x0y0=(geom[0], geom[3]), proj=wgs_proj)
    lats = np.unique(wgrid.xy_coordinates[1])
    lats = lats[::-1]
    lons = np.unique(wgrid.xy_coordinates[0])
    data_array = xr.DataArray(data=arrays,
                              coords=[dates, lats, lons],
                              dims=['time', 'lat', 'lon'])
    wgs_data = xr.Dataset(data_vars={'value': data_array})

    # Albers Equal Area Conic North America (epsg not working)
    albers_proj = Proj('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 \
                        +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 \
                        +datum=NAD83 +units=m +no_defs')

    # Create an albers grid
    geom = albers_source.GetGeoTransform()
    array = albers_source.ReadAsArray()
    res = geom[1]
    x_length = albers_source.RasterXSize 
    y_length = albers_source.RasterYSize 
    agrid = salem.Grid(nxny=(x_length, y_length), dxdy=(res, -res),
                       x0y0=(geom[0], geom[3]), proj=albers_proj)
    lats = np.unique(agrid.xy_coordinates[1])
    lats = lats[::-1]
    lons = np.unique(agrid.xy_coordinates[0])
    data_array = xr.DataArray(data=array,
                              coords=[lats, lons],
                              dims=['lat', 'lon'])
    albers_data = xr.Dataset(data_vars={'value': data_array})
    albers_data.salem.grid._proj = albers_proj
    projection = albers_data.salem.transform(wgs_data, 'linear')
    arrays = projection.value.data
    return(arrays)


################################ classes ######################################
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
        fips = pd.read_csv('data/tables/US_FIPS_Codes.csv', skiprows=1, index_col=0)
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
        ds = None


    def getElements(self):
        '''
        I want to turn this into a class that handles all resolution dependent
        objects, but for now I'm just tossing this together for a meeting.
        '''
        # Get paths
        [grid_path, gradient_path, county_path, state_path,
         source_path, albers_path, admin_path] = self.pathRequest()
    
        # Read in objects
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
            data.close()

        # We actually want full state-county fips for counties
        # Stack both into one
        state_counties = np.stack([states, cnty])

        # Our function will take as the input a list [state fips, county fips]
        # for each index position on the map
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

        if not os.path.exists(county_path) or not os.path.exists(state_path):
            self.buildAdmin()
        if not os.path.exists(grid_path) or not os.path.exists(gradient_path):
            self.buildGrid()
        if not os.path.exists(source_path) or not os.path.exists(albers_path):
            self.buildSource()
        if not os.path.exists(admin_path):
            self.buildAdminDF()
    
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
            ops = ['-at', '-a ' + attribute]
        else:
            ops = ['ATTRIBUTE=' + attribute]

        # Finally rasterize
        gdal.RasterizeLayer(trgt, [1], layer, options=ops)

        # Close target raster
        trgt = None
        src_data = None
    
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
    This translates numpy coordinates to geographic coordinates and back.
    
    Production notes:
        - I think this would also be a good place to parameterize all
            resolution specific elements of the application
        - These elements include:
            1) the grid
            2) the grid gradient
            3) the counties raster
            4) the counties data frame
            5) the states raster
            6) the states data frame
            7) the source array
            8) the source albers nc file
    '''
    def __init__(self, source_path, grid):
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

        Initializing arguments:
            timerange (list)    = [[Year1, Year2], [Month1, Month2]]
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

        Each function returns:

            array      = Singular 2D Numpy array of function output
            arrays     = Timeseries of 2D Numpy arrays within time range
            dates      = List of Posix time stamps
            dmax       = maximum value of array
            dmin       = minimum value of array
    '''

    # Reduce memory by preallocating attribute slots
    __slots__ = ('year1', 'year2', 'month1', 'month2', 'function',
                 'colorscale', 'reverse', 'choice')

    # Create Initial Values
    def __init__(self, time_range=[[2000, 2017], [1, 12]],
                 colorscale='Viridis',reverse='no', choice='pdsi'):
        self.year1 = time_range[0][0]
        self.year2 = time_range[0][1]
        if self.year1 == self.year2:
            self.month1 = time_range[1][0]
            self.month2 = time_range[1][1]
        else:
            self.month1 = 1
            self.month2 = 12
        self.colorscale = colorscale
        self.reverse = reverse
        self.choice = choice


    def setColor(self, default='percentile'):
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
                   'RdWhBu (NOAA PSD Scale)':  [[0.00, 'rgb(115,0,0)'],
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
                   'BrGn':  [[0.00, 'rgb(91, 74, 35)'],  #darkest brown
                             [0.10, 'rgb(122, 99, 47)'], # almost darkest brown
                             [0.15, 'rgb(155, 129, 69)'], # medium brown
                             [0.25, 'rgb(178, 150, 87)'],  # almost meduim brown
                             [0.30, 'rgb(223,193,124)'],  # light brown
                             [0.40, 'rgb(237, 208, 142)'],  #lighter brown
                             [0.45, 'rgb(245,245,245)'],  # white
                             [0.55, 'rgb(245,245,245)'],  # white
                             [0.60, 'rgb(198,234,229)'],  #lighter green
                             [0.70, 'rgb(127,204,192)'],  # light green
                             [0.75, 'rgb(62, 165, 157)'],  # almost medium green
                             [0.85, 'rgb(52,150,142)'],  # medium green
                             [0.90, 'rgb(1,102,94)'],  # almost darkest green
                             [1.00, 'rgb(0, 73, 68)']], # darkest green
                   }

        if self.colorscale == 'Default':
            if default == 'percentile':
                scale = options['RdWhBu']
            elif default == 'original':
                scale = options['BrGn']
            elif default == 'cv':
                scale = options['Portland']
        else:
            scale = options[self.colorscale]
        return scale


    def getData(self, array_path):
        '''
        The challenge is to read as little as possible into memory without
        slowing the app down.
        '''
        # Get time series of values
        # filter by date and location
        d1 = dt.datetime(self.year1, self.month1, 1)
        d2 = dt.datetime(self.year2, self.month2, 1)
        d2 = d2 + relativedelta(months=+1) - relativedelta(days=+1)  # last day

        with xr.open_dataset(array_path) as data:
            data = data.sel(time=slice(d1, d2))
            indexlist = data
            res = indexlist.crs.GeoTransform[1]
            del data
        
        if 'leri' in self.choice:
            arrays = indexlist.value.data
            arrays[arrays < 0] = np.nan
            indexlist.value.data = arrays

        return indexlist, res


    def getOriginal(self):
        '''
        Retrieve Original Timeseries
        '''
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/",
                                  self.choice + '.nc')
        indexlist, res = self.getData(array_path)
        limits = [abs(np.nanmin(indexlist.value.data)),
                  abs(np.nanmax(indexlist.value.data))]
        dmax = max(limits)  # Makes an even graph
        dmin = dmax*-1
        gc.collect()
        return [indexlist, dmin, dmax, res]


    def getPercentile(self):
        '''
        Retrieve Percentiles of Original Timeseries
        '''
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/percentiles",
                                  self.choice + '.nc')
        indexlist, res = self.getData(array_path)
        indexlist.value.data = indexlist.value.data * 100

        # We want the color scale to be centered on 50, first get max/min
        dmax = np.nanmax(indexlist.value.data)
        dmin = np.nanmin(indexlist.value.data)

        # The maximum distance from 50
        delta = max([dmax - 50, 50 - dmin])

        # The same distance above and below 50
        dmin = 50 - delta
        dmax = 50 + delta

        gc.collect()

        return [indexlist, dmin, dmax, res]


    def getAlbers(self):
        '''
        Retrieve Percentiles of Original Timeseries in North American
        Albers Equal Area Conic.
        '''
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/albers",
                                  self.choice + '.nc')
        indexlist, res = self.getData(array_path)
        limits = [abs(np.nanmin(indexlist.value.data)),
                  abs(np.nanmax(indexlist.value.data))]
        dmax = max(limits)  # Makes an even graph
        dmin = dmax*-1
        gc.collect()
        return [indexlist, dmin, dmax, res]


    def calculateCV(indexlist):
        '''
         A single array showing the distribution of coefficients of variation
             throughout the time period represented by the chosen rasters
        '''
        # is it a named list or not?
        if type(indexlist[0]) is list:
            # Get just the arrays from this
            indexlist = [a[1] for a in indexlist]
        else:
            indexlist = indexlist

        # Adjust for outliers
        sd = np.nanstd(indexlist)
        thresholds = [-3*sd, 3*sd]
        for a in indexlist:
            a[a <= thresholds[0]] = thresholds[0]
            a[a >= thresholds[1]] = thresholds[1]

        # Standardize Range
        indexlist = standardize(indexlist)

        # Simple Cellwise calculation of variance
        sds = np.nanstd(indexlist, axis=0)
        avs = np.nanmean(indexlist, axis=0)
        covs = sds/avs

        return covs


    def meanOriginal(self):
        '''
        Calculate mean of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax, res] = self.getOriginal()

        # Get data
        array = indexlist.mean('time').value.data  # <------------------------- This seems to be miscalculating 
        arrays = indexlist.value.data
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='original')

        # EDDI has a reversed scale
        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [array, arrays, dates, colorscale, dmax, dmin, reverse, res]


    def maxOriginal(self):
        '''
        Calculate max of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax, res] = self.getOriginal()

        # Get data
        array = indexlist.max('time').value.data
        arrays = indexlist.value.data
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='original')

        # EDDI has a reversed scale
        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [array, arrays, dates, colorscale, dmax, dmin, reverse, res]


    def minOriginal(self):
        '''
        Calculate max of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax, res] = self.getOriginal()

        # Get data
        array = indexlist.min('time').value.data
        arrays = indexlist.value.data
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='original')

        # EDDI has a reversed scale
        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False
        return [array, arrays, dates, colorscale, dmax, dmin, reverse, res]


    def meanPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax, res] = self.getPercentile()

        # Get data
        array = indexlist.mean('time').value.data
        arrays = indexlist.value.data
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='percentile')

        # EDDI has a reversed scale
        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False
        return [array, arrays, dates, colorscale, dmax, dmin, reverse, res]


    def maxPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
         # Get time series of values
        [indexlist, dmin, dmax, res] = self.getPercentile()

        # Get data
        array = indexlist.max('time').value.data
        arrays = indexlist.value.data
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='percentile')

        # EDDI has a reversed scale
        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [array, arrays, dates, colorscale, dmax, dmin, reverse, res]


    def minPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
         # Get time series of values
        [indexlist, dmin, dmax, res] = self.getPercentile()

        # Get data
        array = indexlist.min('time').value.data
        arrays = indexlist.value.data
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='percentile')

        # EDDI has a reversed scale
        if 'eddi' in self.choice:
            reverse = True
        else:
            reverse = False

        return [array, arrays, dates, colorscale, dmax, dmin, reverse, res]


    def coefficientVariation(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax, res] = self.getOriginal()

        # Get data
        arrays = indexlist.value.data
        array = calculateCV(arrays)
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='cv')

        # The colorscale will always mean the same thing
        reverse = False

        return [array, arrays, dates, colorscale, dmax, dmin, reverse, res]


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
        self.admin_df = admin_df  # <------------------------------------------ Here down can be read in with a resolution value
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
            location = ['county_id', str(list(y)), str(list(x)), county]

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
            location = ['grid_id',str(y), str(x), label]        

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
                # if NW != SE:
                label = NW + " to " + SE
                # else:
                    # label = NW
                location = ['grid_ids', str(y), str(x), label]        
            else:
                raise PreventUpdate

        # 2: location is a list of states
        elif 'update' in trig_id:
            # Selection is the default 'all'
            if type(trig_val) is str:
                location = ['state_mask', 'all', 'Contiguous United States']
        
            # Empty list, default to CONUS
            elif len(trig_val) == 0:
                location = ['state_mask', 'all', 'Contiguous United States']

            # A selection of 'all' within a list
            elif len(trig_val) == 1 and trig_val[0] == 'all':
                location = ['state_mask', 'all', 'Contiguous United States']

            # Single or multiple, not 'all' or empty, state or list of states
            elif len(trig_val) >= 1:
                # Return the mask, a flag, and the state names
                state = list(states_df['state_abbr'][
                             states_df['state_fips'].isin(trig_val)])

                if len(state) < 4:  # Spell out full state name in title
                    state = [states_df['state'][
                             states_df['state_abbr']==s].item() for s in state]
                
                states = ", ".join(state)

                # Now get the right x, y positions
                # state_mask = state_array.copy()
                
                y, x = np.where(np.isin(state_array, trig_val))
                # state_mask[~np.isin(state_mask, trig_val)] = np.nan
                # area_mask = state_mask * 0 + 1

                # And return the location information
                location = ['state_mask', str(list(y)), str(list(x)), states]

        # 3: location is the basename of a shapefile saved as temp.shp
        elif 'shape' in trig_id:
            # We don't have the x,y values just yet
            try:
                shp = gdal.Open('data/shapefiles/temp/temp.tif').ReadAsArray()
                shp[shp==-9999] = np.nan
                y, x = np.where(~np.isnan(shp))
                location = ['shape_mask', str(list(y)), str(list(x)), trig_val]
            except:
                location = ['state_mask', 'all', 'Contiguous United States']
        return location
