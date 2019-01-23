# -*- coding: utf-8 -*-
"""
Learning Memoization with this:
    
https://www.python-course.eu/python3_memoization.php

Created on Sun Jan 20 12:14:42 2019

@author: User
"""
import json
import os
from tqdm import tqdm
import time
import sys

home_path = 'z:/Sync'
data_path = 'd:/'
os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
startyear = 1948
sys.path.insert(0, "scripts")
from Index_Map import Index_Maps

# Sample Data
maps = Index_Maps()
data = maps.meanOriginal()


# Recursive function
fib_memo = {}
def fib(n):
    if n < 2: return 1
    if not n in fib_memo.keys():
        fib_memo[n] = fib(n-1) + fib(n-2)
    return fib_memo[n]

# With our function
cache = {}
def makeMap(signal):
    '''
    To choose which function to return from Index_Maps
    '''
    start = time.time()
    [time_range, function, colorscale, reverse, choice] = signal
    maps = Index_Maps(time_range, colorscale, reverse, choice)
    key = json.dumps(signal)    
    if not key in cache.keys():
        if function == "mean_original":
            data = maps.meanOriginal()
        if function == "omax":
            data = maps.maxOriginal()
        if function == "omin":
            data = maps.minOriginal()
        if function == "mean_perc":
            data = maps.meanPercentile()
        if function == "max":
            data = maps.maxPercentile()
        if function == "min":
            data = maps.minPercentile()
        if function == "ocv":
            data = maps.coefficientVariation()
    
        cache[key] = data

    end = time.time()
    print("{} seconds".format(round(end - start, 2)))
    return cache[key]

# testing 
signal1 = [[[2000, 2017], [1, 12]], 'mean_original', 'Viridis', 'no', 'pdsi']
signal2 = [[[1948, 2017], [1, 12]], 'mean_original', 'Viridis', 'yes', 'pdsi']
signal3 = [[[2000, 2017], [1, 12]], 'mean_original', 'Viridis', 'no', 'spei3']

# And this totally works
data1 = makeMap(signal1)
data2 = makeMap(signal2)
data3 = makeMap(signal3)

# Now to get rid of it
len(cache)
cache.pop(json.dumps(signal1))
len(cache)


# In[] Can also define this using decorators
class Cacher:
    def memoize(function):
        cache = {}
        def cacher(x):
            key = json.dumps(x)
            if key not in cache.keys():
                cache[key] = function(x)
            return cache[key]
        return cacher


@Cacher.memoize
def makeMap(signal):
    '''
    To choose which function to return from Index_Maps
    '''
    start = time.time()

    [time_range, function, colorscale, reverse, choice] = signal

    maps = Index_Maps(time_range, colorscale, reverse, choice)

    if function == "mean_original":
        data = maps.meanOriginal()
    if function == "omax":
        data = maps.maxOriginal()
    if function == "omin":
        data = maps.minOriginal()
    if function == "mean_perc":
        data = maps.meanPercentile()
    if function == "max":
        data = maps.maxPercentile()
    if function == "min":
        data = maps.minPercentile()
    if function == "ocv":
        data = maps.coefficientVariation()

    end = time.time()
    print("{} seconds".format(round(end - start, 2)))

    return data

# testing 
signal1 = [[[2000, 2017], [1, 12]], 'mean_original', 'Viridis', 'no', 'pdsi']
signal2 = [[[1948, 2017], [1, 12]], 'mean_original', 'Viridis', 'yes', 'pdsi']
signal3 = [[[2000, 2017], [1, 12]], 'mean_original', 'Viridis', 'no', 'spei3']

# And this totally works
data1 = makeMap(signal1)
data2 = makeMap(signal2)
data3 = makeMap(signal3)


# In[] Now to get rid of it here is a little trickier...we need to be able to
# access the cache...
# Generate key
# def getKey(function, *args, **kwargs):
#     fid = id(function)
#     args = [id(arg) for arg in args]
#     print(args)
#     if kwargs:
#         kwarglist = [id(value) for key, value in kwargs.items()]
#         identifier = json.dumps([fid, args, kwarglist])
#     else:
#         identifier = json.dumps([fid, args])
#     key = identifier.replace("[", "").replace("]", "")
#     print("Key: " + key)
#     return key


# I could just do this, surely if there is a problem it will tell me at some 
# point. 
# In the future consider solution #4 here:
# https://stackoverflow.com/questions/10879137/how-can-i-memoize-a-class-instantiation-in-python


cache = {}
def memoize(function, *args, **kwargs):
    def cacher(x):
        key = json.dumps(x)
        if key not in cache.keys():
            cache[key] = function(x)
        return cache[key]
    return cacher

@memoize
def makeMap(signal):
    '''
    To choose which function to return from Index_Maps
    '''
    start = time.time()

    [time_range, function, colorscale, reverse, choice] = signal

    maps = Index_Maps(time_range, colorscale, reverse, choice)

    if function == "mean_original":
        data = maps.meanOriginal()
    if function == "omax":
        data = maps.maxOriginal()
    if function == "omin":
        data = maps.minOriginal()
    if function == "mean_perc":
        data = maps.meanPercentile()
    if function == "max":
        data = maps.maxPercentile()
    if function == "min":
        data = maps.minPercentile()
    if function == "ocv":
        data = maps.coefficientVariation()

    end = time.time()
    print("{} seconds".format(round(end - start, 2)))

    return data


# And this works, too?
data1 = makeMap(signal1)
data2 = makeMap(signal2)
data3 = makeMap(signal3)

# And to depopulate
cache.pop(json.dumps(signal1))


