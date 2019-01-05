# -*- coding: utf-8 -*-
"""
Created on Sun May 28 21:14:48 2017

@author: Travis
"""
################################# Switching to/from Ubuntu VPS ################
from sys import platform
import os

if platform == 'win32':
    homepath = "C:/users/user/github/"
    os.chdir(homepath + "PRF-ALTIND")
    from flask_cache import Cache  # This one works on Windows but not Linux
    import gdal
    import rasterio
    import boto3
    import urllib
    import botocore
    def PrintException():
        exc_type, exc_obj, tb = sys.exc_info()
        f = tb.tb_frame
        lineno = tb.tb_lineno
        filename = f.f_code.co_filename
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename,
              lineno, line.strip(), exc_obj))

    gdal.UseExceptions()
    print("GDAL version:" + str(int(gdal.VersionInfo('VERSION_NUM'))))
else:
    homepath = "/home/ubuntu/"
    os.chdir(homepath+"PRF-ALTIND")
    from flask_caching import Cache  # This works on Linux but not Windows :)

###############################################################################
import copy
import dash
from dash.dependencies import Input, Output, State, Event
import dash_core_components as dcc
import dash_html_components as html
import dash_table_experiments as dt
import gc
import glob
import json
from flask import Flask
import matplotlib
import matplotlib.pyplot as plt 
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import numpy.ma as ma
from collections import OrderedDict
import os
import pandas as pd
import plotly
import re 
from textwrap import dedent
import time
from tqdm import *
import xarray as xr

# In[] Function to readjust index intervals
def adjustIntervals(indexlist):
    '''
        Takes in a list of monthly arrays (['index_yyyymm',array])
        Outputs a list of overlapping bimonthly arrays simply averages each
        overlapping two month pair within each year. You have to do this by
        year because Dec - Jan is not an interval, it starts over. This uses
        bilinear resampling.
    '''
    # This is for the plot titles later
    indexnames = [array[0] for array in indexlist]

    # Find year range from available indices
    years = [indexnames[i][-6:-2] for i in range(len(indexnames))]
    year1 = min(years)
    year2 = max(years)

    # Create a function for individual years
    def adjustYear(year):
        indexyear = [index for index in indexlist if index[0][-6:-2] == year]
        newintervals = [[indexyear[i][0], (indexyear[i][1] +
                         indexyear[i+1][1])/2] for i in range(len(indexyear)-1)]
        return(newintervals)

    # Use the above function to loop through each year and adjust intervals
    newyears = [adjustYear(str(year)) for year in range(int(year1),
                                                        int(year2)+1)]

    # Flatten the above list of lists. 
    newindex = [interval for year in newyears for interval in year]
    
    # This becomes the index that we calculate payouts on
    return(newindex)

###########################################################################
##############  To readjust index intervals for USDM ######################
###########################################################################    
# Use this to collect overlapping bimonthlies into a list
def adjustIntervals2(indexlist):
    '''
        Slightly different than the other adjustIntervals. This one is made for
            The USDM, take in weeklies, outputs bimonthlies, and calculates
            modes not means.
    '''

    years = np.unique([u[0][-8:-4] for u in indexlist])
    year1 = min(years)
    year2 = max(years)
    
    # Create a function for individual years
    def adjustYear(year, indexlist):
        # order by year
        newlist = [index for index in indexlist if index[0][-8:-4] == year]
        
        # group by month
        newlist = [[index for index in newlist if index[0][-4:-2] == str(m).zfill(2)] for m in range(1,13)]
        
        # group by overlapping months
        newlist = [[newlist[i],newlist[i+1]] for i in range(len(newlist)-1)]
        
        # Collapse each set of two months into set of arrays
        newlist = [[item for lst in interval for item in lst] for interval in newlist]
        
        return newlist

    # Use the above function to loop through each year and adjust intervals
    newyears = [adjustYear(str(year), indexlist) for year in range(int(year1),int(year2)+1)]
    
    # Flatten the above list of lists. (It's a list with yearly lists of 11 intervals now)
    newindex = [interval for year in newyears for interval in year]
    
    # This becomes the index that we calculate payouts on
    return(newindex)


###########################################################################
##################### Quick Mode Function #################################
###########################################################################   
# Now, how do we choose monthly values. Mode, Median, Mean? Mean would be strange. Mode
    # Is turning out to be incredibly slow...
def arrayMode(array):
    def mode(lst):
        lst = list(lst)
        uniques = np.unique(lst)
        frequencies = [lst.count(i) for i in uniques]
        mx = max(frequencies)
        indx = frequencies.index(mx)
        return uniques[indx]
    return np.apply_along_axis(mode, axis = 0, arr = array)
        
###########################################################################
##################### Basis Risk Check ####################################
###########################################################################
def basisCheck(usdm,noaa,strike,dm):
    '''
    For a single month, this returns an array of 1's where both the DM hit its 
        strike and rainfall didn't. Places where any other scenario occured are
        zeros, we're going to add them up.
    '''
    # Get just the arrays
    if len(usdm) == 2:
        date = usdm[0][-6:]
        usdm = usdm[1]
    if len(noaa) == 2:
        noaa = noaa[1]

    # Get cells at or above dm level drought
    drought = np.copy(usdm)
    drought[drought >= dm] = 9999
    drought[drought < 6] = 1
    
    # get cell at or below strike level rain
    rainless = np.copy(noaa)
    rainless[rainless <= strike] = 9999
    rainless[rainless < 9999] = 2 # No payouts. I had to set the triggered payouts to a high number to escape the index value range.
    rainless[rainless == 9999] = 1 # Payouts
    
    # Now, where are the 1's in drought that aren't in rainless?
    basis = rainless*drought
    basis[basis < 19998] = 0 # 19998 is where no payouts and drought intersect (9999*2)
    basis[basis == 19998] = 1
    
    return basis

###########################################################################
############## Finding Average Cellwise Coefficients of Variance ##########
########################################################################### 
def covCellwise(arraylist):
    '''
     Coefficient of Variance between cell-wise index values
    '''
    
    # Standardize to avoid negative values?
    arrays = [arraylist[i][1] for i in range(len(arraylist))]
    arraylist = standardize(arraylist)
    
    # First get standard deviation for each cell
    sds = np.nanstd([a[1] for a in arraylist],axis = 0)
    
    # Now get mean values for each cell
    avs = np.nanmean([a[1] for a in arraylist],axis = 0)
    
    # Third, simply divide
    covs = sds/avs
    
    # Average SD
    average = np.nanmean(covs)
    return(average)



###########################################################################
##################### USDM Drought Check ##################################
###########################################################################
def droughtCheck(usdm,dm):
    '''
    Check how many cells in a single month were at or above the dm level
    '''
    # Get just the array
    if len(usdm) == 2:
        date = usdm[0][-6:]
        usdm = usdm[1]

    # Get cells at or above dm level drought
    drought = np.copy(usdm)
    drought[drought >= dm] = 6
    drought[drought < 6] = 0
    drought[drought == 6] = 1

    return drought

def droughtCheck2(rain,strike):
    '''
    Check how many cells in a single month were at or above the dm level
    '''
    # Get just the array
    if len(rain) == 2:
        date = rain[0][-6:]
        rain = rain[1]

    # Get cells at or above dm level drought
    drought = np.copy(rain)
    drought[drought <= strike] = -9999
    drought[drought > -9999] = 0
    drought[drought == -9999] = 1

    return drought
###########################################################################
##################### Quick Histograms ####################################
###########################################################################    
def indexHist(array,guarantee = 1,mostfreq = 'n',binumber = 1000, limmax = 0, sl = 0):
    '''
    array = single array or list of arrays
    '''
    
    # Check if it is a list with names, a list without names, a single array with a name, 
        # or a single array without a name.
    if str(type(array)) == "<class 'list'>":
        if type(array[0][0]) == str and len(array[0])==2:
            name = array[0][0][:-7] + ' Value Distribution'
            array = [ray[1] for ray in array]
            na = array[0][0,0]    
            for ray in array:
                ray[ray == na] = np.nan
        elif type(array[0]) == str:
            name = array[0] + ' Value Distribution'
            array = array[1]
            na = array[0,0]    
            array[array == na] = np.nan
        else:
            na = array[0][0,0]
            name = "Value Distribution"
            for ray in array:
                ray[ray == na] = np.nan
    else:
        na = array[0,0]
        name = "Value Distribution"
        array[array == na] = np.nan
    
    # Mask the array for the histogram (Makes this easier)
    arrays = np.ma.masked_invalid(array)
    
    # Get min and maximum values
    amin = np.min(arrays)
    printmax = np.max(arrays)
    if limmax > 0:
        amax = limmax
    else:
        amax = np.max(arrays)
        
    # Get the bin width, and the frequency of values within, set some
    # graphical parameters and then plot!
    fig = plt.figure(figsize=(8, 8))
    hists,bins = np.histogram(arrays,range = [amin,amax],bins = binumber,normed = False)
    if mostfreq != 'n':
        mostfreq =  float(bins[np.where(hists == np.max(hists))])
        targetbin = mostfreq
        targethist = np.max(hists)
        firstprint = 'Most Frequent Value: '+ str(round(mostfreq,2))    
    # Get bin of optional second line
    if sl != 0:     
        differences = [abs(bins[i] - sl) for i in range(len(bins))]
        slindex = np.where(differences == np.nanmin(differences))
        secondline = bins[slindex]
        slheight = hists[slindex]
        secondtitle = '\nRMA Strike level: ' + str(guarantee) + ', Alt Strike Level: ' + str(round(sl,4))
    else:
        secondtitle = ''
    if mostfreq != 'n':
        if mostfreq == 0:
            secondcheck = np.copy(hists)
            seconds = secondcheck.flatten()
            seconds.sort() 
            second = float(bins[np.where(hists == seconds[-2])])
            targetbin = second
            targethist= seconds[-2]
            secondprint = '\n       Second most Frequent: '+str(round(second,2))
        else:
            secondprint = '' 
    width = .65 * (bins[1] - bins[0])
    center = (bins[:-1] + bins[1:]) / 2
    plt.bar(center, hists, align='center', width=width)
    title=(name+":\nMinimum: "+str(round(amin,2))+"\nMaximum: "+str(round(printmax,2))+secondtitle)
    plt.title(title,loc = 'center')    
    if mostfreq != 'n':
        plt.axvline(targetbin, color='black', linestyle='solid', linewidth=4)
        plt.axvline(targetbin, color='r', linestyle='solid', linewidth=1.5)
    drange = np.nanmax(arrays) - np.nanmin(arrays)

    if sl != 0:
        plt.axvline(secondline, color='black', linestyle='solid', linewidth=4)
        plt.axvline(secondline, color='y', linestyle='solid', linewidth=1.5)
