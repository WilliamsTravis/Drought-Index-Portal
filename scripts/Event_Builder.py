# -*- coding: utf-8 -*-
"""
Created on Tue May 14 16:09:16 2019

@author: User
"""

from collections import OrderedDict
import numpy as np
import pandas as pd
import sys

try:
    csv_path = sys.argv[1]
except:
    csv_path = 'C:/users/user/downloads/quadthree.csv'

df = pd.read_csv(csv_path)
d4s = df[['month', 'd4']]
months = df['month']
array = np.array(d4s['d4'])
events = np.copy(array)
event = 1
event_loc = np.where(array != 0)[0]

# Loop through even locations 
for i in range(len(event_loc)-1):
    # If there is no gap
    if event_loc[i+1] == event_loc[i]+1:
        # assign an event id to the full event array
        events[event_loc[i]] = event
    # If there is a gap
    else:
        # We have a new event id
        events[event_loc[i]] = event
        event += 1

# End case
if events[event_loc[-1]] > 0:
    events[event_loc[-1]] = events[event_loc[-2]]

# Unique event array
unique_events = np.unique(events[events != 0])

# Required information lists
month_ranges = []
maxes = []
durations = []
for e in unique_events:
    mx = np.max(array[events == e])
    duration = len(array[events== e])
    idxs = np.where(events == e)[0]
    m1 = months[min(idxs)]
    m2 = months[max(idxs)]
    month_range = m1 + ' - ' + m2
    month_ranges.append(month_range)
    maxes.append(mx)
    durations.append(duration)

# Build dataframe
df = pd.DataFrame(OrderedDict({'id':unique_events,
                               'max_area': maxes,
                               'duration': durations,
                               'period': month_ranges}))

df.to_csv('c:/users/user/desktop/sample_drought_df.csv', index=False)