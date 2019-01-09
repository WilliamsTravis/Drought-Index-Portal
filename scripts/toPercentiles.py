# -*- coding: utf-8 -*-
"""
Not fully sure how to do this, but I am trying to calculate each drought index
value as a percentile of all values. Well, that shouldn't be too difficult, but
how meaningful is it? If the numbers have already been calculated to fit a
certain distribution, will this change anything vital? 


Created on Tue Nov 27 16:06:52 2018

@author: User
"""
import os
from scipy.stats import percentileofscore as pos
from scipy.stats import rankdata

import sys
import warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, 'c:/users/user/github/PRF-ALTIND')
from functions import *
os.chdir('c:/users/user/github/')

# In[] Get index list dictionary
indices = ['noaa', 'pdsi', 'pdsisc', 'pdsiz', 'spi1', 'spi2', 'spi3',
           'spi6', 'spei1', 'spei2', 'spei3', 'spei6', 'eddi1', 'eddi2',
           'eddi3', 'eddi6']
arraydict = {}
for i in tqdm(indices, position=0):
    timeseries = npzIn("data/indices/" + i + "_arrays.npz",
                       "data/indices/" + i + "_dates.npz")
    arraydict[i] = timeseries


# In[] Create single vector of percentiles
indexlist = arraydict['spei6']
arrays = [a[1] for a in indexlist]
lst = [a[55, 55] for a in arrays]


def hist(lst, bins=100):
    plt.hist(lst, bins=bins)

# Now do that for every location in a 3d array
def percentileArrays(indexlist):
    '''
    a list of 2d numpy arrays, or 3d numpy array
    '''
    def percentiles(lst):
        '''
        lst = single time series of numbers

        So this is trickier than the simple ranked percentile method shown
            below. The distribution of percentiles should match that of the
            original values each percentage is associated with. There is
            obviously a way to do this, however, each of those original values
            were calculated as relative impact numbers. If we were to take
            each time series of values (site by site I mean) and convert to
            percentiles according to the distribution of that time-series,
            wouldn't we be losing the relative nature of the original values.
            So, if we have a location where an index value of 0.25 is
            associated with the 110th percentile, and another site where 0.25
            is associated with the 125th, suddenly the standardization intended
            to make the index spatially comparable is lost! I do not how to
            approach this.
        '''

        import scipy.stats
        scipy.stats.moment(lst, 1)

        pct = rankdata(lst)/len(lst)
        return pct

    arrays = [a[1] for a in indexlist]  # scipy.stats
    names = [a[0] for a in indexlist]
    mask = arrays[0] * 0 + 1
    pcts = np.apply_along_axis(percentiles, axis=0, arr=arrays)
    pcts = pcts*mask
    pcts = [pct for pct in pcts]
    indexlist = [[names[i], pcts[i]] for i in range(len(pcts))]
    return indexlist


# Loop through each and save to a new file. This should make strike matching
    # 100% easier. Remember to use original...This totally didn't work for that
for i in tqdm(indices, position=0):
    indexlist = arraydict[i]
    # if "eddi" in i:
    #     indexlist = [[a[0], a[1] * -1] for a in indexlist]
    # Adjust for outliers, here?
    if "noaa here for insurance" not in i:
        # Adjust for outliers
        arrays = [a[1] for a in indexlist]
        sd = np.nanstd(arrays)
        mean = np.nanmean(arrays)
        thresholds = [-3*sd, 3*sd]
        for a in arrays:
            a[a <= thresholds[0]] = thresholds[0]
            a[a >= thresholds[1]] = thresholds[1]
        indexlist = [[indexlist[i][0],
                      arrays[i]] for i in range(len(indexlist))]
        newlist = percentileArrays(indexlist)
    else:
        newlist = indexlist
    npzOut(newlist, r"D:\data\droughtindices\npz\percentiles")