#        plt.annotate('Optional Threshold: \n' + str(round(sl,2)), xy=(sl-.001*drange, slheight), xytext=(min(bins)+.1*drange, slheight-.01*max(hists)),arrowprops=dict(facecolor='black', shrink=0.05))
#    cfm = plt.get_current_fig_manager()
#    cfm.window.move(850,90)

###############################################################################
########################## AWS Retrieval ######################################
###############################################################################
# For singular Numpy File - Might have to write this for a compressed numpy 
def getNPY(path):
    key=[i.key for i in bucket.objects.filter(Prefix = path)][0] # Probably an easier way
    obj = resource.Object("pasture-rangeland-forage", key)
    try:
        with io.BytesIO(obj.get()["Body"].read()) as f:
            # rewind the file
            f.seek(0)
            array = np.load(f)
            array = array.f.arr_0    
    except botocore.exceptions.ClientError as e:
        error = e
        if error.response['Error']['Code'] == "404":
            array = "The object does not exist."
        else:
            raise
    return array

# For 3D Numpy files
def getNPYs(numpypath,csvpath):
    # Get arrays
    key=[i.key for i in bucket.objects.filter(Prefix = numpypath)][0] # Probably an easier way
    obj = resource.Object("pasture-rangeland-forage", key)
    try:
        with io.BytesIO(obj.get()["Body"].read()) as file:
            # rewind the file
            file.seek(0)
            array = np.load(file)
            arrays = array.f.arr_0    
    except botocore.exceptions.ClientError as error:
        print(error)

    # get dates
    key=[i.key for i in bucket.objects.filter(Prefix = csvpath)][0] # Probably an easier way
    obj = resource.Object("pasture-rangeland-forage", key)
    try:
        with io.BytesIO(obj.get()["Body"].read()) as df:        
            datedf = pd.read_csv(df)
    except botocore.exceptions.ClientError as error:
        print(error)
        
    arrays = [[datedf['dates'][i],arrays[i]] for i in range(len(arrays))]
    return arrays


