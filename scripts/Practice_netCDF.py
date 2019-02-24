# -*- coding: utf-8 -*-
"""
Working with netcdfs

Created on Sun Feb 24 13:05:22 2019

@author: User
"""

from bs4 import BeautifulSoup
from collections import OrderedDict
import datetime as dt
from osgeo import gdal
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import requests
import sys
from progressbar import progressbar as pb
from urllib.error import HTTPError, URLError
import urllib
from socket import timeout
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

from functions import Index_Maps, readRaster, percentileArrays, im
# gdal.PushErrorHandler('CPLQuietErrorHandler')

