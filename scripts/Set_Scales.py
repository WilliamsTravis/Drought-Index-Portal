4# -*- coding: utf-8 -*-
"""
Created on Thu Feb 14 23:14:33 2019

@author: User
"""
import os
import pandas as pd
import sys
from tqdm import tqdm
import xarray as xr

# Check if we are working in Windows or Linux to find the data directory
if sys.platform == 'win32':
    os.chdir('C:/Users/User/github/Ubuntu-Practice-Machine')
    data_path = 'f:/'
else:
    os.chdir('/root/Sync/Ubuntu-Practice-Machine/')  # might need for automation...though i could automate cd and back
    data_path = '/root/Sync'

local_indices = ['spi1', 'spi2', 'spi3', 'spi4', 'spi5', 'spi6', 'spi7',
                 'spi8', 'spi9', 'spi10', 'spi11', 'spi12', 'spei1', 'spei2',
                 'spei3', 'spei4', 'spei5', 'spei6', 'spei7', 'spei8', 'spei9',
                 'spei10', 'spei11', 'spei12', 'pdsi', 'pdsisc', 'pdsiz',
                 'leri1', 'leri3',
                 'eddi1', 'eddi2', 'eddi3', 'eddi4', 'eddi5', 'eddi6', 'eddi7',
                 'eddi8', 'eddi9', 'eddi10', 'eddi11', 'eddi12', 'tmin',
                 'tmax', 'tdmean', 'tmean', 'ppt', 'vpdmax', 'vpdmin']
index_paths = [os.path.join(data_path,'data/droughtindices/netcdfs',
                            i  + '.nc') for i in local_indices]

maxes = {}
mins = {}
for i in tqdm(range(len(index_paths)), position=0):
    try:
        with xr.open_dataset(index_paths[i]) as data:
            indexlist = data
            data.close()
        mx = float(indexlist.max().value)
        mn = float(indexlist.min().value)
        maxes[local_indices[i]] = mx
        mins[local_indices[i]] = mn
    except:
        pass

df = pd.DataFrame([maxes, mins]).T
df.columns = ['max', 'min']
df['index'] = df.index
df.to_csv('data/tables/index_ranges.csv', index=False)
