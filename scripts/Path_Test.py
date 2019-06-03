#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun  2 19:47:43 2019

@author: travis
"""
import os
import sys

# Check if we are working in Windows or Linux to find the data
if sys.platform == 'win32':
    data_path = 'f:/'
elif 'travis' in os.getenv('HOME'):
    data_path = '/media/travis/My Passport/'
else:
    data_path = '/root/Sync/'

print("\n" + data_path + "\n")