###########################################################################
############## Mondo, Super Important Main Function ########################
###########################################################################    
def indexInsurance(indexlist, grid, premiums, bases, actuarialyear, studyears,
                   baselineyears, productivity, strike, acres, allocation,
                   difference=0, scale=True, plot=False,
                   interval_restriction=False):
    '''
    **** UNDER CONSTRUCTION AND OPEN TO SUGGESTION ****

        Takes in a list of raster paths and variables, namely a drought index of some sort and 
            uses them to calculate hypothetical Pasture, Rangeland, and Forage Insurance payouts for 
            each Risk Management Agency (RMA) grid cell for each interval between a range of years.

        ARGUMENTS:               DESCRIPTION                                                    OBJECT TYPE
            
        indexlist                - A list of arrays representing a timeseries of drought        (arrays)
                					   index raster datasets.
                                       [NAME_YYYYMM", 2D Numpy Array]
	    grid                     - RMA Insurance grid array                                     (array)
	    premiums                 - List of Premiums arrays				                         (arrays)
	    bases 		             - List of County base value arrays                             (arrays)
        studyears                - Start and end year for the payout calculation                (integers)
        baselineyears            - Years between which the monthly average values will be       (integers)
                                        indexed 
        productivity             - Number signifying productivity ratio                         (float)
        strike                   - Number signifying gaurantee level that triggers payouts      (float)
        acres                    - Number of acres per cell                                     (integer)
        allocation               - Monthly Allocation                                           (float)
	    difference               - For the old plotting system (which output to plot)           (integer)
	    scale                    - Whether or not to scale payments                             (integer)
                						1 = yes, 0 = no
	    plot 		             - Whether or not to plot with the old system (matplotlib)      (True/False)
	    
            
        
        RETURNS:
            
        insurance_package_all
        producerpremiums     - List of producer premium values in every interval/year       (list of arrays)
        indemnities          - List of indemnity values in every interval/year              (list of arrays)
		frequencies	         - List of single payout events				                     (list of arrays)
		pcfs                 - List of payment calculation factors 			                 (list of arrays)
		nets                 - List of net payouts			                                 (list of arrays)
		lossratios           - List of unsubsidized lossratios				                 (list of arrays)
        meanppremium         - Average 'monthly' producer premiums for each grid cell       (array)
        meanindemnity        - Average 'monthly' indemnity for each grid cell               (array)
		frequencysum         - Sum of 'monthly' payout events for each grid cell            (array)
		meanpcf              - Average 'monthly' payment calculation factors for each cell  (array)
		net		             - Average 'monthly' net payments after producer premiums       (array)
 		lossratio            - Average 'monthly' unsusidized loss ratio                     (array)

        THINGS TO DO/Consider:

            1) Add in a try/except structure for errors

            2) Some stipulations on calculating new indices
                a) The RMA is calculated from 1948 up to two years before the crop year, though the
                    baseline years may be changed to check for effects
                c) There are multiple methods of calculation to compensate for drought index value
                    distributions, particularly very large negative values. Be careful to choose a 
		            consistent method to each. For now outliers below 3 standard deviations are 
		            asigned that value. 
                d) So far this is only functional for grazing operations, actuarial rates for 
                    haying are available but need to be rasterized before they can be used here.
                e) payment calculation factor and frequency data do not incorporate the availability
        		    restrictions in the southeast. The payout data does though, so that is why there
		            is such a large discrepancy.  

            3) Insurable interest is apparently included in the original cacluation, what is this 
                    and how do I incorporate it?

	    4) Go back and add the EDDI's back in. There is interest in this and I might be able to ameliorate
		    some of the issues with payment scaling.
                    
    **** UNDER CONSTRUCTION ****

    '''

    ###########################################################################
    ############## Establish some necessary pieces to the calculation #########
    ###########################################################################
    # This dictionary of column names is needed to match information from the
    # actuarial rates to the appropriate place and time. I do this to maintain
    # readability of the original data table. Not currently necessary, but this
    # will be useful if we want to adjust this
    
    colnames1 = {'Grid ID': 'gridid', 'Guarantee Level': 'strike',
                 'Grazing Interval\n Jan-Feb': 'g1',
                 'Grazing Interval\n Feb-Mar': 'g2',
                 'Grazing Interval\n Mar-Apr': 'g3',
                 'Grazing Interval\n Apr-May': 'g4',
                 'Grazing Interval\n May-Jun': 'g5',
                 'Grazing Interval\n Jun-Jul': 'g6',
                 'Grazing Interval\n Jul-Aug': 'g7',
                 'Grazing Interval\n Aug-Sep': 'g8',
                 'Grazing Interval\n Sep-Oct': 'g9',
                 'Grazing Interval\n Oct-Nov': 'g10',
                 'Grazing Interval\n Nov-Dec': 'g11',
                 'Haying Interval (non-irrigated)\n Jan-Feb': 'h1',
                 'Haying Interval (non-irrigated)\n Feb-Mar': 'h2',
                 'Haying Interval (non-irrigated)\n Mar-Apr': 'h3',
                 'Haying Interval (non-irrigated)\n Apr-May': 'h4',
                 'Haying Interval (non-irrigated)\n May-Jun': 'h5',
                 'Haying Interval (non-irrigated)\n Jun-Jul': 'h6',
                 'Haying Interval (non-irrigated)\n Jul-Aug': 'h7',
                 'Haying Interval (non-irrigated)\n Aug-Sep': 'h8',
                 'Haying Interval (non-irrigated)\n Sep-Oct': 'h9',
                 'Haying Interval (non-irrigated)\n Oct-Nov': 'h10',
                 'Haying Interval (non-irrigated)\n Nov-Dec': 'h11',
                 'Haying Interval (irrigated)\n Jan-Feb': 'h1',
                 'Haying Interval (irrigated)\n Feb-Mar': 'h2',
                 'Haying Interval (irrigated)\n Mar-Apr': 'h3',
                 'Haying Interval (irrigated)\n Apr-May': 'h4',
                 'Haying Interval (irrigated)\n May-Jun': 'h5',
                 'Haying Interval (irrigated)\n Jun-Jul': 'h6',
                 'Haying Interval (irrigated)\n Jul-Aug': 'h7',
                 'Haying Interval (irrigated)\n Aug-Sep': 'h8',
                 'Haying Interval (irrigated)\n Sep-Oct': 'h9',
                 'Haying Interval (irrigated)\n Oct-Nov': 'h10',
                 'Haying Interval (irrigated)\n Nov-Dec': 'h11'}
    colnames2 = {y: x for x, y in colnames1.items()}

    # Developing arguments
    # indexlist = homepath + 'data/indices/noaa_arrays.npz'
    # bases = npzIn(homepath + 'data/actuarial/base_arrays_' +
    #           str(actuarialyear) + '.npz',
    #           homepath + 'data/actuarial/base_dates_' +
    #           str(actuarialyear) + '.npz')
    # premiums = npzIn(homepath + 'data/actuarial/premium_arrays_' +
    #                   str(actuarialyear) + '.npz',
    #                   homepath + 'data/actuarial/premium_dates_' +
    #                   str(actuarialyear) + '.npz')
    # grid = readRaster(homepath + "data/rma/prfgrid.tif", 1, -9999)[0]
    # allocation = .5
    # produtivity = 1
    # actuarialyear = 2018
    # studyears = [2000, 2018]
    # baselineyears = [1948, 2016]
    # strike = .8
    # acres = 500
    # difference=0
    # scale=True
    # plot=False

    # Get the indexlist if it is given as a path to the arrays.
    if str(type(indexlist)) != "<class 'list'>":
        try:
            indexlist = readRasters2(indexlist, -9999)[0]
            print("tifs")
        except:
            print("npzs")
            arraypath = indexlist
            datepath = indexlist.replace("arrays", "dates")
            indexlist = npzIn(arraypath,
                              datepath)
        # Fix to work with rasters or npzs

    ###########################################################################
    ################# Define Internal Functions ###############################
    ###########################################################################
    def freqCalc(array, strike):
        strike2 = key.get(strike)
        array[array <= strike2] = -9999
        array[array > strike2] = 0
        array[array == -9999] = 1
        return(array)

    def pcfCalc(array, strike):
        strike2 = key.get(strike)  # Strike2 to preserve original strike value
        array[array > strike2] = 0
        pcf = abs((strike2-array)/strike2)
        pcf[pcf == 1] = 0
        return(pcf)

    ###########################################################################
    ############## Getting all the numbers ####################################
    ###########################################################################
    # Extract the years
    startyear = int(studyears[0])
    endyear = int(studyears[1])
    baselineyear = int(baselineyears[0])
    baselinendyear = int(baselineyears[1])

    ###########################################################################
    ############## Adjust the Climate Index list if Needed ####################
    ###########################################################################     
    # Load in the test index -  Geometry and projection are for writing rasters
    indexname = indexlist[0][0][:-7]

    # Make some index specific adjustments
    if "NOAA" in indexname:
        # Need this for a subsequent step
        key = {.9: .9, .85: .85, .8: .8, .75: .75, .7: .7}

        # No Alterations
        indexlist = indexlist
        payscalar = 1
        premiums_filtered = [p for p in premiums if
                             p[0][-5:-3] == "%02d" % int(strike * 100)]
    else:
        # This was confusing at first
        if "EDDI" in indexname:
            indexlist = [[a[0], a[1]*-1] for a in indexlist]

        # Adjust for outliers
        arrays = [a[1] for a in indexlist]
        sd = np.nanstd(arrays)
        thresholds = [-3*sd, 3*sd]
        for a in arrays:
            a[a <= thresholds[0]] = thresholds[0]
            a[a >= thresholds[1]] = thresholds[1]
        indexlist = [[indexlist[i][0],
                      arrays[i]] for i in range(len(indexlist))]

        # Adjust intervals
        indexlist = adjustIntervals(indexlist)

        # Standardize Range
        indexlist = standardize(indexlist)

        # Find Matching Probability for strike level
        keydf = pd.read_csv("C:/users/user/github/data/Index_Adjustments/" +
                            "newstrikes.csv")

        if indexname not in list(keydf['index']):
            # Get the noaa values for strike matching if needed
            noaalist = npzIn("C:/users/user/github/data/indices/" +
                             "noaa_arrays.npz",
                             "C:/users/user/github/data/indices/" +
                             "noaa_dates.npz")

            # Establish Strikes
            strikes = [.7, .75, .8, .85, .9]
            newstrikes = []
            for i in tqdm(range(len(strikes))):
                newstrikes.append(probMatch(indexlist, noaalist,
                                            strikes[i], plot=False))

            # Create the key
            key = dict(zip(strikes, newstrikes))

            # Turn into dataframe
            indexrows = np.repeat(indexname, 5)
            keydf2 = pd.DataFrame([indexrows, strikes, newstrikes]).transpose()
            keydf2.columns = ['index', 'strike', 'newstrike']

            # Append to the main key dataframe
            keydf = keydf.append(keydf2, ignore_index=True)

            # Save for next time
            keydf.to_csv(homepath + "data/Index_Adjustments/newstrikes.csv",
                         index=False)
        else:
            newstrikes = keydf.ix[keydf["index"] == indexname]
            key = dict(zip(keydf['strike'], keydf['newstrike']))

        if scale:
            # Set up the payment scaling ratios.
            scalardf = pd.read_csv("C:/users/user/github/" +
                                   "data/Index_Adjustments/" +
                                   "index_ratios_bystrike.csv")

            # if indexname.lower() not in scalardf['index']:  # Automate this

            scalardf['indexid'] = (scalardf['index'] + "_" +
                                   scalardf['strike'].astype(str))
            scalars = dict(zip(scalardf['indexid'], scalardf['ratio']))

            # Get the appropriate ratio for the current index's group
            name = ''.join([c.replace('-', '').lower() for c in indexname])
            name = name + "_" + str(strike)
            payscalar = scalars.get(name)
        else:
            payscalar = 1

        # Now, we need to overwrite the premium rates, if the index is NOAA
        # this step is skipped and the actual premiums rates are used.
        # Need pcfs from the full record
        copylist = [[array[0], np.copy(array[1])] for array in indexlist]
        pcfrays = [pcfCalc(array[1], strike) for array in copylist]
        meanpcf = np.nanmean(pcfrays, axis=0)
        pcfs = [[indexlist[i][0], pcfrays[i]] for i in range(len(pcfrays))]

        # We have the strike, now we need the premiums for each interval
        intervals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        premiums_filtered = [premiumLoading(indexlist,
                                            pcfs,
                                            strike,
                                            i) for i in intervals]

    # Now reduce the list to the calculation period.
    indexlist = [year for year in indexlist if
                 int(year[0][-6:-2]) >= startyear and
                 int(year[0][-6:-2]) <= endyear]

    ###########################################################################
    ############## Call the function to get array lists  ######################
    ###########################################################################
    mask = grid*0 + 1

    # totalsubsidyarrays = [insuranceCalc(array, productivity, strike, acres,
    #                                     allocation, bases, premiums,
    #                                     mask)[0] for array in indexlist]

    totalpremiums = [[array[0], insuranceCalc(array, productivity, strike,
                      acres, allocation, bases, premiums_filtered, mask, key,
                      payscalar,
                      interval_restriction)[3]] for array in indexlist]

    producerpremiums = [[array[0], insuranceCalc(array, productivity, strike,
                         acres, allocation, bases, premiums_filtered, mask,
                         key, payscalar,
                         interval_restriction)[1]] for array in indexlist]

    indemnities = [[array[0], insuranceCalc(array, productivity, strike, acres,
                    allocation, bases, premiums_filtered, mask, key,
                    payscalar,
                    interval_restriction)[2]] for array in indexlist]

    totalpremiumarrays = [element[1] for element in totalpremiums]
    premiumarrays = [element[1] for element in producerpremiums]
    indemnityarrays = [element[1] for element in indemnities]

    ###########################################################################
    ############## Call the function to get frequencies #######################
    ###########################################################################
    # These are for frequencies within the study perios=d
    copylist = [[array[0], np.copy(array[1])] for array in indexlist]
    frequencyrays = [freqCalc(array[1], strike) for array in copylist]
    frequencysum = np.sum(frequencyrays, axis=0)
    frequencies = [[indexlist[i][0], frequencyrays[i]] for
                   i in range(len(frequencyrays))]

    ###########################################################################
    ############## Same for Payout Claculation Factors ########################
    ###########################################################################
    # These are for pcfs within the study period
    copylist = [[array[0], np.copy(array[1])] for array in indexlist]
    pcfrays = [pcfCalc(array[1], strike) for array in copylist]
    meanpcf = np.nanmean(pcfrays, axis=0)
    pcfs = [[indexlist[i][0], pcfrays[i]] for i in range(len(pcfrays))]

    ###########################################################################
    ############## Average the out comes to show mean values at each cell #####
    ###########################################################################
    meanppremium = np.nanmean(premiumarrays, axis=0)
    meanindemnity = np.nanmean(indemnityarrays, axis=0)
    meantpremium = np.nanmean(totalpremiumarrays, axis=0)

    # Use those to get net payments and loss ratios
    net = meanindemnity - meanppremium
    nets = [[indemnities[i][0], indemnityarrays[i]-premiumarrays[i]] for
            i in range(len(indemnityarrays))]
    lossratio = np.round(meanindemnity/meantpremium, 2)
    lossratios = [[indemnities[i][0],
                   indemnityarrays[i]/totalpremiumarrays[i]] for
                   i in range(len(indemnityarrays))]

    ###########################################################################
    ################### We have to print and plot before returning ############
    ###########################################################################
    print('######################### Amount Results #######################')
    print(indexname+" Payout Statistics \nMax Payout: ", round(np.nanmax(meanindemnity),2),
          "\nMinimum Payout: ", round(np.nanmin(meanindemnity),2),
          "\nMedian Payout: ", round(np.nanmedian(meanindemnity),2),
          "\nMean Payout: ", round(np.nanmean(meanindemnity),2),
          "\nPayout Standard Deviation: ",round(np.nanstd(meanindemnity),2))
    print('######################### Results ##############################')
        ################### Average Indemnity/ Net Pay Map  #######################
    if plot:
        if difference == 0:
            mainmap = meanindemnity
            series1 = indemnities
            ylimit = 5000
            title = "Potential Payouts"
            title2 = "Average: " + str(round(np.nanmean(meanindemnity), 2))
            label = 'USD ($)'
        elif difference == 1:
            mainmap = net
            series1 = nets
            ylimit = 5000
            title = "Potential Net Pay"
            title2 = "Bi-Monthly Average: $" + str(round(np.nanmean(net), 2))
            label = 'USD ($)'
        elif difference == 2:
            mainmap = lossratio
            series1 = lossratios
            ylimit = 5
            title = "Loss Ratios"
            title2 = "US average: " + str(round(np.nanmean(lossratio), 2))
            label = 'Ratio'
            
        ################### Plot everything  ##################################
        # Main Title
        fig = plt.figure()
        if startyear == endyear:
            endyear = ""
        else:
            endyear = ' - '+str(endyear)
        fig.suptitle('PRF with ' + indexname+";  " + str(startyear) + endyear +
                     ';   Baseline year: ' + str(baselineyear) +
                     ';   Strike Level: %' + str(int(strike*100)) +
                     ';   Rate Year: ' + str(actuarialyear), fontsize=15,
                     fontweight='bold')

        # Establish subplot structure
        ax1 = plt.subplot2grid((3, 4), (0, 0), colspan=2)
        ax2 = plt.subplot2grid((3, 4), (0, 2), colspan=2)
        ax3 = plt.subplot2grid((3, 4), (1, 0), colspan=3, rowspan=2)
        ax4 = plt.subplot2grid((3, 4), (1, 3), colspan=2, rowspan=2)

        # Set initial plot 4 parameters - this is an interactive barplot
        ax4.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax4.set_title('Monthly Trends')

        # Plot 1 - Payout Frequency Distribution
        im = ax1.imshow(frequencysum)
        ax1.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off',
                        labelbottom='off')
        ax1.set_title('Payment Frequency\n US average: ' +
                      str(round(np.nanmean(frequencysum), 2)))
        divider1 = make_axes_locatable(ax1)
        cax1 = divider1.append_axes("left", size="5%", pad=0.05)
        cbar = plt.colorbar(im, cax=cax1)
        cbar.set_label('Potential Payouts', rotation=90, size=10, labelpad=10,
                       fontweight='bold')
        cbar.ax.yaxis.set_label_position('left')
        cbar.ax.yaxis.set_ticks_position('left')

        # Plot 2 - Payment Calculation Factor Distribution
        im2 = ax2.imshow(meanpcf)
        ax2.tick_params(which='both', right='off', left='off',
                        bottom='off', top='off', labelleft='off',
                        labelbottom='off')
        ax2.set_title('Payment Calculation Factors\nUS average: ' +
                      str(round(np.nanmean(meanpcf), 2)))   
        divider2 = make_axes_locatable(ax2)
        cax2 = divider2.append_axes("right", size="5%", pad=0.05)
        cbar2 = plt.colorbar(im2, cax=cax2)
        cbar2.set_label('PCF', rotation=270, size=8,
                        labelpad=10, fontweight='bold')

        # Plot 3- Changes
        im3 = ax3.imshow(mainmap)
        ax3.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off') 
        ax3.set_title(title + '\n' + title2)
        divider3 = make_axes_locatable(ax3)
        cax3 = divider3.append_axes("left", size="5%", pad=0.05)
        cbar3 = plt.colorbar(im3, cax=cax3)
        cbar3.set_label(label, rotation=90, size=8,
                        labelpad=10, fontweight='bold')
        cbar3.ax.yaxis.set_label_position('left')
        cbar3.ax.yaxis.set_ticks_position('left')

        #######################################################################
        ############# Interactive Monthly Payout Trends #######################
        #######################################################################
        # Define click event
        coords = []
        
        def onclick(event):
            global ix, iy
            ix, iy = event.xdata, event.ydata
            # print('x = %d, y = %d'%(ix, iy)) # This is just for testing

            global coords
            coords.append((ix, iy))

            if event.inaxes == ax1:
                calctype = 'Sum '
                ax = ax1
                series = frequencies
                ylim = 12
                xlabel = 'Year'
                rot = -45
                fsize = 8
                bartitle = "Potential Payouts"
                pointtype = 'yo'
                col = 'yellow'
                print("event in ax1")
                yearly = 1
            elif event.inaxes == ax2:
                calctype = 'Average '
                ax = ax2
                bartitle = "Mean pcfs"
                rot = -45
                fsize = 8
                series = pcfs
                ylim = 1
                xlabel = 'Bi-Monthly Interval'
                pointtype = 'ro'
                col = 'red'
                print("event in ax2")
                yearly = 0
            elif event.inaxes == ax3:
                calctype = 'Average '
                ax = ax3
                bartitle = title
                rot = -45
                fsize = 8
                series = series1
                pointtype = 'wo'
                ylim = ylimit
                xlabel = 'Bi-Monthly Interval'
                col = 'white'
                print("event in ax3")
                yearly = 0
                # Colors:   'b', 'g', 'r', 'c', 'm', 'y', 'k', 'w'

            # Catch the target grid cell
            targetid = grid[round(float(iy)), round(float(ix))]
            index = np.where(grid == targetid)

            # Create the time series of data at that gridcell
            timeseries = [[item[0], item[1][index]] for item in series]

            # For title
            years = [int(item[0][-6:-2]) for item in timeseries]
            year1 = str(min(years))
            year2 = str(max(years))

            # For the x axis and value matching
            intervals = [format(int(interval), '02d') for
                         interval in range(1, 12)]
            months = {1: 'Jan-Feb',
                      2: 'Feb-Mar',
                      3: 'Mar-Apr',
                      4: 'Apr-May',
                      5: 'May-Jun',
                      6: 'Jun-Jul',
                      7: 'Jul-Aug',
                      8: 'Aug-Sep',
                      9: 'Sep-Oct',
                      10: 'Oct-Nov',
                      11: 'Nov-Dec'}

            # The actual values
            valuelist = [[series[1] for series in timeseries if
                          series[0][-2:] == interval] for
                          interval in intervals]

            # In tuple form for the bar chart
            averages = tuple(np.asarray([np.mean(sublist) for
                                         sublist in valuelist]))
            intlabels = tuple([months.get(i) for i in range(1, 12)])
            x = np.arange(len(intervals))

            # A yearly series of sums for the frequency box
            if yearly == 1:
                timeseries = [[item[0], item[1][index]] for item in series]

                # For title
                years = [int(item[0][-6:-2]) for item in timeseries]
                year1 = str(min(years))
                year2 = str(max(years))

                # For the x axis and value matching
                intervals = [str(interval) for interval in range(int(year1),
                                                                 int(year2)+1)]

                # The actual values
                valuelist = [[series[1] for series in timeseries if
                              series[0][-6:-2] == interval] for
                              interval in intervals]

                # In tuple form for the bar chart
                axinterval = round((int(year2)-int(year1))/10)
                averages = tuple(np.asarray([np.nansum(sublist) for
                                             sublist in valuelist]))
                intlabels = tuple([interval for interval in range(int(year1),
                                                                  int(year2)+1,
                                                                  axinterval)])
                x = np.arange(len(intervals))

            # For adding a spot to the map
            spot = np.where(grid == targetid)

            # Clears data but not axes
            ax4.cla()

            # Plot the bar chart
            ax4.tick_params(which='both', right='on', left='off', bottom='on',
                            top='off', labelleft='off', labelright='on',
                            labelbottom='on')
            ax4.yaxis.set_label_position("right")
            ax4.bar(x, averages, align='center', alpha=0.5, color=col,
                    linewidth=2, edgecolor='black')
            ax4.set_ylabel(calctype + bartitle, rotation=270,
                           labelpad=15, fontweight='bold')
            ax4.set_ylim([0, ylim])
            ax4.set_title(bartitle + ' -- Grid ID: '+str(int(targetid)))
            if yearly == 1:
                ax4.set_xticks([])
                ax4.set_xticks(np.arange(1, len(intervals)+1, axinterval),
                               minor=True)
                ax4.set_xticklabels([])
                ax4.set_xticklabels(intlabels, rotation=rot,
                                    ha="left", fontsize=fsize, minor=True)
                ax4.set_xlabel(xlabel)
            else:
                ax4.set_xticks(np.arange(len(intervals)))
                ax4.set_xticklabels(intlabels, rotation=rot,
                                    ha="left", fontsize=fsize)
                ax4.set_xlabel(xlabel)

            # Add spot to map
            point = ax.plot(int(spot[1]), int(spot[0]), pointtype,
                            markersize=6, markeredgewidth=1,
                            markeredgecolor='k')

            # Draw it all
            fig.canvas.draw()
            return coords
        global cid
        cid = fig.canvas.mpl_connect('button_press_event', onclick)

    ###########################################################################
    ############## Bundle up the results for a tidy return ####################
    ###########################################################################
   
    insurance_package_all = [producerpremiums, indemnities, frequencies, pcfs,
                             nets, lossratios, meanppremium, meanindemnity,
                             frequencysum, meanpcf, net, lossratio]

    print("Insurance Model Calculated. " + indexname + ": " + str(startyear) +
          " - " + str(endyear) + " at " + str(int(strike*100)) + "%")
    print("Return Order: producerpremiums, indemnities, frequencies, pcfs, " +
          "nets, lossratios, meanppremium, meanindemnity, frequencysum, " +
          "meanpcf, net, lossratio")
    return insurance_package_all


