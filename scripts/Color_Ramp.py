# -*- coding: utf-8 -*-
"""
Created on Sat Jan  5 11:01:14 2019

@author: User
"""

# In[] Functions and Libraries
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors
import os
import scipy as spy

homepath = "C:/users/user/github/"
os.chdir(homepath + "PRF-ALTIND")
from functions import npzIn
from functions import indexHist

os.chdir("D:/data/droughtindices/npz/")

# In[]
# I am looking to recreate the red, yellow, green, blue color ramp from ArcMap
x, y, c = zip(*np.random.rand(30, 3)*4-2)
colorList = matplotlib.colors.LinearSegmentedColormap.from_list
cmap = colorList("", ["#C4563B", "#FEFC01", "#05D219", "#0B2C7A"])

norm = plt.Normalize(0, 1)
plt.scatter(x, y, c=c, cmap=cmap, norm=norm)
plt.colorbar()
plt.show()

# In[] How to create similar color-scales for different distributions?
indexlist = npzIn('noaa_arrays.npz', 'noaa_dates.npz')
arrays = [a[1] for a in indexlist]
indexHist(arrays)
