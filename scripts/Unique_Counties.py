# -*- coding: utf-8 -*-
"""
Created on Wed Mar 27 14:17:44 2019

@author: User
"""
counties_df = pd.read_csv('data/tables/unique_counties.csv')  # <-------------- Rebuild this to have a FIPS code as its value, same method as states
fips = pd.read_csv('data/tables/US_FIPS_Codes.csv', skiprows=1)
states = pd.read_table('data/tables/state_fips.txt', sep='|')
fips2 = fips.merge(states, left_on='State', right_on='STATE_NAME')
fips2['place'] = fips2['County Name'] + ' County, ' + fips2['STUSAB']
def frmt(number):
    return '{:03d}'.format(number)
fips2['fips'] = fips2['FIPS State'].map(frmt) + fips2['FIPS County'].map(frmt)
fips2['fips'] = fips2['fips'].astype(float)
fips2 = fips2[['place', 'fips']]

counties_df = counties_df.merge(fips2, on='place')