# In[] Calculating new premiums
def premiumLoading(indexlist, pcfs, strike=.7, interval=1):
    '''
    This is as work in progress because I don't know how they calculate the
    loading rates over the pure risk premium. For now this finds the average
    PCF values for each interval of a given index (back to 1948) and simply
    multiplies that by the corresponding average loading rate found from the
    rainfall index.
    '''
    # Use either a precalculated list or a path to generate the index arrays
    # Get all of the rainfall indices
    if str(type(indexlist)) != "<class 'list'>":
        arraypath = indexlist
        datepath = indexlist.replace("arrays", "dates")
        indexlist = npzIn(arraypath, datepath)

    # We need strings of the numeric strikes and intervals
    interval_string = "%02d" % interval
    strike_string = "%02d" % int(strike * 100)

    # Get the pcfs from the right interval, the strike is already incorporated
    pcf_specific = [p[1] for p in pcfs if p[0][-2:] == interval_string]
    pcf = np.nanmean(pcf_specific, axis=0)

    # Get the loading ratio and just use that for now. I can't find a pattern
    ratios = pd.read_csv('c:/users/user/github/prf-altind/loading_rates.csv')
    ratio = ratios.loading_factor[(ratios.strike == strike) &
                                  (ratios.intervals == interval)]

    # Get the new, simpler premium map
    premium = pcf*float(ratio)

    return ['PRATES_' + strike_string + '_' + interval_string, premium]


# In[] Indemnity Calculator
def insuranceCalc(index, productivity, strike, acres, allocation, bases,
                  premiums, mask, key, payscalar, interval_restriction=False):
    '''
    This calculates only the total premium and producer premium charged for
    each hypothetical plan, and returns those along with the indemnities for
    one interval of one year. Each object returned is a list of arrays.
    '''
    ############## Index  #################################################
    name = index[0]  # This chooses the first part of each index array
    index = index[1]*mask  # not always needed but doesnt change the outcome
    eligibleindex = np.copy(index)
    strike2 = key.get(strike)  # Strike2 to preserve the original strike value
    eligibleindex[eligibleindex > strike2] = 0
    eligibleindex[eligibleindex > 0] = 1

    ############## Actuarial rates ########################################
    if interval_restriction:
        baselabels = [b[0] for b in bases]
        targetbaselabel = "BRATES_" + name[-2:]
        targetbaseindex = baselabels.index(targetbaselabel)
        base = bases[targetbaseindex][1]  # This specifies base rates by interval according to the RI's eligibility
    else:
        base = bases[0][1]  # This applies full eligibility
    premiumlabels = [p[0] for p in premiums]
    targetpremiumlabel = "PRATES_" + str(int(100*strike)) + "_" + name[-2:]
    targetpremiumindex = premiumlabels.index(targetpremiumlabel)
    premiumrate = premiums[targetpremiumindex][1]

    ############# Protection ##############################################
    # Default Protection amount - scale here for payments and premiums
    protection = base * strike * productivity * acres * allocation * payscalar

    ############## Subsidies ##############################################
    # Subsidy rates given strike level
    subsidykey = {0.7: 0.59, 0.75: 0.59, 0.8: 0.55, 0.85: 0.55, 0.9: 0.51}
    
    # Subsidy rate
    subsidyrate = subsidykey.get(strike)
    
    ############# Premium #################################################
    # Simply the premium times the protection
    totalpremium = premiumrate * protection

    ############# Payments ################################################
    # Producer Premium
    producerpremium = totalpremium * (1 - subsidyrate)
    subsidy = totalpremium - producerpremium

    ############# Payouts #################################################
    # Payout Calculation Factor
    pcf = abs((strike2 - index)/strike2)

    # Indemnity
    indemnity = pcf * protection * eligibleindex

    ############# Return everything #####################
    return([subsidy, producerpremium, indemnity, totalpremium])


