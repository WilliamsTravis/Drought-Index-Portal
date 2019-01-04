# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 16:14:42 2017

@author: Travis
"""
import time,urllib, linecache, sys,tqdm
import pickle, os
#from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno,
          line.strip(), exc_obj))
    
    
website = 'https://wrcc.dri.edu/wwdt/data/PRISM/pdsi/'
path_to_chromedriver = "C:\\drivers\\chrome\\chromedriver"
driver = webdriver.Chrome(executable_path = path_to_chromedriver)
driver.set_window_position(975,0)
driver.get(website)
driver.implicitly_wait(30)   

# For spei and spi the links we want are separated into different pages, 
# so we need two sets of links
# spi 
indexes = ["spi"+str(i)+"/" for  i in range(1,13)]
alllinks = [website+indexes[i] for i in range(0,12)]
for i in range(0,len(alllinks)):
#    driver.get(alllinks[i])
#    index = indexes[i]
    links = driver.find_elements_by_partial_link_text('nc')
    urls = [website+index+link.text for link in links if link.text[-2:]=="nc"]
#    urlshort = urls[1264:-10]
    for url in urls:
        driver.get(url) 
        print(url)
#        time.sleep(2)
    driver.get(website)
    
indexes = ["spi"+str(i)+"/" for  i in range(1,13)]
alllinks = [website+indexes[i] for i in range(0,12)]
for i in range(0,len(alllinks)):
    driver.get(alllinks[i])
    index = indexes[i]
    links = driver.find_elements_by_partial_link_text('1998')
    urls = [website+index+link.text for link in links if link.text[-2:]=="nc"]
#    urlshort = urls[1264:-10]
    for url in urls:
        driver.get(url) 
        print(url)
#        time.sleep(2)
    driver.get(website)    

# pdsi 
links = driver.find_elements_by_partial_link_text('nc')
urls = [website+link.text for link in links if len(link.text) > 20]
urls = urls[:-2]
for url in urls:
    driver.get(url) 
    print(url)
    time.sleep(2)

