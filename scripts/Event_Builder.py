# -*- coding: utf-8 -*-
"""
Created on Tue May 14 16:09:16 2019

@author: User
"""


import pandas as pd
import numpy as np
from collections import OrderedDict

df = pd.read_csv('c:/users/user/downloads/timeseries_1 (13).csv')
d4s = df[['month', 'd4']]
months = df['month']
array = np.array(d4s['d4'])
events = np.copy(array)
event = 1
event_loc = np.where(array != 0)[0]

for i in range(len(event_loc)-1):
    if event_loc[i+1] == event_loc[i]+1:
        events[event_loc[i]] = event
    else:
        events[event_loc[i]] = 0  # this will knock a few months off...fix
        event += 1

unique_events = np.unique(events.astype(int))
unique_events = unique_events[unique_events != 0]

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