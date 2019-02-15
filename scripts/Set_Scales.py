# -*- coding: utf-8 -*-
"""
Created on Thu Feb 14 23:14:33 2019

@author: User
"""
import os
import sys
from tqdm import tqdm
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    sys.path.extend(['Z:/Sync/Ubuntu-Practice-Machine/',
                     'C:/Users/User/github/Ubuntu-Practice-Machine',
                     'C:/Users/travi/github/Ubuntu-Practice-Machine'])
    data_path = 'f:/'
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')  # might need for automation...though i could automate cd and back
    data_path = '/root/Sync'


local_indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2',
                 'spei3', 'spei6', 'pdsi', 'pdsisc', 'pdsiz', 'eddi1',
                 'eddi2', 'eddi3', 'eddi6', 'noaa']
index_paths = [os.path.join(data_path,'data/droughtindices/netcdfs', i  + '.nc') for
               i in local_indices]

maxes = {}
mins = {}
for i in tqdm(range(len(index_paths)), position=0):
    with xr.open_dataset(index_paths[i]) as data:
        indexlist = data
        data.close()
    mx = float(indexlist.max().value)
    mn = float(indexlist.min().value)
    maxes[local_indices[i]] = mx
    mins[local_indices[i]] = mn

df = pd.DataFrame([maxes, mins]).T
df.columns = ['max', 'min']
df['index'] = df.index
df.to_csv('../data/index_ranges.csv', index=False)
