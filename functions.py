# -*- coding: utf-8 -*-
"""
Support functions for Ubunut-Practice-Machine
Created on Tue Jan 22 18:02:17 2019

@author: User
"""
import datetime as dt
from dateutil.relativedelta import relativedelta
import gc
import json
import matplotlib.pyplot as plt
import numpy as np
import os
from osgeo import gdal
import pandas as pd
from pyproj import Proj
import salem
from scipy.stats import rankdata
import sys
import xarray as xr

# Check if windows or linux
if sys.platform == 'win32':
    data_path = 'f:/'
    sys.path.extend(['Z:/Sync/Ubuntu-Practice-Machine/',
                     'C:/Users/travi/github/Ubuntu-Practice-Machine',
                     'C:/Users/User/github/Ubuntu-Practice-Machine'])
else:
    home_path = '/root/Sync'
    data_path = '/root/Sync'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))


####### Variables #############################################################
grid = np.load("data/npy/prfgrid.npz")["grid"]
state_array = gdal.Open('data/rasters/us_states.tif').ReadAsArray()
mask = state_array * 0 + 1

######## Functions ############################################################
def areaSeries(location, arrays, dates, reproject=False):
    '''
    location = list output from app.callback function 'locationPicker'
    arrays = a time series of arrays falling into each of 5 drought categories
    inclusive = whether or to categorize drought by including all categories
    '''
    print("areaSeries location: " + str(location))
    if type(location[0]) is int:
        print("Location is singular")
        y, x, label, idx = location
        timeseries = np.array([round(a[y, x], 4) for a in arrays])

    else:
        if location[0] == 'state_mask':
            flag, states, label, idx = location
            if states != 'all':
                states = json.loads(states)
                state_mask = state_array.copy()
                state_mask[~np.isin(state_mask, states)] = np.nan
                state_mask = state_mask * 0 + 1
            else:
                state_mask = mask
            arrays = arrays * state_mask
        else:
            # Collect array index positions and other information for print
            y, x, label, idx = location
            x = json.loads(x)
            y = json.loads(y)

            # Create a location mask and filter the arrays
            ys = np.array(y)
            xs = np.array(x)
            loc_mask = arrays[0].copy()
            loc_mask[ys, xs] = 9999
            loc_mask[loc_mask<9999] = np.nan
            loc_mask = loc_mask * 0 + 1
            arrays = arrays * loc_mask
        
        # Timeseries of mean values
        timeseries = np.array([round(np.nanmean(a), 4) for a in arrays])

    # If we are sending the output to the drought area function
    if reproject:
        print("Reprojecting to Alber's")
        arrays = wgsToAlbers(arrays)

    print("Area fitlering complete.")
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

def droughtArea(arrays, choice, inclusive=False):
    '''
    This will take in a time series of arrays and a drought severity
    category and mask out all cells with values above or below the category
    thresholds. If inclusive is 'True' it will only mask out all cells that
    fall above the chosen category.

    For now this requires original values, percentiles even out too quickly
    '''

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
                    'pdsi': {0:[-1.0, -2.0],
                             1: [-2.0, -3.0],
                             2: [-3.0, -4.0],
                             3: [-4.0, -5.0],
                             4: [-5.0, -999]}}

    # Choose a set of categories
    cat_key = [key for key in drought_cats.keys() if key in choice][0]
    cats = drought_cats[cat_key]

    # Total number of pixels
    mask = arrays[0] * 0 + 1
    total_area = np.nansum(mask)

    # We want an ndarray for each category
    # @jit  # <---------------------------------------------------------------- Possible way to speed this up, but not quite that simple
    def rangeFilter(a, d, inclusive):
        '''
        There is somem question about the Drought Severity Coverage Index. The
        NDMC does not use inclusive drought categories though NIDIS appeared to
        in the "Historical Character of US Northern Great Plains Drought"
        study. In an effort to match NIDIS' sample chart, we are using the
        inclusive method for now. It would be fine either way as long as the
        index is compared to other values with the same calculation, but we
        should really defer to NDMC. We could also add an option to display
        inclusive vs non-inclusive drought severity coverages.
        '''
        # Filter above or below thresholds
        # ac = a.copy()
        if inclusive is False:
            ac[(ac >= d[0]) | (ac < d[1])] = np.nan
        else:
            a[a > d[0]] = np.nan
        area = a*0+1
        ps = [(np.nansum(b)/total_area) * 100 for b in area]
        return ps

    print("starting offending loops...")
    p = {}
    for i in range(5):  # <---------------------------------------------------- Slowest part of whole app
        d = cats[i]
        ps = rangeFilter(arrays, d, inclusive=True)
        p[i] = ps

    DSCI = np.array([np.array(p[key]) for key in p.keys()])
    DSCI = np.array([DSCI[i]*(i+1) for i in range(5)])
    DSCI = np.sum(DSCI, axis=0)
    DSCI = DSCI/15
    p = [i for key, i in p.items()]
    p.insert(3, list(DSCI))

    # Return a list of five layers, the signal might need to be adjusted
    # for inclusive
    print("drought area calculations complete.")
    return p


