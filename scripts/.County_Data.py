# -*- coding: utf-8 -*-
"""
Created on Wed Feb 20 13:19:33 2019

@author: User
"""


import pandas as pd

# building one master counties data set!
# what we have
df = pd.read_csv('data/counties2.csv')
 # 'grid', 'county', 'state', 'place', 'gradient



# We need county and state fips too
fips = pd.read_csv('data/US_FIPS_Codes.csv',skiprows=1)
fips['FIPS County'] = fips['FIPS County'].apply(lambda x: "{:03d}".format(x))
fips['FIPS State'] = fips['FIPS State'].apply(lambda x: "{:02d}".format(x))
fips['FIPS County'] = fips['FIPS State'] + fips['FIPS County']
fips['place'] = fips['County Name'] + ' County, ' + fips['State']
fips.to_csv('data/fips.csv')

# The main table doesn't have fips, but it has county and state abbrs
states = pd.read_table('data/state_fips.txt', sep='|')
fips = pd.merge(fips, states, left_on='State', right_on='STATE_NAME')
states = states[['STUSAB', 'STATE_NAME']]
fips['place'] = fips['County Name'] + ' County, ' + fips['STUSAB']

df2 = pd.merge(df, fips, on='place', how='left')
df2.to_csv('data/counties3.csv', index=False)