###############################################################################
########################## Mask Maker  ########################################
############################################################################### 
def makeMask(rasterpath, savepath):
    """
        This will take in a tif and output a mask of NaNs and 1's
    """

    mask = gdal.Open(rasterpath) # this is not an actual mask quite yet
    geometry = mask.GetGeoTransform()
    arrayref = mask.GetProjection()
    mask = np.array(mask.GetRasterBand(1).ReadAsArray())
    xpixels = mask.shape[1]
    ypixels = mask.shape[0]
    mask[mask == np.min(mask)] = np.nan
    mask = mask*0 + 1
    image = gdal.GetDriverByName("GTiff").Create(savepath,
                                xpixels, ypixels, 1,gdal.GDT_Float32)
    image.SetGeoTransform(geometry)
    image.SetProjection(arrayref)
    image.GetRasterBand(1).WriteArray(mask)


###########################################################################
############## Creating monthly averages at each cell #####################
###########################################################################  
def monthlies(indexlist):
    '''
        This takes in the series of indemnity arrays an RMA grid ID of choice
        and outputs average monthly payouts there.
    '''        
    indexname = indexlist[0][0][:-7] #Get index name
    intmax = np.max([int(item[0][-2:]) for item in indexlist])
    intervals = [format(int(interval),'02d') for
                 interval in range(1, intmax + 1)] # formatted interval strings
    intervallist = [[index[1] for index in indexlist if
                     index[0][-2:] == interval] for interval in intervals]
    averageslist = [np.nanmean(interval,axis = 0) for  interval in intervallist] # Just averages for each interval
    averageslist = [[indexname + "_" + format(int(i+1),'02d'), averageslist[i]] for i in range(len(averageslist))] # Tack on new names for each interval
    return(averageslist)



####################################################################################################
############################ Monthly Payout Trends #################################################
####################################################################################################
def monthlyPay(indemnities, indemnity, grid, targetid, strike,frequency = False):
    '''
        This takes in the series of indemnity arrays  an RMA grid ID of choice and outputs
            average monthly payouts there.
            
            
        indemnities = the list of all interval-wise payout arrays
        indemnity = the singular payout average array
    '''
    if frequency == True:
        title = "Payout Frequency"
    else:
        title = "Average Payouts"
        
    indexname = indemnities[0][0][:-7]
    if type(targetid) == str or type(targetid) == int:
        targetid = float(targetid)
    index = np.where(grid == targetid)
    timeseries = [[payout[0],payout[1][index]] for payout in indemnities]
    years = [int(payout[0][-6:-2]) for payout in timeseries]
    year1 = str(min(years)) 
    year2 = str(max(years))
    intervals = [format(int(interval),'02d') for interval in range(1,12)]
    valuelist = [[series[1] for series in timeseries if series[0][-2:] ==  interval] for interval in intervals]
    
    # For plotting:
    averages =  tuple(np.asarray([np.mean(sublist) for sublist in valuelist]))
    intlabels = tuple([interval for interval in range(1,12)])
    x = np.arange(len(intervals))    
    spot = np.where(grid == targetid)

    # Plotting:
    fig = plt.figure()
    st = fig.suptitle(indexname+'-based PRF\nMonthly '+title+ ' at Grid ID: '+ str(int(targetid))+'\n'+year1+ ' to '+ year2 + '\nStrike Level: %'+ str(int(strike*100)), fontsize="x-large", fontweight = 'bold')
    
    ax1 = plt.subplot2grid((2, 2), (0, 0), colspan = 2)
    ax2 = plt.subplot2grid((2, 2), (1,0), colspan = 2) 

    ax1.bar(x,averages, align='center', alpha=0.5)
    ax1.set_xticks(np.arange(len(intervals)))
    ax1.set_xticklabels(intlabels)
    ax1.set_ylabel('Average Payouts ($)')
    ax1.set_xlabel('Bi-Monthly Interval')

    im = ax2.imshow(indemnity) 
    ax2.axis('off')
    plt.plot(int(spot[1]),int(spot[0]),'rs', markersize=7)#
    ax2.tick_params(which='both',right = 'off',left = 'off', bottom='off', top='off',labelleft = 'off',labelbottom='off') 
    ax2.set_title('Grid '+ str(int(targetid)),loc = 'right', fontweight = 'bold')   

###########################################################################
############## Finding Monthly and Total Standard Deviation ###############
########################################################################### 
def monthlySD(arraylist):
    '''
     Standard Deviation between monthly cell-wise average values
    '''
    # Aiming for monthly variance figures, by cell
    # First get interval list
    intervals = [str(i).zfill(2) for i in range(1,12)]
    
    # Second group mean arrays by month 
    monthlies = [[i, np.nanmean([ray[1] for ray in arraylist if ray[0][-2:] == i],axis = 0)] for i in intervals]
    
    # Second group mean arrays by month 
    sds = np.nanstd([month[1] for month in monthlies],axis = 0)

    # Average SD
    average = np.nanmean(sds)
    return(average)
    
###########################################################################
############## Finding Monthly and Total Standard Deviation ###############
########################################################################### 
def monthlySD2(arraylist):
    '''
     Standard Deviation between monthly cell-wise counts (payout frequencies)
    '''
    # Aiming for monthly variance figures, by cell
    # First get interval list
    intervals = [str(i).zfill(2) for i in range(1,12)]
    
    # Second group mean arrays by month 
    monthlies = [[i, np.nansum([ray[1] for ray in arraylist if ray[0][-2:] == i],axis = 0)] for i in intervals]
    
    # Second group mean arrays by month 
    sds = np.nanstd([month[1] for month in monthlies],axis = 0)

    # Average SD
    average = np.nanmean(sds)
    return(average)

###########################################################################
############## Creating monthly averages at each cell #####################
###########################################################################  
def normalize(indexlist, baselinestartyear, baselinendyear):
    '''
        This will find the indexed value of the monthly average. 
    '''        
    indexname = indexlist[0][0][:-7]  # Get index name
    baseline = [year for year in indexlist if
                int(year[0][-6:-2]) >= baselinestartyear and 
                int(year[0][-6:-2]) <= baselinendyear]
    average = monthlies(baseline)
    normallist = []
    for i in range(len(indexlist)):
        for y in range(len(average)):
            if indexlist[i][0][-2:] == average[y][0][-2:]:
                index = indexlist[i][1] / average[y][1]
                normallist.append([indexlist[i][0],index]) 
    return(normallist)

# In[] Support functions
def npzIn(array_path, date_path):
    '''
    This takes a path to a compressed npz of arrays, and a path to a compressed
    array of associated dates, reads them in and create a list of lists:
        [[NAME_YYYYMM, numpy array], [NAME_YYYYMM, numpy array], ...]
    '''
    # Get all of the premium rates
    with np.load(array_path) as data:
        arrays = data.f.arr_0
        data.close()
    with np.load(date_path) as data:
        dates = data.f.arr_0
        data.close()
    arraylist = [[str(dates[i]), arrays[i]] for i in range(len(arrays))]

    return arraylist


def npzOut(indexlist, savepath):
    # Can't save dates with the arrays :/
    dates = [a[0] for a in indexlist]
    name = dates[0][:-7].lower()
    name = "".join([c for c in name if c.isalnum()])
    datepath = os.path.join(savepath, name + "_dates.npz")

    # Can't save arrays with the dates :/
    arrays = np.stack([a[1] for a in indexlist])
    arraypath = os.path.join(savepath, name + "_arrays.npz")

    # Save each
    np.savez_compressed(datepath, dates)
    np.savez_compressed(arraypath, arrays)


