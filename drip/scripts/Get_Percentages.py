# -*- coding: utf-8 -*-
"""
Created on Tue May 14 11:39:16 2019

@author: User
"""

import os
import tqdm
from functions import Admin_Elements, Index_Maps, movie, im


# In[] Supporting functions
def retrieveData(signal, function, choice, location):
    '''
    This takes the user defined signal and uses the Index_Map class to filter'
    by the selected dates and return the singular map, the 3d timeseries array,
    and the colorscale.

    sample arguments:
        signal = [[[2000, 2017], [1, 12], [ 4, 5, 6, 7]], 'Viridis', 'no']
        choice = 'pdsi'
        function = 'omean'
    '''
    # Retrieve signal elements
    time_data = signal[0]
    colorscale = signal[1]

    # Determine the choice_type based on function
    choice_types = {'omean': 'original',
                    'omin': 'original',
                    'omax': 'original',
                    'pmean': 'percentile',
                    'pmin': 'percentile',
                    'pmax': 'percentile',
                    'oarea': 'area',
                    'ocorr': 'correlation_o',
                    'pcorr': 'correlation_p'}
    choice_type = choice_types[function]

    # Retrieve data package
    data = Index_Maps(choice, choice_type, time_data, colorscale)

    # Set mask (also sets coordinate dictionary)
    data.setMask(location, crdict)

    return data


# In[] Administrative and geometric info
resolution = 0.25
admin = Admin_Elements(resolution)

[state_array, county_array, grid, mask,
 source, albers_source, crdict, admin_df] = admin.getElements()

# In[] Specifications
year_range = [2000, 2017]
month_range = [1, 12]
choice = 'pdsi'

months = list(range(1, 13))
signal = [[year_range, month_range, months], 'Viridis', 'no']
function = 'oarea'
location  =  ['all', 'y', 'x', 'Contiguous United States', 0]

# In[] Create Dataset
data = retrieveData(signal, function, choice, location)
ts_series, ts_series_ninc, dsci = data.getArea(crdict)

# In[] Loop through time periods
years = [[1980,1980], [1983, 1983], [1986, 1986]]
months = [[6, 11], [6, 8], [6, 8]]
events = ['1', '2', '3']
summaries = ['a', 'b', 'c']
costs = ['c1', 'c2','c3']

dscis = []
percentages = []
for i in tqdm(range(len(years))):
    year_range = years[i]
    month_range = months[i]
    data = retrieveData(signal, function, choice, location)
    ts_series, ts_series_ninc, dsci = data.getArea(crdict)
    dscis.append(dsci)
    percentages.append(ts_series)

data = {'events': events, 'costs' : costs, 'summaries': summaries}

i = dscis[0].index(max(dscis[0]))
e1 = [p[i] for p in percentages[0]]
