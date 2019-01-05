# -*- coding: utf-8 -*-
"""
Take tifs and convert to npz for faster i/o

Created on Fri Jan  4 18:58:26 2019

@author: User
"""
# -*- coding: utf-8 -*-
"""
Create single multidimensional numpy files for each index
Created on Fri Jun  8 20:48:33 2018

@author: User
"""
import os
os.chdir(r"C:\Users\User\github\PRF-ALTIND")
from functions import *
os.chdir("C:/users/user/github/")
mask = readRaster("d:\\data\\masks\\nad83\\mask25.tif", 1, -9999)[0]
indexnames = ['d:\\data\\droughtindices\\noaa\\nad83\\',
              'd:\\data\\droughtindices\\pdsi\\nad83\\',
              'd:\\data\\droughtindices\\pdsisc\\nad83\\',
              'd:\\data\\droughtindices\\pdsiz\\nad83\\',
              'd:\\data\\droughtindices\\spi\\nad83\\1month\\',
              'd:\\data\\droughtindices\\spi\\nad83\\2month\\',
              'd:\\data\\droughtindices\\spi\\nad83\\3month\\',
              'd:\\data\\droughtindices\\spi\\nad83\\6month\\',
              'd:\\data\\droughtindices\\spei\\nad83\\1month\\', 
              'd:\\data\\droughtindices\\spei\\nad83\\2month\\', 
              'd:\\data\\droughtindices\\spei\\nad83\\3month\\', 
              'd:\\data\\droughtindices\\spei\\nad83\\6month\\',
              'd:\\data\\droughtindices\\eddi\\nad83\\1month\\',
              'd:\\data\\droughtindices\\eddi\\nad83\\2month\\',
              'd:\\data\\droughtindices\\eddi\\nad83\\3month\\',
              'd:\\data\\droughtindices\\eddi\\nad83\\6month\\']
savenames = ['noaa','pdsi','pdsisc','pdsiz','spi1','spi2','spi3','spi6',
             'spei1','spei2','spei3','spei6', 'eddi1', 'eddi2', 'eddi3',
             'eddi6']

for i in tqdm(range(len(indexnames)), position=0):
    print(savenames[i])
    arraylist = readRasters2(indexnames[i], -9999)[0]
    arrays = [a[1]*mask for a in arraylist]
    dates = [a[0] for a in arraylist]
    np.savez_compressed("d:\\data\\droughtindices\\npz\\" + savenames[i] +
                        "_arrays.npz",arrays)
    np.savez_compressed("d:\\data\\droughtindices\\npz\\" + savenames[i] +
                        "_dates.npz",dates)