# In[] The Optimal Interval Experiment
def optimalIntervalExperiment(indexlist, targetinfo, targetarrayname,
                              studyears, informinginfo, informingarrayname,
                              informingyears, strike, savename, plot=True,
                              save=True, interval_restriction=False):
    '''
        This is an experiment to check the ability of different indices to be
            exploited for temporal trends from historic patterns.

        Target arrays = payments or net payments
        Informing arrays = payout triggers or pcfs
    '''
    # Actuarial rates
    grid = readRaster("c:/users/user/github/data/rma/prfgrid.tif",
                      1, -9999)[0]

    premiums = npzIn('c:/users/user/github/data/actuarial/' +
                     'premium_arrays_2018.npz',
                     'c:/users/user/github/data/actuarial/' +
                     'premium_dates_2018.npz')
    bases = npzIn('c:/users/user/github/data/actuarial/base_arrays_2018.npz',
                  'c:/users/user/github/data/actuarial/base_dates_2018.npz')

    # Insurance Call
    # First get the insurance payment results
    # Argument Definitions
    actuarialyear = 2018
    productivity = 1
    acres = 500
    allocation = .5
    grid, geom, proj = readRaster("C:/users/user/github/data/rma/prfgrid.tif",
                                  1, -9999)
    mask = grid * 0 + 1
    if informinginfo == 2:
        informfolder = "byfrequency"
    elif informinginfo == 3:
        informfolder = "bypcf"

    # run this for the PCF information period
    dfs = indexInsurance(indexlist,
                         grid,
                         premiums,
                         bases,
                         actuarialyear,
                         informingyears,
                         informingyears,  # This repeat is on purpose
                         productivity,
                         strike,
                         acres,
                         allocation,
                         scale=True,
                         plot=False,
                         interval_restriction=False)

    informingarrays = dfs[informinginfo]

    # Now let's create an eligibility list for the Rainfall index
    ppremiums = dfs[0]
    eligibility = [[p[0][-2:], p[1]*0+1] for p in ppremiums]

    ############### Find Optimal Intervals ####################################
    # Here we want to see the optimal interval choice for each cell
    # We need to find the max and second max payout, payments, or pcfs
    # First bin pcfs in monthly groups

    def optimalIntervals(arraylist, eligibility):
        """
        Creates two arrays of cell-wise months associated with the highest two
            average monthly values given an input of a monthly time series of
            arrays. The first array is the time interval where the maximum
            average values are found, and the second array is the time interval
            of the second highest average values. Do this with a full study
            period, or not but be careful about this.
        """
        # Groups the informing values into interval-wise averages
        months = monthlies(arraylist)

        # Multiply by eligibility layers
        months = [[months[i][0], months[i][1] * eligibility[i][1]] for
                  i in range(len(months))]

        # remove the names from the list
        justarrays = [month[1] for month in months]

        # Get rid of nans
        for i in justarrays:
            i[np.isnan(i)] = -9999

        def bestInterval(arrays):
            def bestOne(lst):
                lst = list(lst)
                ts = np.copy(lst)
                ts.sort()
                one = ts[len(ts)-1]
                p1 = lst.index(one)
                return p1
            return np.apply_along_axis(bestOne, axis=0, arr=arrays)

        def secondBestInterval(arrays):
            def bestOne(lst):
                lst = list(lst)
                ts = np.copy(lst)
                ts.sort()
                two = ts[len(ts)-2]
                p2 = lst.index(two)
                return p2
            return np.apply_along_axis(bestOne, axis=0, arr=arrays)

        bests = bestInterval(justarrays)*mask
        seconds = secondBestInterval(justarrays)*mask
        return [bests, seconds]

    # This will give the bimonthly intervals associated with the highest two
    # informing values (pcfs, frequencies, payments) for each cell
    bests, seconds = optimalIntervals(informingarrays, eligibility)

    ############### Reset and Build Seasonal Payouts ##########################
    # Run again for the study years
    dfs = indexInsurance(indexlist,
                         grid,
                         premiums,
                         bases,
                         actuarialyear,
                         studyears,   # Using the study period now
                         informingyears,
                         productivity,
                         strike,
                         acres,
                         allocation,
                         scale=True,
                         plot=False,
                         interval_restriction=False)

    targetrays = dfs[targetinfo]

    # get seasonal indemnification
    winter = [i for i in targetrays if i[0][-2:] == '11' or i[0][-2:] == '01']
    spring = [i for i in targetrays if i[0][-2:] == '02' or i[0][-2:] == '04']
    summer = [i for i in targetrays if i[0][-2:] == '05' or i[0][-2:] == '07']
    fall = [i for i in targetrays if i[0][-2:] == '08' or i[0][-2:] == '10']

    # Get total cell-wise values
    wintersum = np.nansum([i[1] for i in winter], axis=0)*mask
    springsum = np.nansum([i[1] for i in spring], axis=0)*mask
    summersum = np.nansum([i[1] for i in summer], axis=0)*mask
    fallsum = np.nansum([i[1] for i in fall], axis=0)*mask

    # Get mean cell-wise values
    wintermean = np.nanmean([i[1] for i in winter], axis=0)*mask
    springmean = np.nanmean([i[1] for i in spring], axis=0)*mask
    summermean = np.nanmean([i[1] for i in summer], axis=0)*mask
    fallmean = np.nanmean([i[1] for i in fall], axis=0)*mask

    # Get max cell-wise values
    wintermax = np.nanmax([i[1] for i in winter], axis=0)*mask
    springmax = np.nanmax([i[1] for i in spring], axis=0)*mask
    summermax = np.nanmax([i[1] for i in summer], axis=0)*mask
    fallmax = np.nanmax([i[1] for i in fall], axis=0)*mask

    ############### Use Optimal Intervals #####################################
    # We want a map where each cell sums up the payments from the intervals
    # with the two highest mean pcfs
    def optimalValues(arrays, yearstring, bests, seconds):
        """
        Here arrays should be a series of whichever with names, so the original
            timeseries returns. Then we can do this for each year and add them
            up to match the seasonal payouts. I could do all of that in a
            single function, but that could get super confusing quickly.
        """
        # Add the best and second best arrays to the stack so that each cell's
        # time-series includes these figures in the last two positions
        yearays = [i[1] for i in arrays if i[0][-6:-2] == yearstring]
        bests2 = np.copy(bests)
        seconds2 = np.copy(seconds)
        yearays.append(bests2)
        yearays.append(seconds2)

        # Remove nans, don't know how to deal with them here
        for a in yearays:
            a[np.isnan(a)] = 0

        # Cellwise function for each of the two intervals
        def bestOne(lst):
            lst = list(lst)
            ts = np.copy(lst)
            bestpos = ts[len(lst)-2]  # Best position is now second to last
            values = ts[:len(lst)-2]
            top = values[int(bestpos)]
            return top

        def secondBest(lst):
            lst = list(lst)
            ts = np.copy(lst)
            secondbestpos = ts[len(lst)-1]  # the second best is now last :)
            values = ts[:len(lst)-2]
            second = values[int(secondbestpos)]
            return second

        # Call each function and add the results together to simulate the
        # optimal 50% allocation strategy based on PCFs histories.
        bestarray = np.apply_along_axis(bestOne, axis=0, arr=yearays)*mask
        secondarray = np.apply_along_axis(secondBest, axis=0, arr=yearays)*mask
        optimal = bestarray + secondarray
        return optimal

    # Now to add up the optimal payouts over the study period
    years = [str(i) for i in range(studyears[0], studyears[1]+1)]
    optimalpayments = [optimalValues(targetrays, ys, bests,
                                     seconds) for ys in tqdm(years,
                                                             position=0)]
    optimalsum = np.nansum(optimalpayments, axis=0)*mask
    optimalmean = np.nanmean(optimalpayments, axis=0)*mask
    optimalmax = np.nanmax(optimalpayments, axis=0)*mask

    ###########################################################################
    ############################## Plot! ######################################
    ###########################################################################
    ############################ Shapefile ####################################
    if plot:
        # Main Title Business
        startyear = studyears[0]
        endyear = studyears[1]
        if startyear == endyear:
            endyear = ""
        else:
            endyear = ' - ' + str(endyear)

        fig = plt.figure()
        fig.suptitle(targetarrayname + '-Based Potential Payments: ' +
                     str(startyear)+str(endyear), fontsize=15,
                     fontweight='bold')

        # Establish Coloring Limits
        vmin = 0
        vmax = np.nanmax(np.nanmean(optimalsum)) + .5*np.nanmax(
                np.nanmean(optimalsum))
    
        # Function for fromatting colorbar labels
        setCommas = FuncFormatter(lambda x, p: format(int(x), ','))
    
        # Establish subplot structure
        ax1 = plt.subplot2grid((3, 3), (0, 0), colspan=1)
        ax2 = plt.subplot2grid((3, 3), (0, 1), colspan=1)
        ax3 = plt.subplot2grid((3, 3), (0, 2), colspan=1)  # ,rowspan = 2)
        ax4 = plt.subplot2grid((3, 3), (1, 0), colspan=1)  # ,rowspan = 2)
        ax5 = plt.subplot2grid((3, 3), (1, 1), colspan=1)  # ,rowspan = 2)
        ax6 = plt.subplot2grid((3, 3), (1, 2), colspan=1)  # ,rowspan = 2)
    
        # Set initial plot 4 parameters - this is an interactive barplot
        ax1.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax2.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax3.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax4.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax5.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax6.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
    
        # Scootch things over
        fig.tight_layout()
        fig.subplots_adjust(left=.1, bottom=0.0, right=.975, top=.92,
                            wspace=.015, hspace=.015)
    
        # Plot 1 - Payout Frequency Distribution
        im = ax1.imshow(wintersum, vmax=vmax)
        ax1.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax1.set_title('Winter')
        ax1.annotate("Intervals 11 & 1\n\n Total: $" +
                     setCommas(np.nansum(wintersum)) + "\nMax:        $" +
                     setCommas(np.nanmax(wintersum)),
                     xy=(.97, 0.1), xycoords='axes fraction', fontsize=6,
                     horizontalalignment='right', verticalalignment='bottom')
    
        # Plot 2 - Payment Calculation Factor Distribution
        im2 = ax2.imshow(springsum, vmax=vmax)
        ax2.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax2.set_title('Spring')
        ax2.annotate("Intervals 2 & 4\n\n Total: $" +
                     setCommas(np.nansum(springsum)) + "\nMax:        $" +
                     setCommas(np.nanmax(springsum)),
                     xy=(.97, 0.1), xycoords='axes fraction', fontsize=6,
                     horizontalalignment='right', verticalalignment='bottom')
    
        # Plot 3- Changes
        im3 = ax3.imshow(summersum, vmax=vmax)
        ax3.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax3.set_title('Summer')
        ax3.annotate("Intervals 5 & 7\n\n Total: $" +
                     setCommas(np.nansum(summersum)) + "\nMax:        $" +
                     setCommas(np.nanmax(summersum)),
                     xy=(.97, 0.1), xycoords='axes fraction', fontsize=6,
                     horizontalalignment='right', verticalalignment='bottom')
    
        # Plot 4
        im4 = ax4.imshow(fallsum, vmax=vmax)
        ax4.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax4.set_title('Fall')
        ax4.annotate("Intervals 8 & 10\n\n Total: $" +
                     setCommas(np.nansum(fallsum)) + "\nMax:        $" +
                     setCommas(np.nanmax(fallsum)),
                     xy=(.97, 0.1), xycoords='axes fraction', fontsize=6,
                     horizontalalignment='right', verticalalignment='bottom')
    
        # Plot 5
        im5 = ax5.imshow(optimalsum, vmax=vmax)
        ax5.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off') 
        ax5.set_title("Highest Two " + informingarrayname + " Intervals")
        ax5.annotate("Various Intervals\n\n Total: $" +
                     setCommas(np.nansum(optimalsum)) + "\nMax:        $" +
                     setCommas(np.nanmax(optimalsum)),
                     xy=(.97, 0.1), xycoords='axes fraction', fontsize=6,
                     horizontalalignment='right', verticalalignment='bottom')

        # Plot 6
        monthcolors = ["#050f51",  #'darkblue',
                       "#1131ff",  #'blue',
                       "#09bc45",  #'somegreensishcolor',
                       "#6cbc0a",  #'yellowgreen',
                       "#0d9e00",  #'forestgreen',
                       "#075e00",  #'darkgreen',
                       "#1ad10a",  #'green',
                       "#fff200",  #'yellow',
                       "#ff8c00",  #'red-orange',
                       "#b7a500",  #'darkkhaki',
                       "#6a7dfc"  #'darkerblue'
                       ]

        cmap = matplotlib.colors.LinearSegmentedColormap.from_list('mycmap',
                                                                   monthcolors)
        labels = ["Jan-Feb", "Feb-Mar", "Mar-Apr", "Apr-May", "May-Jun",
                  "Jun-Jul", "Jul-Aug", "Aug-Sep", "Sep-Oct", "Oct-Nov",
                  "Nov-Dec"]
        bests = bests*mask
        im6 = ax6.imshow(bests, cmap=cmap, label=labels)
        ax6.tick_params(which='both', right='off', left='off', bottom='off',
                        top='off', labelleft='off', labelbottom='off')
        ax6.set_title('Intervals With Highest ' + informingarrayname)
        legend_elements = [Patch(facecolor=monthcolors[i],
                                 label=labels[i]) for i in range(0, 10)]
        ax6.legend(handles=legend_elements, loc="right", fontsize=5.6,
                   bbox_to_anchor=(.98, .4))
    
        # Shared Colorbar
        # add_axes order = x0, y0, width, height
        cax1 = fig.add_axes([0.075, 0.45, 0.012, 0.375])
        cbar = plt.colorbar(im, cax=cax1, format=setCommas)
        cbar.set_label('Potential Payment ($)', rotation=90, size=10, labelpad=10,
                       fontweight='bold')
        cbar.ax.yaxis.set_label_position('left')
        cbar.ax.yaxis.set_ticks_position('left')
    
        # Parameter info
        plt.figtext(0.45, 0.3, ' Strike Level: %' + str(int(strike*100)) +
                    '; Rate Year: ' + str(actuarialyear) + '; Acres: ' +
                    str(acres), backgroundcolor='darkgreen', color='white',
                    weight='roman', size='x-small')
    if save:
        savepath = ("G:\\My Drive\\THESIS\\data\\Index Project\\" +
                    "Optimal Intervals\\")
        seriesdict = {0: 'premiums', 1: 'indemnities', 2: 'frequencies',
                      3: 'pcfs', 4: 'nets', 5: 'lossratios'}

        toRaster(bests, savepath + informfolder + "\\nad83\\" +
                 seriesdict[targetinfo] + "\\" + savename + "_bests_" +
                 str(int(strike*100)) + ".tif", geom, proj)
        toRaster(wintermean, savepath + informfolder + "\\nad83\\" +
                 seriesdict[targetinfo] + "\\" + savename + "_winter_" +
                 str(int(strike*100)) + ".tif", geom, proj)
        toRaster(springmean, savepath + informfolder + "\\nad83\\" +
                 seriesdict[targetinfo] + "\\" + savename + "_spring_" +
                 str(int(strike*100)) + ".tif", geom, proj)
        toRaster(summermean, savepath + informfolder + "\\nad83\\" +
                 seriesdict[targetinfo] + "\\" + savename +
                 "_summer_" + str(int(strike*100)) + ".tif", geom, proj)
        toRaster(fallmean, savepath + informfolder + "\\nad83\\" +
                 seriesdict[targetinfo] + "\\" + savename +
                 "_fall_" + str(int(strike*100)) + ".tif", geom, proj)
        toRaster(optimalmean, savepath + informfolder + "\\nad83\\" +
                 seriesdict[targetinfo] + "\\" + savename +
                 "_optimal_" + str(int(strike*100)) + ".tif",  geom, proj)

    ###########################################################################
    ######################### Save Maxes, sums, index, and strike #############
    ###########################################################################
    dfrm = {"index": savename,
            "strike": strike,
            "wintermax": np.nanmax(wintermax),
            "springmax": np.nanmax(springmax),
            "summermax": np.nanmax(summermax),
            "fallmax": np.nanmax(fallmax),
            "optimalmax": np.nanmax(optimalmax),
            "wintermean": np.nanmean(wintermean),
            "springmean": np.nanmean(springmean),
            "summermean": np.nanmean(summermean),
            "fallmean": np.nanmean(fallmean),
            "optimalmean": np.nanmean(optimalmean),
            "wintertotal": np.nansum(wintersum),
            "springtotal": np.nansum(springsum),
            "summertotal": np.nansum(summersum),
            "falltotal": np.nansum(fallsum),
            "optimaltotal": np.nansum(optimalsum)}

    return dfrm


