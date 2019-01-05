# -*- coding: utf-8 -*-
"""
Created on Sat Jan  5 11:01:14 2019

@author: User
"""

# In[] Functions and Libraries
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors


# In[]
# I am looking to recreate the red, yellow, green, blue color ramp from ArcMap
x,y,c = zip(*np.random.rand(30,3)*4-2)

cmap = matplotlib.colors.LinearSegmentedColormap.from_list("",
                                                           ["red","yellow",
                                                            "green", "blue"])

norm=plt.Normalize(-2,2)
plt.scatter(x,y,c=c, cmap=cmap, norm=norm)
plt.colorbar()
plt.show()

