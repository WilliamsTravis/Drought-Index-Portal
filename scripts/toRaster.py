# -*- coding: utf-8 -*-
"""
Created on Tue Jan  8 11:06:01 2019

@author: User
"""

import os
os.chdir(r"C:\Users\User\github\Ubuntu-Practice-Machine")
from functions import *
mask, geom, proj = readRaster("d:\\data\\masks\\nad83\\mask25.tif", 1, -9999)
npzpaths = {'noaa': "d:\\data\\droughtindices\\npz\\percentiles\\noaa",
            'pdsi': "d:\\data\\droughtindices\\npz\\percentiles\\pdsi",
            'pdsisc': "d:\\data\\droughtindices\\npz\\percentiles\\pdsisc",
            'pdsiz': "d:\\data\\droughtindices\\npz\\percentiles\\pdsiz",
            'spi1': "d:\\data\\droughtindices\\npz\\percentiles\\spi1",
            'spi2': "d:\\data\\droughtindices\\npz\\percentiles\\spi2",
            'spi3': "d:\\data\\droughtindices\\npz\\percentiles\\spi3",
            'spi6': "d:\\data\\droughtindices\\npz\\percentiles\\spi6",
            'spei1': "d:\\data\\droughtindices\\npz\\percentiles\\spei1",
            'spei2': "d:\\data\\droughtindices\\npz\\percentiles\\spei2",
            'spei3': "d:\\data\\droughtindices\\npz\\percentiles\\spei3",
            'spei6': "d:\\data\\droughtindices\\npz\\percentiles\\spei6",
            'eddi1': "d:\\data\\droughtindices\\npz\\percentiles\\eddi1",
            'eddi2': "d:\\data\\droughtindices\\npz\\percentiles\\eddi2",
            'eddi3': "d:\\data\\droughtindices\\npz\\percentiles\\eddi3",
            'eddi6': "d:\\data\\droughtindices\\npz\\percentiles\\eddi6"}
rasterpaths = {'noaa': 'D:/data/droughtindices/noaa/nad83/percentiles',
               'pdsi': 'D:/data/droughtindices/pdsi/nad83/percentiles',
               'pdsisc': 'D:/data/droughtindices/pdsisc/nad83/percentiles',
               'pdsiz': 'D:/data/droughtindices/pdsiz/nad83/percentiles',
               'spi1': 'D:/data/droughtindices/spi/nad83/1month/percentiles',
               'spi2': 'D:/data/droughtindices/spi/nad83/2month/percentiles',
               'spi3': 'D:/data/droughtindices/spi/nad83/3month/percentiles',
               'spi6': 'D:/data/droughtindices/spi/nad83/6month/percentiles',
               'spei1': 'D:/data/droughtindices/spei/nad83/1month/percentiles',
               'spei2': 'D:/data/droughtindices/spei/nad83/2month/percentiles',
               'spei3': 'D:/data/droughtindices/spei/nad83/3month/percentiles',
               'spei6': 'D:/data/droughtindices/spei/nad83/6month/percentiles',
               'eddi1': 'D:/data/droughtindices/eddi/nad83/1month/percentiles',
               'eddi2': 'D:/data/droughtindices/eddi/nad83/2month/percentiles',
               'eddi3': 'D:/data/droughtindices/eddi/nad83/3month/percentiles',
               'eddi6': 'D:/data/droughtindices/eddi/nad83/6month/percentiles'}

savenames = ['noaa', 'pdsi', 'pdsisc', 'pdsiz', 'spi1', 'spi2', 'spi3', 'spi6',
             'spei1', 'spei2', 'spei3', 'spei6', 'eddi1', 'eddi2', 'eddi3',
             'eddi6']

for index in tqdm(savenames, position=0):
    indexlist = npzIn(npzpaths[index] + "_arrays.npz",
                      npzpaths[index] + "_dates.npz")
    toRasters(indexlist, rasterpaths[index], geom, proj)