###############################################################################
###################### Probability Matching for strike levels #################
###############################################################################
def probMatch(indexlist, noaalist, strike, binumber=100, limmax=0, plot=True):
    '''
    rasterpath = path to folder of drought index rasters to be made into arrays
    noaapath = path to folder of rma rainfall rasters to be made into arrays
    strike = PRF strike level to convert
    binumber = number of bins to put values in
    linmax = index value limit for noaa precip (it extends quite far)

    This will take in a list of drought index values, generate a histogram for both that and the 
        noaa index and then calculate the drought index value that corresponds with an equal 
        probability of occurence in the noaa index for a chosen strike level. 
        
    '''    
   
    # Tinker
    name = indexlist[0][0][:-7] + ' Value Distribution'
    startyear = indexlist[0][0][-6:-2]
    endyear = indexlist[len(indexlist)-1][0][-6:-2]
    arrays = [ray[1] for ray in indexlist]
    na = arrays[0][0,0]    
    for ray in arrays:
        ray[ray == na] = np.nan
    
    # Mask the array for the histogram (Makes this easier)
    noaarays = [ray[1] for ray in noaalist]
    noaarays = np.ma.masked_invalid(noaarays)
    darrays = np.ma.masked_invalid(arrays)
    
    ###########################################################################
    ############### NOAA First ################################################
    ###########################################################################

    # Get min and maximum values
    amin = np.min(noaarays)
    amax = np.max(noaarays)
    printmax = np.max(noaarays)
    if limmax > 0:
        plotmax = limmax
    else:
        plotmax = amax

    # create histogram with frequency and bin values
    noaahists,noaabins = np.histogram(noaarays,range = [amin,amax],bins = 5000,normed = True)    
    
    # and another for plotting
    noaaplothists,noaaplotbins = np.histogram(noaarays,range = [amin,plotmax],bins = binumber,normed = False)    
    
    # Find the bin width
    noaawidth = noaabins[1] - noaabins[0]
    plotwidth = noaaplotbins[1] - noaaplotbins[0]
    
    # Calculate the bin that corresponds with the strike level
    for i in range(len(noaabins)):
        if strike >= noaabins[i] - noaawidth and strike <= noaabins[i] + noaawidth:
            binindex = i
            break
    
    # Calculate the portion of area under the curve compared to the total area
    portion = sum(np.diff(noaabins[:binindex])*noaahists[:binindex-1])        
    ###########################################################################
    ############### Drought Index Second ######################################
    ###########################################################################
    # create histogram with frequency and bin values
    dmin = np.min(darrays)
    dmax = np.max(darrays)
    dhists,dbins = np.histogram(darrays,range = [dmin,dmax],bins = 5000,normed = True)    
    dplothists,dplotbins = np.histogram(darrays,range = [dmin,dmax],bins = binumber,normed = False)    
    
    # Find the bin width
    dwidth = dbins[1] - dbins[0]    
    dplotwidth = dplotbins[1] - dplotbins[0]
    

    # Calculate area proportions until they almost match the portion cacluated for the noaa arrays
    for i in range(1,len(dbins)):
        dportion = sum(np.diff(dbins[:i])*dhists[:i-1]) 
        if dportion >= portion - .01 and dportion <= portion + .01: 
            newstrike = dbins[i]
            newhist = dhists[i]        
            break
                
    ############### plot both ######################################################################
    if plot == True:
        fig =  plt.figure()
        fig.suptitle(name+'\n'+str(startyear)+' - ' +endyear + '\n RMA Strike Level: '+ str(round(strike,2)) + '; Alt Strike Level: ' + str(round(newstrike,2)), fontsize="x-large")    
            
        # Establish subplot structure
        ax1 = plt.subplot2grid((2, 3), (0, 0),rowspan = 3, colspan = 2)
        ax2 = plt.subplot2grid((2, 3), (1, 2), colspan = 1)  
    #    fig.subplots_adjust(wspace=.25,hspace = .25)
    
        # Plot 1 - Drought Index Distribution with new strike level highlighted.
    #    ax1.tick_params(which='both',right = 'off',left = 'off', bottom='off', top='off',labelleft = 'off',labelbottom='off')
        width = .65 * (dplotbins[1] - dplotbins[0])
        center = (dplotbins[:-1] + dplotbins[1:]) / 2
        ax1.bar(center, dplothists, align='center', width=width, color = 'g')      
        ax1.axvline(newstrike, color='black', linestyle='solid', linewidth=6)
        ax1.axvline(newstrike, color='red', linestyle='solid', linewidth=3.5)
            
        # Set initial plot 2 parameters
        ax2.tick_params(which='both',right = 'on',left = 'off', bottom='on', top='off',labelleft = 'on',labelbottom='on')
        ax2.set_title('RMA Index Frequencies')
    
        width = .65 * (noaaplotbins[1] - noaaplotbins[0])
        center = (noaaplotbins[:-1] + noaaplotbins[1:]) / 2
        ax2.bar(center, noaaplothists, align='center', width=width)
        ax2.axvline(strike, color='black', linestyle='solid', linewidth=4)
        ax2.axvline(strike, color='orange', linestyle='solid', linewidth=1.5)
        ax2.yaxis.set_label_position('right')
        ax2.yaxis.set_ticks_position('right')
        
    return round(newstrike,4)

