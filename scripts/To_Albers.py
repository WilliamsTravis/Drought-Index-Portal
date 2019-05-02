# -*- coding: utf-8 -*-
"""
This will take existing .nc files in WGS84 and project them into Alber's Equal
Area Conic. These will be used for the 'Drought Area' option: Instead of
reprojecting and pulling each array in the timeseries in memory, we will
reproject a single array in memory and use it as a mask in a disk operation
to pull only the smaller time series of percentages in.

That is the plan at least.

Created on Tue Apr 30 11:03:20 2019

@author: User
"""
import glob
import os
import sys

if sys.platform == 'win32':
    home_path = 'c:/users/user/github/ubuntu-practice-machine'
    data_path = 'f:/data/droughtindices/netcdfs'
else:
    home_path = '/root/Sync/Ubuntu-Practice-Machine'
    data_path = '/root/Sync/data/droughtindices/netcdfs'
os.chdir(home_path)

# So, I am only going to use the original index values in this function
files = glob.glob(os.path.join(data_path, '*nc'))

for file in files:
    