def im(array):
    '''
    This just plots an array as an image
    '''
    plt.imshow(array)


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
        data = maps.meanOriginal()  # This will require some extra doing...
    return data


# For making outlines...move to css, maybe
def outLine(color, width):
    string = ('-{1}px -{1}px 0 {0}, {1}px -{1}px 0 {0}, ' +
              '-{1}px {1}px 0 {0}, {1}px {1}px 0 {0}').format(color, width)
    return string


def percentileArrays(arrays):
    '''
    a list of 2d numpy arrays or a 3d numpy array
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
    pcts = pcts*mask
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


# WGS
def wgsToAlbers(arrays):
    dates = range(len(arrays))
    wgs_proj = Proj(init='epsg:4326')
    wgrid = salem.Grid(nxny=(300, 120), dxdy=(0.25, -0.25),
                       x0y0=(-130, 50), proj=wgs_proj)
    lats = np.unique(wgrid.xy_coordinates[1])
    lats = lats[::-1]
    lons = np.unique(wgrid.xy_coordinates[0])
    data_array = xr.DataArray(data=arrays,
                              coords=[dates, lats, lons],
                              dims=['time', 'lat', 'lon'])
    wgs_data = xr.Dataset(data_vars={'value': data_array})

    # Albers Equal Area Conic North America
    albers_proj = Proj('+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 \
                       +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 \
                       +datum=NAD83 +units=m +no_defs')
    with salem.open_xr_dataset(os.path.join(data_path,
				 'data/droughtindices/netcdfs/albers/albers.nc')) as data:
        albers = data
        albers.salem.grid._proj = albers_proj  # Something was off here
        data.close()

    projection = albers.salem.transform(wgs_data, 'linear')
    arrays = projection.value.data
    return(arrays)


################################ classes ######################################
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
    This translates numpy coordinates to geographic coordinates and back
    '''
    def __init__(self, source_path):
        self.source = xr.open_dataarray(source_path)
        self.grid = grid  #  <------------------------------------------------- best way to make a custom grid from source?

        # Geometry
        self.x_length = self.source.shape[2]
        self.y_length = self.source.shape[1]
        self.res = self.source.res[0]
        self.lon_min = self.source.transform[0]
        self.lat_max = self.source.transform[3] - self.res
        self.xs = range(self.x_length)
        self.ys = range(self.y_length)
        self.lons = [self.lon_min + self.res*x for x in self.xs]
        self.lats = [self.lat_max - self.res*y for y in self.ys]

        # Dictionaires with coordinates and array index positions
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
                 'colorscale', 'reverse', 'choice', 'grid', 'mask')

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
        self.grid = np.load(os.path.join(data_path,
                                         "data/prfgrid.npz"))["grid"]
        self.mask = self.grid * 0 + 1


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
            del data

        return indexlist


    def getOriginal(self):
        '''
        Retrieve Original Timeseries
        '''
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/",
                                  self.choice + '.nc')
        indexlist = self.getData(array_path)
        limits = [abs(np.nanmin(indexlist.value.data)),
                  abs(np.nanmax(indexlist.value.data))]
        dmax = max(limits)  # Makes an even graph
        dmin = dmax*-1
        gc.collect()
        return [indexlist, dmin, dmax]


    def getPercentile(self):
        '''
        Retrieve Percentiles of Original Timeseries
        '''
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/percentiles",
                                  self.choice + '.nc')
        indexlist = self.getData(array_path)
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

        return [indexlist, dmin, dmax]


    def getAlbers(self):
        '''
        Retrieve Percentiles of Original Timeseries in North American
        Albers Equal Area Conic.
        '''
        array_path = os.path.join(data_path,
                                  "data/droughtindices/netcdfs/albers",
                                  self.choice + '.nc')
        indexlist = self.getData(array_path)
        limits = [abs(np.nanmin(indexlist.value.data)),
                  abs(np.nanmax(indexlist.value.data))]
        dmax = max(limits)  # Makes an even graph
        dmin = dmax*-1
        gc.collect()
        return [indexlist, dmin, dmax]


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
        [indexlist, dmin, dmax] = self.getOriginal()

        # Get data
        array = indexlist.mean('time').value.data
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

        return [array, arrays, dates, colorscale, dmax, dmin, reverse]


    def maxOriginal(self):
        '''
        Calculate max of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax] = self.getOriginal()

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

        return [array, arrays, dates, colorscale, dmax, dmin, reverse]


    def minOriginal(self):
        '''
        Calculate max of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax] = self.getOriginal()

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
        return [array, arrays, dates, colorscale, dmax, dmin, reverse]


    def meanPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax] = self.getPercentile()

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
        return [array, arrays, dates, colorscale, dmax, dmin, reverse]


    def maxPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
         # Get time series of values
        [indexlist, dmin, dmax] = self.getPercentile()

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

        return [array, arrays, dates, colorscale, dmax, dmin, reverse]


    def minPercentile(self):
        '''
        Calculate mean of percentiles of original index values
        '''
         # Get time series of values
        [indexlist, dmin, dmax] = self.getPercentile()

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

        return [array, arrays, dates, colorscale, dmax, dmin, reverse]


    def coefficientVariation(self):
        '''
        Calculate mean of percentiles of original index values
        '''
        # Get time series of values
        [indexlist, dmin, dmax] = self.getOriginal()

        # Get data
        arrays = indexlist.value.data
        array = calculateCV(arrays)
        dates = indexlist.time.data
        del indexlist

        # Get color scale
        colorscale = self.setColor(default='cv')

        # The colorscale will always mean the same thing
        reverse = False

        return [array, arrays, dates, colorscale, dmax, dmin, reverse]


