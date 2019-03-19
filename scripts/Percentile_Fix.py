# -*- coding: utf-8 -*-
"""
Created on Mon Mar 18 19:11:57 2019

@author: User
"""
from functions import toNetCDFPercentile
from tqdm import tqdm

local_indices = ['spi1', 'spi2', 'spi3', 'spi6', 'spei1', 'spei2', 'spei3',
                 'spei6', 'pdsi', 'pdsisc', 'pdsiz']
root = 'f:/data/droughtindices/netcdfs/'
perc_root = root + 'percentiles/'
src_paths = [root + index + '.nc' for index in local_indices]
dst_paths = [perc_root + index + '.nc' for index in local_indices]

for i in tqdm(range(len(src_paths)), position=0):
    toNetCDFPercentile(src_paths[i], dst_paths[i])