###############################################################################
######################## Define Raster Manipulation Class #####################
###############################################################################
class RasterArrays:
    '''
    This class creates a series of Numpy arrays from a folder containing a
    series of rasters. With this you can retrieve a named list of arrays, a
    list of only arrays, and a few general statistics or fields. It also
    includes several sample methods that might be useful when manipulating or
    analysing gridded data.

        Initializing arguments:

            rasterpath(string) = directory containing series of rasters.
            navalue(numeric) = value used for NaN in raster, or user specified

        Attributes:

            namedlist (list) = [[filename, array],[filename, array]...]
            geometry (tuple) = (spatial geometry): (upper left coordinate,
                                          x-dimension pixel size,
                                          rotation,
                                          lower right coordinate,
                                          rotation,
                                          y-dimension pixel size)
            crs (string) = Coordinate Reference System in Well-Know Text Format
            arraylist (list) = [array, array...]
            minimumvalue (numeric)
            maximumvalue (numeric)
            averagevalues (Numpy array)

        Methods:

            standardizeArrays = Standardizes all values in arrays
            calculateCV = Calculates Coefficient of Variation
            generateHistogram = Generates histogram of all values in arrays
            toRaster = Writes a singular array to raster
            toRasters = Writes a list of arrays to rasters
    '''
    # Reduce memory use of dictionary attribute storage
    __slots__ = ('namedlist', 'geometry', 'crs', 'exceptions', 'arraylist',
                 'minimumvalue', 'maximumvalue', 'averagevalues', 'navalue')

    # Create initial values
    def __init__(self, rasterpath, navalue=-9999):
        [self.namedlist, self.geometry,
        self.crs] = readRasters2(rasterpath, navalue)
        self.arraylist = [a[1] for a in self.namedlist]
        self.minimumvalue = np.nanmin(self.arraylist)
        self.maximumvalue = np.nanmax(self.arraylist)
        self.averagevalues = np.nanmean(self.arraylist, axis=0)
        self.navalue = navalue
    # Establish methods
    def standardizeArrays(self):
        '''
        Min/Max standardization of array list, returns a named list
        '''
        print("Standardizing arrays...")
        mins = np.nanmin(self.arraylist)
        maxes = np.nanmax(self.arraylist)

        def singleArray(array, mins, maxes):
            '''
            calculates the standardized values of a single array
            '''
            newarray = (array - mins)/(maxes - mins)
            return newarray

        standardizedarrays = []
        for i in range(len(self.arraylist)):
            standardizedarrays.append([self.namedlist[i][0],
                                       singleArray(self.namedlist[i][1],
                                                   mins, maxes)])
        return standardizedarrays

    def calculateCV(self, standardized=True):
        '''
         A single array showing the distribution of coefficients of variation
             throughout the time period represented by the chosen rasters
        '''
        # Get list of arrays
        if standardized is True:
            numpyarrays = self.standardizeArrays()
        else:
            numpyarrays = self.namedlist

        # Get just the arrays from this
        numpylist = [a[1] for a in numpyarrays]

        # Simple Cellwise calculation of variance
        sds = np.nanstd(numpylist, axis=0)
        avs = np.nanmean(numpylist, axis=0)
        covs = sds/avs

        return covs

    def generateHistogram(self,
                          bins=1000,
                          title="Value Distribution",
                          xlimit=0,
                          savepath=''):
        '''
        Creates a histogram of the entire dataset for a quick view.

          bins = number of value bins
          title = optional title
          xlimit = x-axis cutoff value
          savepath = image file path with extension (.jpg, .png, etc.)
        '''
        print("Generating histogram...")
        # Get the unnamed list
        arrays = self.arraylist

        # Mask the array for the histogram (Makes this easier)
        arrays = np.ma.masked_invalid(arrays)

        # Get min and maximum values
        amin = np.min(arrays)
        if xlimit > 0:
            amax = xlimit
        else:
            amax = np.max(arrays)

        # Get the bin width, and the frequency of values within
        hists, bins = np.histogram(arrays, range=[amin, amax],
                                   bins=bins, normed=False)
        width = .65 * (bins[1] - bins[0])
        center = (bins[:-1] + bins[1:]) / 2

        # Make plotting optional
        plt.ioff()

        # Create Pyplot figure
        plt.figure(figsize=(8, 8))
        plt.bar(center, hists, align='center', width=width)
        title = (title + ":\nMinimum: " + str(round(amin, 2)) +
                 "\nMaximum: " + str(round(amax, 2)))
        plt.title(title, loc='center')

        # Optional write to image
        if len(savepath) > 0:
            print("Writing histogram to image...")
            savepath = os.path.normpath(savepath)
            if not os.path.exists(os.path.dirname(savepath)):
                os.mkdir(os.path.dirname(savepath))
            plt.savefig(savepath)
            plt.close()
        else:
            plt.show()
    
    def toRaster(self, array, savepath):
        '''
        Uses the geometry and crs of the rasterArrays class object to write a
            singular array as a GeoTiff.
        '''
        print("Writing numpy array to GeoTiff...")
        # Check that the Save Path exists
        savepath = os.path.normpath(savepath)
        if not os.path.exists(os.path.dirname(savepath)):
            os.mkdir(os.path.dirname(savepath))

        # Retrieve needed raster elements
        geometry = self.geometry
        crs = self.crs
        xpixels = array.shape[1]
        ypixels = array.shape[0]

        # This helps sometimes
        savepath = savepath.encode('utf-8')

        # Create file
        image = gdal.GetDriverByName("GTiff").Create(savepath,
                                                     xpixels,
                                                     ypixels,
                                                     1,
                                                     gdal.GDT_Float32)
        # Save raster and attributes to file
        image.SetGeoTransform(geometry)
        image.SetProjection(crs)
        image.GetRasterBand(1).WriteArray(array)
        image.GetRasterBand(1).SetNoDataValue(self.navalue)

    def toRasters(self, namedlist, savefolder):
        """
        namedlist (list) = [[name, array], [name, array], ...]
        savefolder (string) = target directory
        """
        # Create directory if needed
        print("Writing numpy arrays to GeoTiffs...")
        savefolder = os.path.normpath(savefolder)
        savefolder = os.path.join(savefolder, '')
        if not os.path.exists(savefolder):
            os.mkdir(savefolder)

        # Get spatial reference information
        geometry = self.geometry
        crs = self.crs
        sample = namedlist[0][1]
        ypixels = sample.shape[0]
        xpixels = sample.shape[1]

        # Create file
        for array in tqdm(namedlist):
            image = gdal.GetDriverByName("GTiff").Create(savefolder+array[0] +
                                                         ".tif",
                                                         xpixels,
                                                         ypixels,
                                                         1,
                                                         gdal.GDT_Float32)
            image.SetGeoTransform(geometry)
            image.SetProjection(crs)
            image.GetRasterBand(1).WriteArray(array[1])
#            image.GetRasterBand(1).SetNoDataValue(self.navalue)


###############################################################################
##################### Convert single raster to array ##########################
###############################################################################
def readRaster(rasterpath, band, navalue=-9999):
    """
    rasterpath = path to folder containing a series of rasters
    navalue = a number (float) for nan values if we forgot 
                to translate the file with one originally
    
    This converts a raster into a numpy array along with spatial features needed to write
            any results to a raster file. The return order is:
                
      array (numpy), spatial geometry (gdal object), coordinate reference system (gdal object)
    
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
    return(array,geometry,arrayref)

###############################################################################
##################### Convert single raster to array ##########################
###############################################################################
def readRasterAWS(awspath,navalue = -9999):
    """
    rasterpath = path to folder containing a series of rasters
    navalue = a number (float) for nan values if we forgot 
                to translate the file with one originally
    
    This converts a raster into a numpy array along with spatial features needed to write
            any results to a raster file. The return order is:
                
      array (numpy), spatial geometry (gdal object), coordinate reference system (gdal object)
    
    """
    with rasterio.open(awspath) as src:
        array = src.read(1,window = ((0,120),(0,300)))
        geometry = src.get_transform()
        arrayref = src.get_crs()
    array = array.astype(float)
    if np.nanmin(array) < navalue:
        navalue = np.nanmin(array)
    array[array==navalue] = np.nan
    return array
###############################################################################
######################## Convert multiple rasters #############################
####################### into numpy arrays #####################################
###############################################################################
def readRasters(files, navalue=-9999):
    """
    files = list of files to read in
    navalue = a number (float) for nan values if we forgot 
                to translate the file with one originally
    
    This converts monthly rasters into numpy arrays and them as a list in another
            list. The other parts are the spatial features needed to write
            any results to a raster file. The list order is:
                
      [[name_date (string),arraylist (numpy)], spatial geometry (gdal object),
       coordinate reference system (gdal object)]
    
    The file naming convention required is: "INDEXNAME_YYYYMM.tif"

    """
    print("Converting raster to numpy array...")
    files = [f for f in files if os.path.isfile(f)]
    names = [os.path.basename(files[i]) for i in range(len(files))]
    sample = gdal.Open(files[1])
    geometry = sample.GetGeoTransform()
    arrayref = sample.GetProjection()
    alist = []
    for i in tqdm(range(0,len(files))):
        rast = gdal.Open(files[i])
        array = np.array(rast.GetRasterBand(1).ReadAsArray())
        array = array.astype(float)
        array[array == navalue] = np.nan
        name = str.upper(names[i][:-4])  # the file name excluding its extention (may need to be changed if the extension length is not 3)
        alist.append([name,array])  # It's confusing but we need some way of holding these dates. 
    return(alist,geometry,arrayref)

###############################################################################
######################## Convert multiple rasters #############################
####################### into numpy arrays silently ############################
###############################################################################
def readRasters2(rasterpath, navalue=-9999):
    """
    rasterpath = path to folder containing a series of rasters
    navalue = a number (float) for nan values if we forgot
                to translate the file with one originally

    This converts monthly rasters into numpy arrays and them as a list in
            another list. The other parts are the spatial features needed to
            write any results to a raster file. The list order is:

      [[name_date (string), arraylist (numpy)], spatial geometry (gdal object),
       coordinate reference system (gdal object)]

    The file naming convention required is: "INDEXNAME_YYYYMM.tif"
    """
    alist = []
    files = glob.glob(os.path.join(rasterpath, '*'))
    files = [f for f in files if os.path.isfile(f)]
    names = [os.path.basename(files[i]) for i in range(len(files))]
    for i in tqdm(range(len(files)), position=0):
        try:
            ext = os.path.splitext(files[i])[1]
            rast = gdal.Open(files[i])
            if 'geometry' and 'arrayref' not in locals():
                geometry = rast.GetGeoTransform()
                arrayref = rast.GetProjection()
            array = np.array(rast.GetRasterBand(1).ReadAsArray())
            del rast
            array = array.astype(float)
            array[array == navalue] = np.nan
            name = str.upper(names[i][:-len(ext)])
            alist.append([name, array])
        except RuntimeError:
            pass
    return(alist, geometry, arrayref)

###########################################################################
###################### Read Arrays from NPZ or NPY format #################
###########################################################################
def readArrays(path):
    '''
    This will only work if the date files are in the same folder as the .np or .npz
        Otherwise it outputs the same results as the readRaster functions. 
        No other parameters required. 
    '''
    datepath = path[:-10]+"dates"+path[-4:]
    with np.load(path) as data:
        arrays = data.f.arr_0
        data.close()
    with np.load(datepath) as data:
        dates = data.f.arr_0
        data.close()
        dates = [str(d) for d in dates]
    arraylist = [[dates[i],arrays[i]] for i in range(len(arrays))]
    return(arraylist)
    
###########################################################################
############## Little Standardization function for differenct scales ######
###########################################################################  
## Min Max Standardization 
def standardize(indexlist):
    if type(indexlist[0][0])==str:
        arrays = [a[1] for a in indexlist]
    else:
        arrays = indexlist
    mins = np.nanmin(arrays)
    maxes = np.nanmax(arrays)
    def single(array,mins,maxes):    
        newarray = (array - mins)/(maxes - mins)
        return(newarray)
    standardizedlist = [[indexlist[i][0],single(indexlist[i][1],mins,maxes)] for i in range(len(indexlist))]
    return(standardizedlist)

# SD Standardization
def standardize2(indexlist):
    arrays = [indexlist[i][1] for i in range(len(indexlist))]
    mu = np.nanmean(arrays)
    sd = np.nanstd(arrays)
    def single(array,mu,sd):    
        newarray = (array - mu)/sd
        return(newarray)
    standardizedlist = [[indexlist[i][0],single(indexlist[i][1],mu,sd)] for i in range(len(indexlist))]
    return(standardizedlist)

###############################################################################
##################### Write single array to tiffs #############################
###############################################################################
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
      
###############################################################################
##################### Write arrays to tiffs ###################################
###############################################################################
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
        image = gdal.GetDriverByName("GTiff").Create(path+"\\"+ray[0]+".tif",xpixels, ypixels, 1,gdal.GDT_Float32)
        image.SetGeoTransform(geometry)
        image.SetProjection(srs)
        image.GetRasterBand(1).WriteArray(ray[1])
          