class Location_Builder:
    '''
    This takes a location selection determined to be the triggering choice,
    decides what type of location it is, and builds the appropriate location
    list object needed further down the line. To do so, it holds county, 
    state, grid, and other administrative information.
    '''
    def __init__(self, location, coordinate_dictionary):
        self.location = location
        self.counties_df = pd.read_csv('data/tables/counties3.csv')
        self.states_df = self.counties_df[['STATE_NAME', 'STUSAB',
                                    'FIPS State']].drop_duplicates().dropna()
        self.cd = coordinate_dictionary

    def chooseRecent(self):
        '''
        Check the location for various features to determine what type of
        selection it came from. Return a list with some useful elements.
        '''
        location= self.location
        counties_df = self.counties_df
        states_df = self.states_df
        cd = self.cd

        # 1: Selection is a grid ID
        if type(location) is int and len(str(location)) >= 3:
            county = counties_df['place'][counties_df.grid == location].item()
            y, x = np.where(cd.grid == location)
            location = [int(y), int(x), county]
    
        # 2: location is a list of states
        elif type(location) is list:
            # Empty, default to CONUS
            if len(location) == 0:
                location = ['state_mask', 'all', 'Contiguous United States']
    
            elif len(location) == 1 and location[0] == 'all':
                location = ['state_mask', 'all', 'Contiguous United States']
    
            # Single or multiple, not all or empty, state or list of states
            elif len(location) >= 1:
                # Return the mask, a flag, and the state names
                state = list(states_df['STUSAB'][
                             states_df['FIPS State'].isin(location)])
                if len(state) < 4:
                    state = [states_df['STATE_NAME'][
                             states_df['STUSAB'] == s].item() for s in state]
                states = ", ".join(state)
                location = ['state_mask', str(location), states]
    
        # Selection is the default 'all' states
        elif type(location) is str:
            location = ['state_mask', 'all', 'Contiguous United States']
    
        # 4: Location is a point object
        elif type(location) is dict:
            if len(location['points']) == 1:
                lon = location['points'][0]['lon']
                lat = location['points'][0]['lat']
                x = cd.londict[lon]
                y = cd.latdict[lat]
                gridid = cd.grid[y, x]
                counties = counties_df['place'][counties_df.grid == gridid]
                county = counties.unique()
                if len(county) == 0:
                    label = ""
                else:
                    label = county[0]
                location = [y, x, label]
    
            elif len(location['points']) > 1:
                selections = location['points']
                y = list([cd.latdict[d['lat']] for d in selections])
                x = list([cd.londict[d['lon']] for d in selections])
                counties = np.array([d['text'][:d['text'].index(':')] for
                                     d in selections])
                county_df = counties_df[counties_df['place'].isin(
                                        list(np.unique(counties)))]
    
                # Use gradient to print NW and SE most counties as a range
                NW = county_df['place'][
                    county_df['gradient'] == min(county_df['gradient'])].item()
                SE = county_df['place'][
                    county_df['gradient'] == max(county_df['gradient'])].item()
                if NW != SE:
                    label = NW + " to " + SE
                else:
                    label = NW
                location = [str(y), str(x), label]
    
        return location