# -*- coding: utf-8 -*-
"""
An Application to visualize time series of drought indices.
Things to do:
    1) Much of the functionality of this was added in a rather ad hoc manner
       for time's sake. It's time to go through and modularize everything.
            a) Read this: "https://dev.to/ice_lenor/modularization-and-
                           dependency-management-three-steps-to-better-code":
            b) Also this: "https://docs.python-guide.org/writing/structure/"
            d) Within each function, determine the selection type (point,
               multi-point, county, state, shapefile), rather than using if
               statements.
    2) Also, less important, the styling needs help on two fronts:
            a) Move all styling to the css file for consistency and readability
            b) Learn to read the css locally. Periodically, depending on the
               browser and perhaps the position of the moon, the css fails to
               load completely. It is possible that reading it directly from a
               local repository will fix this issue.
    3) The correlation function is new and simple. It would be good to talk
       with the team about what would be most useful. I think it would be neat
       to express the time series as ranges of covariance from where a point is
       clicked. That would mean fitting a model of semivariance to each
       selection in projected space and would likely require more computing
       than any other part of the app, but it could be done. If there are non-
       parametric ways of doing this we could skip the model fitting step. Or,
       if one model does generally well with each index and location we could
       use established shapes. We could just use the average distance to
       a specific threshold correlation coefficient (eg. 500 km to 0.5). We
       are, however, just now learning of non-linear dependence...this might be
       a future addition.
    4) Long-term goal. Retrieve data from a data base. Learning to do this with
       PostgreSQL was actually the main reason why I created the
       "Ubuntu-Practice-Machine" to begin with. I'd had trouble storing NetCDF
       files initially and decided it would be more useful to make something
       that works as quickly as possible. I am new to this sort of thing, but
       I think that this would be useful in many ways beyond learning how to
       manage geographic data in a data base.
             a) Spinning up a new instance would not require downloading the
                data a new each time? How would connecting remotely work? At
                the very least, it would not require all of the
                transformations.
             b) It is possible that spatial querying could be done faster
                through PostGIS?
             c) It would be more organized and possibly simpler to share data
                with a GIS.
    5) Fully integrate DASK. It turns out that xarray already uses dask and
       was keeping much of the data on disk. This helps to avoid memory
       errors and improve speed. With the area calculations it worsens
       it significantlym though... Is this an inevitable tradeoff?
    6) Describe new climate data sets:
        http://www.prism.oregonstate.edu/documents/PRISM_datasets_aug2013.pdf
    7) Consolidate all of the download scripts into one. Also, incorporate the
       scale setting script into this.
    8) Reconsider the property decorator for certain attributes in
       Index_Maps(). It works to automatically update these attributes, but
       does not allow us to access them.
    9) I would like to see the GRACE soil moisture models in here.
    10) There are no preset categories for severity in the climate variables.
    11) There are a few sequences of button clicks that resets the map layout,
        though it is rare to see so watch out for that and maybe we can figure
        what does that.

Created on April 15th 2019
@author: Travis Williams - Earth Lab of the Universty of Colorado Boulder
         Travis.Williams@colorado.edu
"""
# Functions and Libraries
#import netCDF4  # For certain xarray issues, it helps to explicitly load this
import base64
import copy
from collections import OrderedDict
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import datetime as dt
import fiona
from flask_caching import Cache
import gc
import geopandas as gpd
import json
import numpy as np
import os
from osgeo import gdal, osr
import pandas as pd
import psutil
import tempfile
import urllib
import warnings
import xarray as xr
from functions import Admin_Elements, Index_Maps, Location_Builder
from functions import shapeReproject, unit_map

# What to do with the mean of empty slice warning?
warnings.filterwarnings("ignore")

# In case the data needs to be stored elsewhere
data_path = ''

# In[] Default Values
# For testing
source_signal = [[[2000, 2017], [1, 12], [5, 6, 7, 8]], 'Viridis', 'no']
source_choice = 'pdsi'
source_function = 'pmean'
source_location = ['grids', '[10, 11, 11, 11, 12, 12, 12, 12]',
                   '[243, 242, 243, 244, 241, 242, 243, 244]',
                   'Aroostook County, ME to Aroostook County, ME', 2]

# Initializing Values
default_function = 'pmean'
default_function_type = 'perc'
default_sample = 'spi1'
default_1 = 'pdsi'
default_2 = 'spi1'
default_date = '2000 - 2019'
default_basemap = 'dark'
default_location = '[["all", "y", "x", "Contiguous United States", 0], 9, "None"]'
default_years = [2000, 2019]
default_extent = {'mapbox.center': {'lon': -92, 'lat': 40},
                  'mapbox.zoom': 2.2, 'mapbox.bearing': 0, 'mapbox.pitch': 20}

# Default click before the first click for any map (might not be necessary)
default_click = {'points': [{'curveNumber': 0, 'lat': 40.0, 'lon': -105.75,
                             'marker.color': 0, 'pointIndex': 0,
                             'pointNumber': 0, 'text': 'Boulder County, CO'}]}

# Default for click store (includes an index for most recent click)
default_clicks = [list(np.repeat(default_click.copy(), 4)), 0]
default_clicks = json.dumps(default_clicks)

# For scaling
ranges = pd.read_csv('data/tables/index_ranges.csv')

# In[] The DASH application and server
app = dash.Dash(__name__)

# Go to stylesheet, styled after a DASH example (how to serve locally?)  # <--- Check out criddyp's response about a third of the way down here <https://community.plot.ly/t/serve-locally-option-with-additional-scripts-and-style-sheets/6974/6>
#app.css.append_css({'external_url':
#                    'https://codepen.io/williamstravis/pen/maxwvK.css'})
## For the Loading screen
#app.css.append_css({"external_url":
#                    "https://codepen.io/williamstravis/pen/EGrWde.css"})
# app.scripts.config.serve_locally = True

# Attempting local css
app.css.append_css({"external_url":  "static/stylesheet.css"})
app.scripts.config.serve_locally = True

# Create Server Object
server = app.server

# Disable exceptions (attempt to speed things up)
app.config['suppress_callback_exceptions'] = True

# Create a simple file storeage cache, holds unique outputs of Index_Maps
cache = Cache(config={'CACHE_TYPE': 'filesystem',
                      'CACHE_DIR': 'data/cache',
                      'CACHE_THRESHOLD': 2})

# Create a separate cache to hold drought area data for toggling DSCI on/off
cache2 = Cache(config={'CACHE_TYPE': 'filesystem',
                       'CACHE_DIR': 'data/cache2',
                       'CACHE_THRESHOLD': 2})
cache.init_app(server)
cache2.init_app(server)

# In[] Interface Options
# Drought Index Options
indices = [{'label': 'PDSI', 'value': 'pdsi'},
           {'label': 'PDSI-SC', 'value': 'pdsisc'},
           {'label': 'Palmer Z Index', 'value': 'pdsiz'},
           {'label': 'SPI-1', 'value': 'spi1'},
           {'label': 'SPI-2', 'value': 'spi2'},
           {'label': 'SPI-3', 'value': 'spi3'},
           {'label': 'SPI-4', 'value': 'spi4'},
           {'label': 'SPI-5', 'value': 'spi5'},
           {'label': 'SPI-6', 'value': 'spi6'},
           {'label': 'SPI-7', 'value': 'spi7'},
           {'label': 'SPI-8', 'value': 'spi8'},
           {'label': 'SPI-9', 'value': 'spi9'},
           {'label': 'SPI-10', 'value': 'spi10'},
           {'label': 'SPI-11', 'value': 'spi11'},
           {'label': 'SPI-12', 'value': 'spi12'},
           {'label': 'SPEI-1', 'value': 'spei1'},
           {'label': 'SPEI-2', 'value': 'spei2'},
           {'label': 'SPEI-3', 'value': 'spei3'},
           {'label': 'SPEI-4', 'value': 'spei4'},
           {'label': 'SPEI-5', 'value': 'spei5'},
           {'label': 'SPEI-6', 'value': 'spei6'},
           {'label': 'SPEI-7', 'value': 'spei7'},
           {'label': 'SPEI-8', 'value': 'spei8'},
           {'label': 'SPEI-9', 'value': 'spei9'},
           {'label': 'SPEI-10', 'value': 'spei10'},
           {'label': 'SPEI-11', 'value': 'spei11'},
           {'label': 'SPEI-12', 'value': 'spei12'},
           {'label': 'EDDI-1', 'value': 'eddi1'},
           {'label': 'EDDI-2', 'value': 'eddi2'},
           {'label': 'EDDI-3', 'value': 'eddi3'},
           {'label': 'EDDI-4', 'value': 'eddi4'},
           {'label': 'EDDI-5', 'value': 'eddi5'},
           {'label': 'EDDI-6', 'value': 'eddi6'},
           {'label': 'EDDI-7', 'value': 'eddi7'},
           {'label': 'EDDI-8', 'value': 'eddi8'},
           {'label': 'EDDI-9', 'value': 'eddi9'},
           {'label': 'EDDI-10', 'value': 'eddi10'},
           {'label': 'EDDI-11', 'value': 'eddi11'},
           {'label': 'EDDI-12', 'value': 'eddi12'},
           {'label': 'LERI-1', 'value': 'leri1'},
           {'label': 'LERI-3', 'value': 'leri3'},
           {'label': 'TMIN', 'value': 'tmin'},
           {'label': 'TMAX', 'value': 'tmax'},
           {'label': 'TMEAN', 'value': 'tmean'},
           {'label': 'TDMEAN', 'value': 'tdmean'},
           {'label': 'PPT', 'value': 'ppt'},
           {'label': 'VPDMAX', 'value': 'vpdmax'},
           {'label': 'VPDMIN', 'value': 'vpdmin'},
           {'label': 'VPDMEAN', 'value': 'vpdmean'}]

# Index dropdown labels
indexnames = {'noaa': 'NOAA CPC-Derived Rainfall Index',
              'mdn1': 'Mean Temperature Departure  (1981 - 2010) - 1 month',
              'pdsi': 'Palmer Drought Severity Index',
              'pdsisc': 'Self-Calibrated Palmer Drought Severity Index',
              'pdsiz': 'Palmer Z-Index',
              'spi1': 'Standardized Precipitation Index - 1 month',
              'spi2': 'Standardized Precipitation Index - 2 month',
              'spi3': 'Standardized Precipitation Index - 3 month',
              'spi4': 'Standardized Precipitation Index - 4 month',
              'spi5': 'Standardized Precipitation Index - 5 month',
              'spi6': 'Standardized Precipitation Index - 6 month',
              'spi7': 'Standardized Precipitation Index - 7 month',
              'spi8': 'Standardized Precipitation Index - 8 month',
              'spi9': 'Standardized Precipitation Index - 9 month',
              'spi10': 'Standardized Precipitation Index - 10 month',
              'spi11': 'Standardized Precipitation Index - 11 month',
              'spi12': 'Standardized Precipitation Index - 12 month',
              'spei1': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 1 month',
              'spei2': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 2 month',
              'spei3': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 3 month',
              'spei4': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 4 month',
              'spei5': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 5 month',
              'spei6': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 6 month',
              'spei7': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 7 month',
              'spei8': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 8 month',
              'spei9': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 9 month',
              'spei10': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 10 month',
              'spei11': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 11 month',
              'spei12': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 12 month',
              'eddi1': 'Evaporative Demand Drought Index - 1 month',
              'eddi2': 'Evaporative Demand Drought Index - 2 month',
              'eddi3': 'Evaporative Demand Drought Index - 3 month',
              'eddi4': 'Evaporative Demand Drought Index - 4 month',
              'eddi5': 'Evaporative Demand Drought Index - 5 month',
              'eddi6': 'Evaporative Demand Drought Index - 6 month',
              'eddi7': 'Evaporative Demand Drought Index - 7 month',
              'eddi8': 'Evaporative Demand Drought Index - 8 month',
              'eddi9': 'Evaporative Demand Drought Index - 9 month',
              'eddi10': 'Evaporative Demand Drought Index - 10 month',
              'eddi11': 'Evaporative Demand Drought Index - 11 month',
              'eddi12': 'Evaporative Demand Drought Index - 12 month',
              'leri1': 'Landscape Evaporative Response Index - 1 month',
              'leri3': 'Landscape Evaporative Response Index - 3 month',
              'tmin': 'Average Daily Minimum Temperature (°C)',
              'tmax': 'Average Daily Maximum Temperature (°C)',
              'tmean': 'Mean Temperature (°C)',
              'tdmean': 'Mean Dew Point Temperature (°C)',
              'ppt': 'Average Precipitation (mm)',
              'vpdmax': 'Maximum Vapor Pressure Deficit (hPa)' ,
              'vpdmin': 'Minimum Vapor Pressure Deficit (hPa)',
              'vpdmean': 'Mean Vapor Pressure Deficit (hPa)'}

# Function options
function_options_perc = [{'label': 'Mean', 'value': 'pmean'},
                         {'label': 'Maximum', 'value': 'pmax'},
                         {'label': 'Minimum', 'value': 'pmin'},
                         {'label': 'Correlation', 'value': 'pcorr'}]
function_options_orig = [{'label': 'Mean', 'value': 'omean'},
                         {'label': 'Maximum', 'value': 'omax'},
                         {'label': 'Minimum', 'value': 'omin'},
                         {'label': 'Drought Severity Area', 'value':'oarea'},
                         {'label': 'Correlation', 'value': 'ocorr'}]
function_names = {'pmean': 'Average Percentiles',
                  'pmax': 'Maxmium Percentiles',
                  'pmin': 'Minimum Percentiles',
                  'omean': 'Average Index Values',
                  'omax': 'Maximum Index Values',
                  'omin': 'Minimum Index Values',
                  'oarea': 'Average Index Values',
                  'pcorr': "Pearson's Correlation ",
                  'ocorr': "Pearson's Correlation "}

# Acronym "options"
ams = [{'label': 'PDSI: The Palmer Drought Severity Index (WWDT)', 'value': 0},
       {'label': 'PDSI-Self Calibrated: The Self-Calibrating Palmer Drought ' +
                 'Severity Index (WWDT)', 'value': 1},
       {'label': 'Palmer Z Index: The Palmer Z Index (WWDT)', 'value': 2},
       {'label': 'SPI: The Standardized Precipitation Index - 1 to 12 ' +
                 'months (WWDT)', 'value': 3},
       {'label': 'SPEI: The Standardized Precipitation-Evapotranspiration ' +
                 'Index - 1 to 12 months (WWDT)', 'value': 4},
       {'label': 'EDDI: The Evaporative Demand Drought Index - 1 to 12 ' +
                 'months (PSD)', 'value': 5},
       {'label': 'LERI: The Landscape Evaporative Response Index - 1 or 3 ' +
                 'months (PSD)', 'value': 6},
       {'label': 'TMIN: Average Daily Minimum Temperature ' +
                 '(°C)(PRISM)', 'value': 7},
       {'label': 'TMAX: Average Daily Maximum Temperature ' +
                 '(°C)(PRISM)', 'value': 9},
       {'label': 'TMEAN: Mean Temperature (°C)(PRISM)', 'value': 11},
       {'label': 'TDMEAN: Mean Dew Point Temperature ' +
                 '(°C)(PRISM)', 'value': 14},
       {'label': 'PPT: Average Precipitation (mm)(PRISM)', 'value': 15},
       {'label': 'VPDMAX: Maximum Vapor Pressure Deficit ' +
                 '(hPa)(PRISM)', 'value': 18},
       {'label': 'VPDMIN: Minimum Vapor Pressure Deficit ' +
                 '(hPa)(PRISM)', 'value': 20}]

acronym_text = ("""
INDEX/INDICATOR ACRONYMS


PDSI:            Palmer Drought Severity Index

PDSI-SC:         Self-Calibrating PDSI

Palmer Z Index:  Palmer Z Index

SPI:             Standardized Precipitation Index

SPEI:            Standardized Precip-ET Index

EDDI:            Evaporative Demand Drought Index

LERI:            Landscape Evaporation Response Index

TMIN:            Average Daily Minimum Temp (°C)

TMAX:            Average Daily Maximum Temp (°C)

TMEAN:           Mean Temperature (°C)

TDMEAN:          Mean Dew Point Temperature (°C)

PPT:             Average Precipitation (mm)

VPDMAX:          Max Vapor Pressure Deficit (hPa)

VPDMIN:          Min Vapor Pressure Deficit (hPa)
""")

# County data frame and options
counties_df = pd.read_csv('data/tables/unique_counties.csv')
rows = [r for idx, r in counties_df.iterrows()]
county_options = [{'label': r['place'], 'value': r['fips']} for r in rows]
fips_pos = {county_options[i]['value']: i for i in range(len(county_options))}
label_pos = {county_options[i]['label']: i for i in range(len(county_options))}

# State options
states_df = pd.read_table('data/tables/state_fips.txt', sep='|')
states_df = states_df.sort_values('STUSAB')
nconus = ['AK', 'AS', 'DC', 'GU', 'HI', 'MP', 'PR', 'UM', 'VI']
states_df = states_df[~states_df.STUSAB.isin(nconus)]
rows = [r for idx, r in states_df.iterrows()]
state_options = [{'label': r['STUSAB'], 'value': r['STATE']} for r in rows]
state_options.insert(0, {'label': 'ALL STATES IN CONUS', 'value': 'all'})

# Map type options
maptypes = [{'label': 'Light', 'value': 'light'},
            {'label': 'Dark', 'value': 'dark'},
            {'label': 'Basic', 'value': 'basic'},
            {'label': 'Outdoors', 'value': 'outdoors'},
            {'label': 'Satellite', 'value': 'satellite'},
            {'label': 'Satellite Streets', 'value': 'satellite-streets'}]

# Color scale options
colorscales = ['Default', 'Blackbody', 'Bluered', 'Blues', 'Earth', 'Electric',
               'Greens', 'Greys', 'Hot', 'Jet', 'Picnic', 'Portland',
               'Rainbow', 'RdBu', 'Reds', 'Viridis', 'RdWhBu',
               'RdWhBu (Extreme Scale)', 'RdYlGnBu', 'BrGn']
color_options = [{'label': c, 'value': c} for c in colorscales]

# We need one external colorscale for a hard set drought area chart
RdWhBu = [[0.00, 'rgb(115,0,0)'], [0.10, 'rgb(230,0,0)'],
          [0.20, 'rgb(255,170,0)'], [0.30, 'rgb(252,211,127)'],
          [0.40, 'rgb(255, 255, 0)'], [0.45, 'rgb(255, 255, 255)'],
          [0.55, 'rgb(255, 255, 255)'], [0.60, 'rgb(143, 238, 252)'],
          [0.70, 'rgb(12,164,235)'], [0.80, 'rgb(0,125,255)'],
          [0.90, 'rgb(10,55,166)'], [1.00, 'rgb(5,16,110)']]

# Get time dimensions from the first data set, assuming netcdfs are uniform
with xr.open_dataset(
        os.path.join(data_path,
             'data/droughtindices/netcdfs/' + default_sample + '.nc')) as data:
    min_date = data.time.data[0]
    max_date = data.time.data[-1]
    resolution = data.crs.GeoTransform[1]
max_year = pd.Timestamp(max_date).year
min_year = pd.Timestamp(min_date).year + 5
max_month = pd.Timestamp(max_date).month

# Get spatial dimensions from the sample data set above
admin = Admin_Elements(resolution)
[state_array, county_array, grid, mask,
 source, albers_source, crdict, admin_df] = admin.getElements()  # <----------- remove albers source here (carefully)

# Date options
years = [int(y) for y in range(min_year, max_year + 1)]
months = [int(m) for m in range(1, 13)]
mnths2 = copy.copy(months)
for m in months[:-1]:
    mnths2.append(m + 12)
yearmarks = {y: {'label': y, 'style': {"transform": "rotate(45deg)"}} for
             y in years}
monthmarks = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
              13: 'Nov ', 14: 'Oct ', 15: 'Sep ', 16: 'Aug ', 17: 'Jul ',
              18: 'Jun ', 19: 'May ', 20: 'Apr ', 21: 'Mar ', 22: 'Feb ',
              23: 'Jan '}
monthmarks_full = {1: 'January', 2: 'February', 3: 'March', 4: 'April',
                   5: 'May', 6: 'June', 7: 'July', 8: 'August', 9: 'September',
                   10: 'October', 11: 'November', 12: 'December'}
monthoptions = [{'label': monthmarks[i], 'value': i} for i in range(1, 13)]
months_slanted = {i: {'label': monthmarks[i],
                      'style': {"transform": "rotate(45deg)"}} for i in mnths2}

# Only display every 5 years for space
for y in years:
    if y % 5 != 0:
        yearmarks[y] = ""


# In[] Map Elements
# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')

# Mapbox initial layout
# Check this out! https://paulcbauer.shinyapps.io/plotlylayout/
layout = dict(
    autosize=True,
    height=500,
    font=dict(color='#CCCCCC',
              fontweight='bold'),
    titlefont=dict(color='#CCCCCC',
                   size='20',
                   family='Time New Roman',
                   fontweight='bold'),
    margin=dict(l=55, r=35, b=65, t=90, pad=4),
    hovermode="closest",
    plot_bgcolor="#083C04",
    paper_bgcolor="black",
    legend=dict(font=dict(size=10, fontweight='bold'), orientation='h'),
    title='<b>Index Values/b>',
    mapbox=dict(
        accesstoken=mapbox_access_token,
        style="satellite-streets",
        center=dict(lon=-95.7, lat=37.1),
        zoom=2))


# In[] Temporary CSS Items
tab_height = '25px'
tab_style = {'height': tab_height, 'padding': '0'}
tablet_style = {'line-height': tab_height, 'padding': '0'}
selected_style = {'color': 'black',
                  'box-shadow': '1px 1px 0px white',
                  'border-left': '1px solid lightgrey',
                  'border-right': '1px solid lightgrey',
                  'border-top': '3px solid black'}
unselected_style = {'border-top-left-radius': '3px',
                    'background-color': '#f9f9f9',
                    'padding': '0px 24px',
                    'border-bottom': '1px solid #d6d6d6'}
on_button_style = {'height': '45px',
                   'padding': '9px',
                   'background-color': '#cfb87c',
                   'border-radius': '4px',
                   'font-family': 'Times New Roman',
                   'font-size': '12px',
                   'margin-top': '-5px'}
off_button_style =  {'height': '45px',
                     'padding': '9px',
                     'background-color': '#b09d6d',
                     'border-radius': '4px',
                     'font-family': 'Times New Roman',
                     'font-size': '12px',
                     'margin-top': '-5px'}

# In[]: Application Structure
# Dynamic Elements
def divMaker(id_num, index='noaa'):
    div = html.Div([
         html.Div([

            # Tabs and dropdowns
            html.Div([
              dcc.Tabs(id='choice_tab_{}'.format(id_num),
                       value='index',
                       style=tab_style,
                       children=
                         dcc.Tab(value='index',
                                 label='Drought Index/Indicator',
                                 style=tablet_style,
                                 selected_style=tablet_style)),
              dcc.Dropdown(id='choice_{}'.format(id_num),
                           options=indices,
                           value=index,
                           clearable=False)],
              style={'width': '25%', 'float': 'left'},
              title='Select a drought index for this element'),
            html.Div([
              dcc.Tabs(id='location_tab_{}'.format(id_num),
                       value='county',
                       style=tab_style,
                       children=[
                         dcc.Tab(value='county',
                                 label='County',
                                 style=tablet_style,
                                 selected_style=tablet_style
                                 ),
                         dcc.Tab(value='state',
                                 label='State/States',
                                 style=tablet_style,
                                 selected_style=tablet_style),
                         dcc.Tab(value='shape',
                                 label='Shapefile',
                                 style=tablet_style,
                                 selected_style=tablet_style)
                         ]),
              html.Div(id='location_div_{}'.format(id_num),
                       children=[
                         html.Div(
                           id='county_div_{}'.format(id_num),
                           children=[
                             dcc.Dropdown(
                               id='county_{}'.format(id_num),
                               clearable=False,
                               options=county_options,
                               multi=False,
                               value=24098)]),
                         html.Div(
                           id='state_div_{}'.format(id_num),
                           children=[
                             dcc.Dropdown(
                               id='state_{}'.format(id_num),
                               options=state_options,
                               clearable=False,
                               multi=True,
                               placeholder=('Contiguous United States'),
                               value=None)],
                             style={'display': 'none'}),
                         html.Div(
                           id='shape_div_{}'.format(id_num),
                           title=
                           ('To use a shapefile as an area filter, upload ' +
                            'one as either a zipfile or a grouped selection ' +
                            'that includes the .shp, .shx, .sbn, .sbx, ' +
                            '.proj, and .sbx files. Make sure the file is ' +
                            'unprojected for now.'),
                           children=[
                             dcc.Upload(
                               id='shape_{}'.format(id_num),
                               children=['Drag and drop or ',
                                         html.A('select files')],
                               multiple=True,
                               style={'borderWidth': '2px',
                                      'borderStyle': 'dashed',
                                      'borderRadius': '3px',
                                      'borderColor': '#CCCCCC',
                                      'textAlign': 'center',
                                      'margin': '2px',
                                      'padding': '2px'})])])],
                            style={'width': '60%',
                                   'float': 'left'}),

            html.Div([
              html.Button(
                id='reset_map_{}'.format(id_num),
                children='Reset',
                title=('Remove area filters.'),
                style={'width': '15%',
                       'font-size': '10',
                       'height': '26px',
                       'line-height': '4px',
                       'background-color': '#ffff',
                       'font-family': 'Times New Roman'}),
              html.Button(
                id='update_graphs_{}'.format(id_num),
                children='Update',
                title=('Update the map and  graphs with location choices ' +
                       '(state selections do not update automatically).'),
                style={'width': '15%',
                       'height': '34px',
                       'font-size': '10',
                       'line-height': '5px',
                       'background-color': '#F9F9F9',
                       'font-family': 'Times New Roman'})])],
                className='row'),

            html.Div([
              dcc.Graph(id='map_{}'.format(id_num),
                        config={'showSendToCloud': True})]),
            html.Div([
              dcc.Graph(id='series_{}'.format(id_num),
                        config={'showSendToCloud': True})]),
            html.Div(id='coverage_div_{}'.format(id_num),
                     style={'margin-bottom': '25'}),
            html.Button(
              id='dsci_button_{}'.format(id_num),
              title=
                ('The Drought Severity Coverage Index (DSCI) is a way to ' +
                 'aggregate the five drought severity classifications into a '+
                 'single number. It is calculated by taking the percentage ' +
                 'of an area in each drought category, weighting each by ' +
                 'their severity, and adding them together:                 ' +
                 '%D0*1 + %D1*2 + %D2*3 + %D3*4 + %D4*5'),
              type='button',
              n_clicks=2,
              children=['Show DSCI: Off']),
            html.Hr(),
            html.A('Download Timeseries Data',
                   id='download_link_{}'.format(id_num),
                   download='timeseries_{}.csv'.format(id_num),
                   title=
                     ('This csv includes information for only this element ' +
                      'and is titled "timeseries_{}.csv"'.format(id_num)),
                   href="", target='_blank'),
            html.Div(id='key_{}'.format(id_num),
                     children='{}'.format(id_num),
                     style={'display': 'none'}),
            html.Div(id='label_store_{}'.format(id_num),
                     style={'display': 'none'}),
            html.Div(id='shape_store_{}'.format(id_num),
                     style={'display': 'none'})],
        className='six columns')

    return div

# Navigation bar
navbar = html.Nav(
          className="top-bar fixed",
          children=[

            # Sponser Logos
            html.Div([
              html.A(
                html.Img(
                  src=("/static/earthlab.png"),
                  className='one columns',
                  style={'height': '40',
                         'width': '130',
                         'float': 'right',
                         'position': 'static'}),
                  href="https://www.colorado.edu/earthlab/",
                  target="_blank"),
              html.A(
                html.Img(
                  src=('/static/wwa_logo2015.png'),
                  className='one columns',
                  style={'height': '40',
                         'width': '130',
                         'float': 'right',
                         'position': 'static'}),
                  href="http://wwa.colorado.edu/",
                  target="_blank"),
              html.A(
                html.Img(
                  src=("/static/nidis.png"),
                  className='one columns',
                  style={'height': '40',
                         'width': '170',
                         'float': 'right',
                         'position': 'relative'}),
                  href="https://www.drought.gov/drought/",
                  target="_blank"),
              html.A(
                html.Img(
                  src=("/static/cires.png"),
                  className='one columns',
                  style={'height': '40',
                         'width': '80',
                         'float': 'right',
                         'position': 'relative',
                         'margin-right': '20'}),
                  href="https://cires.colorado.edu/",
                  target="_blank"),
              html.A(
                html.Img(
                   src=("/static/culogo.png"),
                  className='one columns',
                  style={'height': '40',
                         'width': '50',
                         'float': 'right',
                         'position': 'relative',
                         'margin-right': '20',
                         'border-bottom-left-radius': '3px'}),
                  href="https://www.colorado.edu/",
                  target="_blank")],
              style={'background-color': 'white',
                     'width': '600px',
                     'position': 'center',
                     'float': 'right',
                     'margin-right': '-3px',
                     'margin-top': '-5px',
                     'border': '3px solid #cfb87c',
                     'border-radius': '5px'},
              className='row'),
             # End Sponser Logos

        # Acronym Button
        html.Button(
          children="ACRONYMS (HOVER)",
          type='button',
          title=acronym_text,
          style={'height': '45px',
                 'padding': '9px',
                 'background-color': '#cfb87c',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman',
                 'font-size': '12px',
                 'margin-top': '-5px',
                 'float': 'left',
                 'margin-left': '-5px'}),
          # End Acronym Button


          # Toggle Buttons
          html.Div([
            html.Button(id='toggle_options',
                        children='Toggle Options: Off',
                        n_clicks=1,
                        type='button',
                        title=('Display/hide options that ' +
                               'apply to each map below.'),
                        style={'display': 'none'}),
            html.Button(id="desc_button",
                        children='Project Description: Off',
                        title=('Display/hide a description of ' +
                               'the application with instructions.'),
                        style={'display': 'none'}),
            html.Button(id="click_sync",
                        children='Location Syncing: On',
                        title=('Sync/unsync the location ' +
                               'of the time series between each map.'),
                        style={'display': 'none'}),
            html.Button(id="year_sync",
                        children='Year Syncing: On',
                        title=('Sync/unsync the years ' +
                               'of the time series between each map.'),
                        style={'display': 'none'})
                        ],
            style={'float': 'left',
                   'margin-left': '15px'})],
          style={'position': 'fixed','top': '0px', 'left': '0px',
                 'background-color': 'black', 'height': '50px',
                 'width': '100%', 'zIndex': '9999',
                 'border-bottom': '10px solid #cfb87c'})
          # End Toggle Buttons

# Static Elements
body = html.Div([

      # Title
      html.Div([
        html.H1('Drought Index Portal (DrIP)'),
          html.Hr()],
            className='twelve columns',
            style={'font-weight': 'bolder',
                   'text-align': 'center',
                   'font-size': '50px',
                   'font-family': 'Times New Roman',
                   'margin-top': '100'}),
            # End Title

     # Description
     html.Div([
       html.Div([
         dcc.Markdown(id='description')],
                      style={'text-align':'center',
                             'width':'70%',
                             'margin':'0px auto'}),
         html.Hr(style={'margin-bottom': '1px'})],
         style={'text-align':'center',
                'margin': '0 auto',
                'width': '100%'}),
         # End Description

     # Options
     html.Div(id='options',
              children=[

                # Year Slider
                html.Div([
                  html.H3(id='date_range',
                          children=['Date Range']),
                  html.Div([
                    dcc.RangeSlider(id='year_slider',
                                    value=default_years,
                                    min=min_year,
                                    max=max_year,
                                    updatemode='drag',
                                    marks=yearmarks)],
                    style={'margin-top': '0', 'margin-bottom': '80'}),
                  html.Div(id='year_div2',
                    children=[
                      html.H3(id='date_range2', children='Date Range #2'),
                      dcc.RangeSlider(id='year_slider2',
                                      value=default_years,
                                      min=min_year,
                                      max=max_year,
                                      updatemode='drag',
                                      marks=yearmarks)],
                    style={'display': 'none',
                           'margin-top': '0', 'margin-bottom': '80'})]),
                    # End Year Slider

                # Month Options
                html.Div(
                  children=[
                          html.Div([
                             html.H5('Start and End Months'),
                             dcc.RangeSlider(id='month_slider',
                                             value=[1, 12],
                                             marks=months_slanted,
                                             min=1,
                                             max=23,
                                             updatemode='drag')],
                             className='six columns',
                             title=('Choose the first month of the first ' +
                                    'year and last month of the last year ' +
                                    'of the study period.')),
                          html.Div(
                            children=[
                              html.H5('Included Months'),
                              dcc.Checklist(
                                className='check_blue',
                                id='month',
                                options=monthoptions,
                                values=list(range(1, 13)),
                                labelStyle={'display': 'inline-block'}),
                              html.Button(id='all_months', type='button',
                                          children='All',
                                          style={'height': '25px',
                                                 'line-height': '25px'}),
                              html.Button(id='no_months', type='button',
                                          children='None',
                                          style={'height': '25px',
                                                 'line-height': '25px'})],
                            className='five columns',
                            title=('Choose which months of the year to ' +
                                   'be included.'))],
                        className='row'),
                        # End Month Options

                # Rendering Options
                html.Div(id='options_div',
                         children=[

                           # Maptype
                           html.Div([
                             html.H3("Map Type"),
                             dcc.Dropdown(id="map_type",
                                          value=default_basemap,
                                          options=maptypes)],
                             className='two columns'),
                             # End Maptype

                           # Functions
                           html.Div([
                             html.H3("Function"),
                             dcc.Tabs(
                               id='function_type',
                               value=default_function_type,
                               style=tab_style,
                               children=[
                                 dcc.Tab(label='Index Values',
                                         value='index',
                                         style=tablet_style,
                                         selected_style=tablet_style),
                                 dcc.Tab(label='Percentiles',
                                         value='perc',
                                         style=tablet_style,
                                         selected_style=tablet_style)]),
                             dcc.Dropdown(id='function_choice',
                                          options=function_options_perc,
                                          value=default_function)],
                             className='three columns'),
                             # End Functions

                           # Color Scales
                           html.Div([
                             html.H3('Color Gradient'),
                             dcc.Tabs(
                               id='reverse',
                               value='no',
                               style=tab_style,
                               children=[
                                 dcc.Tab(value='no',
                                         label="Not Reversed",
                                         style=tab_style,
                                         selected_style=tablet_style),
                                 dcc.Tab(value='yes',
                                         label='Reversed',
                                         style=tab_style,
                                         selected_style=tablet_style)]),
                             dcc.Dropdown(id='colors',
                                          options=color_options,
                                          value='Default')],
                             className='three columns')],
                        # End Color Scales

               style={'margin-bottom': '50',
                      'margin-top': '50',
                      'text-align': 'left'})],
               className='row'),
               # End Options

       # Submission Button
       html.Div([
         html.Button(id='submit',
                     title=('Submit the option settings ' +
                            'above and update the graphs below.'),
                     children='Submit Options',
                     type='button',
                     style={'background-color': '#C7D4EA',
                            'border-radius': '2px',
                            'font-family': 'Times New Roman',
                            'margin-top': '100px',
                            'margin-bottom': '35px'})],
         style={'text-align': 'center'}),
         # End Submission Button

       # Break line
       html.Hr(style={'margin-top': '1px'}),

       # The Map divs
       html.Div([divMaker(1, default_1), divMaker(2, default_2)],
                className='row'),
                # End Map Divs

       # Signals
       html.Div(id='signal', style={'display': 'none'}),
       html.Div(id='date_print', children=default_date,
                style={'display': 'none'}),
       html.Div(id='date_print2', children=default_date,
                style={'display': 'none'}),
       html.Div(id='location_store_1', children=default_location,
                style={'display': 'none'}),
       html.Div(id='location_store_2', children=default_location,
                style={'display': 'none'}),
       html.Div(id='choice_store', style={'display': 'none'}),
       html.Div(id='area_store_1', children='[0, 0]',
                style={'display': 'none'}),
       html.Div(id='area_store_2', children='[0, 0]',
                style={'display': 'none'})
                # End Signals

       ], className='ten columns offset-by-one')
       # End Static Elements

app.layout = html.Div([navbar, body])

# In[]: App Callbacks
# For singular elements
@app.callback([Output('date_range', 'children'),
               Output('date_print', 'children'),
               Output('date_range2', 'children'),
               Output('date_print2', 'children')],
              [Input('year_slider', 'value'),
               Input('year_slider2', 'value'),
               Input('month_slider', 'value'),
               Input('month', 'values'),
               Input('year_sync', 'n_clicks')])
def adjustDatePrint(year_range,year_range2, month_range, months, sync):
    '''
    If users select one year, only print it once
    '''
    # If not syncing, these need numbers
    if not sync:
        sync = 0
    if sync % 2 == 0:
        number = ""
    else:
        number = " #1"

    # Don't print start and end months if full year is chosen
    month_range = [int(month_range[0]), int(month_range[1])]
    month_range = [monthmarks[m] for m in month_range]
    if month_range[0] == 'Jan' and month_range[1] == 'Dec':
        mrs = ['', '']
        mjoin = ''
    else:
        mrs = [month_range[0] + ' ', month_range[1] + ' ']
        mjoin = ' - '

    # Don't print months included if all are included
    if len(months) == 12:
        month_incl_print = ""
    else:
        if months[0]:
            month_incl_print = "".join([monthmarks[a][0].upper() for
                                        a in months])
            month_incl_print = ' (' + month_incl_print + ')'
        else:
            month_incl_print = ''

    # Year slider #1: If a single year do this
    if year_range[0] == year_range[1]:
        string = str(year_range[0])
        if mrs[0] == mrs[1]:
            string = mrs[0] + str(year_range[0])
        else:
            string = mrs[0] + mjoin + mrs[1] + str(year_range[0])
    else:
        string = (mrs[0] + str(year_range[0]) + ' - ' + mrs[1] +
                  str(year_range[1]))

    # Year slider #2: If a single year do this
    if year_range2[0] == year_range2[1]:
        string2 = str(year_range2[0])
        if mrs[0] == mrs[1]:
            string2 = mrs[0] + str(year_range2[0])
        else:
            string2 = mrs[0] + mjoin + mrs[1] + str(year_range2[0])
    else:
        string2 = (mrs[0] + str(year_range2[0]) + ' - ' + mrs[1] +
                  str(year_range2[1]))

    # And now add the month printouts
    string = string + month_incl_print
    string2 = string2 + month_incl_print
    full = 'Date Range' + number + ':  ' + string
    full2 = 'Date Range #2:  ' + string2

    return full, string, full2, string2


@app.callback([Output('function_choice', 'options'),
               Output('function_choice', 'value')],
              [Input('function_type', 'value')])
def optionsFunctions(function_type):
    '''
    Use the Percentile/Index tab to decide which functions options to
    display.
    '''
    if function_type == 'perc':
        return function_options_perc, 'pmean'
    else:
        return function_options_orig, 'omean'


@app.callback([Output('description', 'children'),
               Output('desc_button', 'style'),
               Output('desc_button', 'children')],
              [Input('desc_button', 'n_clicks')])
def toggleDescription(click):
    '''
    Toggle description on/off
    '''
    if not click:
        click = 0
    if click % 2 == 0:
        desc_children = ""
        style = off_button_style
        button_children = "Description: Off"

    else:
        desc_children = open('data/tables/description.txt').read()  # <-------- It makes no sense that the description doc is in the tables folder
        style = on_button_style
        button_children = "Description: On"

    return desc_children, style, button_children


@cache.memoize()
def retrieveData(signal, function, choice, location):
    '''
    This takes the user defined signal and uses the Index_Map class to filter'
    by the selected dates and return the singular map, the 3d timeseries array,
    and the colorscale.

    sample arguments:
        signal = [[[2000, 2017], [1, 12], [ 4, 5, 6, 7]], 'Viridis', 'no']
        choice = 'pdsi'
        function = 'omean'
        location = ["all", "y", "x", "Contiguous United States", 0]
    '''

    # Retrieve signal elements
    time_data = signal[0]
    colorscale = signal[1]

    # Determine the choice_type based on function
    choice_types = {'omean': 'original',
                    'omin': 'original',
                    'omax': 'original',
                    'pmean': 'percentile',
                    'pmin': 'percentile',
                    'pmax': 'percentile',
                    'oarea': 'area',
                    'ocorr': 'correlation_o',
                    'pcorr': 'correlation_p'}
    choice_type = choice_types[function]

    # Retrieve data package
    data = Index_Maps(choice, choice_type, time_data, colorscale)

    # Set mask (also sets coordinate dictionary)
    data.setMask(location, crdict)

    return data


# Output list of all index choices for syncing
@app.callback(Output('choice_store', 'children'),
              [Input('choice_1', 'value'),
               Input('choice_2', 'value')])
def storeIndexChoices(choice1, choice2):
    '''
    Collect and hide both data choices in the hidden 'choice_store' div
    '''
    return (json.dumps([choice1, choice2]))


@app.callback(Output('signal', 'children'),
              [Input('submit', 'n_clicks')],
              [State('colors', 'value'),
               State('reverse', 'value'),
               State('year_slider', 'value'),
               State('year_slider2', 'value'),
               State('month_slider', 'value'),
               State('month', 'values')])
def submitSignal(click, colorscale, reverse, year_range, year_range2,
                 month_range, month_filter):
    '''
    Collect and hide the options signal in the hidden 'signal' div.
    '''
    # This is to translate the inverse portion of the month range
    overflow = {13:11, 14:10, 15: 9, 16: 8, 17: 7, 18: 6, 19: 5, 20: 4, 21: 3,
                22: 2, 23:1}
    for i in [0, 1]:
        if month_range[i] > 12:
            month_range[i] = overflow[month_range[i]]
    signal = [[year_range, year_range2, month_range, month_filter], colorscale,
              reverse]
    return json.dumps(signal)


@app.callback([Output('options', 'style'),
               Output('toggle_options', 'style'),
               Output('submit', 'style'),
               Output('toggle_options', 'children')],
              [Input('toggle_options', 'n_clicks')])
def toggleOptions(click):
    '''
    Toggle options on/off
    '''
    if click % 2 == 0:
        div_style = {}
        button_style = on_button_style
        submit_style = {'background-color': '#C7D4EA',
                        'border-radius': '2px',
                        'font-family': 'Times New Roman',
                        'margin-top': '100px',
                        'margin-bottom': '35px'}
        children = "Display Options: On"
    else:
        div_style = {'display': 'none'}
        button_style = off_button_style
        submit_style = {'display': 'none'}
        children = "Display Options: Off"
    return div_style, button_style, submit_style, children


@app.callback([Output('click_sync', 'style'),
               Output('click_sync', 'children')],
              [Input('click_sync', 'n_clicks')])
def toggleLocationSyncButton(click):
    '''
    Change the color of on/off location syncing button - for css
    '''
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Location Syncing: On"
        style = on_button_style
    else:
        children = "Location Syncing: Off"
        style = off_button_style
    return style, children


@app.callback(Output('month', 'values'),
              [Input('all_months', 'n_clicks'),
               Input('no_months', 'n_clicks')])
def toggleMonthFilter(all_months, no_months):
    '''
    This fills or empties the month filter boxes with/of checks
    '''
    # If no clicks yet, prevent update
    if not any([all_months, no_months]):
        raise PreventUpdate

    # Find which input triggered this callback
    context = dash.callback_context
    triggered_value = context.triggered[0]['value']
    trigger = context.triggered[0]['prop_id']
    if triggered_value:
        if 'all' in trigger:
            return list(range(1, 13))
        else:
            return [None]


@app.callback(Output('year_div2', 'style'),
              [Input('year_sync', 'n_clicks')])
def toggleYearSlider(click):
    '''
    When syncing years, there should only be one time slider
    '''
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'display': 'none', 'margin-top': '0', 'margin-bottom': '80'}
    else:
        style = {'margin-top': '0', 'margin-bottom': '80'}
    return style


@app.callback([Output('year_sync', 'style'),
               Output('year_sync', 'children')],
              [Input('year_sync', 'n_clicks')])
def toggleYearSyncButton(click):
    '''
    Change the color of on/off year syncing button - for css
    '''
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Year Syncing: On"
        style = on_button_style
    else:
        children = "Year Syncing: Off"
        style = off_button_style
    return style, children

# In[] App callbacks
# For multiple instances
for i in range(1, 3):
    @app.callback(Output('location_store_{}'.format(i), 'children'),
                  [Input('map_1', 'clickData'),
                   Input('map_2', 'clickData'),
                   Input('map_1', 'selectedData'),
                   Input('map_2', 'selectedData'),
                   Input('county_1', 'value'),
                   Input('county_2', 'value'),
                   Input('shape_store_1', 'children'),
                   Input('shape_store_2', 'children'),
                   Input('update_graphs_1', 'n_clicks'),
                   Input('update_graphs_2', 'n_clicks'),
                   Input('reset_map_1', 'n_clicks'),
                   Input('reset_map_2', 'n_clicks')],
                  [State('state_1', 'value'),
                   State('state_2', 'value'),
                   State('click_sync', 'children'),
                   State('key_{}'.format(i), 'children')])
    def locationPicker(click1, click2, select1, select2, county1, county2,
                       shape1, shape2, update1, update2, reset1, reset2,
                       state1, state2, sync, key):
            '''
            This coordinates map selections between the two maps. I apologize
            for this, it can be rather confusing.

            The new context method allows us to select which input was most
            recently changed. However, it is still necessary to have an
            independent callback that identifies the most recent selection.
            Because there are many types of buttons and clicks that could
            trigger a graph update we have to work through each input to check
            if it is a location selector to begin with.

            Sample Arguments:

            key = 1
            sync = "Location Syncing: On"
            locations = [{'points': [{'curveNumber': 0, 'pointNumber': 3485, 'pointIndex': 3485, 'lon': -116.5, 'lat': 43.5, 'text': 'Ada County, ID (grid: 28145)<br>     41.571', 'marker.color': 41.57119369506836}]}, None, None, None, 24098, 24098, None, None, None, None, None, None]
            updates = [None, None]
            triggered_value = {'points': [{'curveNumber': 0, 'pointNumber': 3485, 'pointIndex': 3485, 'lon': -116.5, 'lat': 43.5, 'text': 'Ada County, ID (grid: 28145)<br>     41.571', 'marker.color': 41.57119369506836}]}
            trigger = "map_1.clickData"
            key = 0
            sync = "Location Syncing: On"
            locations = [{'points': [{'curveNumber': 0, 'pointNumber': 3485, 'pointIndex': 3485, 'lon': -116.5, 'lat': 43.5, 'text': 'Ada County, ID (grid: 28145)<br>     41.571', 'marker.color': 41.57119369506836}]}, None, None, None, 24098, 24098, None, None, None, None, None, None]
            updates = [None, None]
            triggered_value = {'points': [{'curveNumber': 0, 'pointNumber': 3485, 'pointIndex': 3485, 'lon': -116.5, 'lat': 43.5, 'text': 'Ada County, ID (grid: 28145)<br>     41.571', 'marker.color': 41.57119369506836}]}
            trigger = "map_1.clickData"
           '''
            # Figure out which element we are working with
            key = int(key) - 1

            # package all the selections for indexing
            if click1 is not None:
                print("\nCLICK1: " + str(click1) + "\n")
            locations = [click1, click2, select1, select2, county1, county2,
                         shape1, shape2, reset1, reset2, state1, state2]
            updates = [update1, update2]

            # Find which input triggered this callback
            context = dash.callback_context
            triggered_value = context.triggered[0]['value']
            trigger = context.triggered[0]['prop_id']

            # print out variables for developing
#            print('\n')
#            print("key = " + json.dumps(key))
#            print('\n')
#            print("sync = " + json.dumps(sync))
#            print('\n')
#            print("locations = " + str(locations))
#            print('\n')
#            print("updates = " + str(updates))
#            print('\n')
#            print("triggered_value = " + str(triggered_value))
#            print('\n')
#            print("trigger = " + json.dumps(trigger))
#            print('\n')

            # Two cases: 1) if syncing return a copy, 2) if not split
            if 'On' in sync:
                # If the update graph button activates US state selections
                if 'update_graph' in trigger:
                    if triggered_value is None:
                        triggered_value = 'all'
                        sel_idx = 0
                        triggering_element = sel_idx % 2 + 1
                    else:
                        # The idx of the most recent update is -2 or -1
                        update_idx = updates.index(triggered_value) - 2
                        if locations[update_idx] is None:
                            raise PreventUpdate
                        triggered_value = locations[update_idx]
                        sel_idx = locations.index(triggered_value)
                        triggering_element = sel_idx % 2 + 1
                else:
                    sel_idx = locations.index(triggered_value)
                    triggering_element = sel_idx % 2 + 1

                # Use the triggered_value to create the selector object
                selector = Location_Builder(trigger, triggered_value, crdict,
                                            admin_df, state_array,
                                            county_array)

                # Now retrieve information for the most recently updated element
                location, crds, pointids = selector.chooseRecent()

                # What is this about?
                if 'shape' in location[0] and location[3] is None:
                    location =  ['all', 'y', 'x', 'Contiguous United States']
                try:
                    location.append(triggering_element)
                except:
                    raise PreventUpdate

            # If not syncing, only use the inputs for this element
            if 'On' not in sync:
                locations = locations[key::2]

                # That also means that the triggering element is this one
                triggering_element = key + 1

                # The update graph button activates US state selections
                if 'update_graph' in trigger:
                    if triggered_value is None:
                        triggered_value = 'all'
                    else:
                        # The idx of the most recent update is -2 or -1
                        # update_idx = updates.index(triggered_value) - 2
                        if locations[-1] is None:
                            raise PreventUpdate
                        triggered_value = locations[-1]

                # If this element wasn't the trigger, prevent updates
                if triggered_value not in locations:
                    raise PreventUpdate

                # Use the triggered_value to create the selector object
                selector = Location_Builder(trigger, triggered_value,
                                            crdict, admin_df, state_array,
                                            county_array)

                # Retrieve information for the most recently updated element
                location, crds, pointids = selector.chooseRecent()

                # What is this about?
                if 'shape' in location[0] and location[3] is None:
                    location =  ['all', 'y', 'x', 'Contiguous United States']

                # Add the triggering element key to prevent updates later
                try:
                    location.append(triggering_element)
                except:
                    raise PreventUpdate

            return json.dumps([location, crds, pointids])

    @app.callback([Output('county_div_{}'.format(i), 'style'),
                   Output('state_div_{}'.format(i), 'style'),
                   Output('shape_div_{}'.format(i), 'style')],
                  [Input('location_tab_{}'.format(i), 'value'),
                   Input('state_{}'.format(i), 'value')],
                  [State('key_{}'.format(i), 'children')])
    def displayLocOptions(tab_choice, states, key):
        key = int(key)
        if tab_choice == 'county':
            county_style = {}
            state_style = {'display': 'none'}
            shape_style = {'display': 'none'}
        elif tab_choice == 'state':
            if states is not None:
                if len(states) <= 5:
                    font_size = 15
                else:
                    font_size = 8
            else:
                font_size = 15
            county_style = {'display': 'none'}
            state_style = {'font-size': font_size}
            shape_style = {'display': 'none'}
        else:
            county_style = {'display': 'none'}
            state_style = {'display': 'none'}
            shape_style = {}
        return county_style, state_style, shape_style


    @app.callback(Output('shape_store_{}'.format(i), 'children'),
                  [Input('shape_{}'.format(i), 'contents')],
                  [State('shape_{}'.format(i), 'filename'),
                   State('shape_{}'.format(i), 'last_modified')])
    def parseShape(contents, filenames, last_modified):
        '''
        contents = ['data:application/octet-stream;base64,U1FMaXRlIGZvcm1hdCAzABAAAgIAQCAgAAAADAAAADkAAAAAAAAAAAAAAB4AAAAEAAAAAAAAAAAAAAABAAAn2AAAAABHUEtHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAC4csAUAAAACD/YAAAAAOA/7D/YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEBwAAAAPEQ0AAAADDdMADjEN0w6WAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACBFwELVx1XDT0HBwcHAkVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNmZWF0dXJlc0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXMyMDE5LTA4LTI1VDIxOjE2OjQ0LjkxMVrAWiSNpqxRpkA51ojIdzjdwFdgj1ubOdtAQeaAM1rlHxDmCgAAAAEP1wAP1wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoA1cJRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhcwoAAAABD9cAD9cAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKANXCUVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXMNAAAAAQ/WAA/WAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKAEDVwlFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzCgAAAAEP1wAP1wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoA1cJRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhcw0AAAABD8AAD8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD4BB1cVJQIICEVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNnZW9tTVVMVElQT0xZR09OEOYKAAAAAQ/SAA/SAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAtBFcVCUVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNnZW9tCgAAAAEP1wAP1wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoA1cJRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhcw0AAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADQAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANDvIAEQBNAA76DN0Otw58DAEMmgloC7YLawd+CR8FuAV3BDgC6wGkAE0AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIJUEQcbVS0IhDF0cmlnZ2VyZ3BrZ190aWxlX21hdHJpeF9tYXRyaXhfd2lkdGhfdXBkYXRlZ3BrZ190aWxlX21hdHJpeENSRUFURSBUUklHR0VSICdncGtnX3RpbGVfbWF0cml4X21hdHJpeF93aWR0aF91cGRhdGUnIEJFRk9SRSBVUERBVEUgT0YgbWF0cml4X3dpZHRoIE9OICdncGtnX3RpbGVfbWF0cml4JyBGT1IgRUFDSCBST1cgQkVHSU4gU0VMRUNUIFJBSVNFKEFCT1JULCAndXBkYXRlIG9uIHRhYmxlICcnZ3BrZ190aWxlX21hdHJpeCcnIHZpb2xhdGVzIGNvbnN0cmFpbnQ6IG1hdHJpeF93aWR0aCBjYW5ub3QgYmUgbGVzcyB0aGFuIDEnKSBXSEVSRSAoTkVXLm1hdHJpeF93aWR0aCA8IDEpOyBFTkSCRBAHG1UtCIQRdHJpZ2dlcmdwa2dfdGlsZV9tYXRyaXhfbWF0cml4X3dpZHRoX2luc2VydGdwa2dfdGlsZV9tYXRyaXhDUkVBVEUgVFJJR0dFUiAnZ3BrZ190aWxlX21hdHJpeF9tYXRyaXhfd2lkdGhfaW5zZXJ0JyBCRUZPUkUgSU5TRVJUIE9OICdncGtnX3RpbGVfbWF0cml4JyBGT1IgRUFDSCBST1cgQkVHSU4gU0VMRUNUIFJBSVNFKEFCT1JULCAnaW5zZXJ0IG9uIHRhYmxlICcnZ3BrZ190aWxlX21hdHJpeCcnIHZpb2xhdGVzIGNvbnN0cmFpbnQ6IG1hdHJpeF93aWR0aCBjYW5ub3QgYmUgbGVzcyB0aGFuIDEnKSBXSEVSRSAoTkVXLm1hdHJpeF93aWR0aCA8IDEpOyBFTkSCSg8HG1EtCIQhdHJpZ2dlcmdwa2dfdGlsZV9tYXRyaXhfem9vbV9sZXZlbF91cGRhdGVncGtnX3RpbGVfbWF0cml4Q1JFQVRFIFRSSUdHRVIgJ2dwa2dfdGlsZV9tYXRyaXhfem9vbV9sZXZlbF91cGRhdGUnIEJFRk9SRSBVUERBVEUgb2Ygem9vbV9sZXZlbCBPTiAnZ3BrZ190aWxlX21hdHJpeCcgRk9SIEVBQ0ggUk9XIEJFR0lOIFNFTEVDVCBSQUlTRShBQk9SVCwgJ3VwZGF0ZSBvbiB0YWJsZSAnJ2dwa2dfdGlsZV9tYXRyaXgnJyB2aW9sYXRlcyBjb25zdHJhaW50OiB6b29tX2xldmVsIGNhbm5vdCBiZSBsZXNzIHRoYW4gMCcpIFdIRVJFIChORVcuem9vbV9sZXZlbCA8IDApOyBFTkSCPA4HG1EtCIQFdHJpZ2dlcmdwa2dfdGlsZV9tYXRyaXhfem9vbV9sZXZlbF9pbnNlcnRncGtnX3RpbGVfbWF0cml4Q1JFQVRFIFRSSUdHRVIgJ2dwa2dfdGlsZV9tYXRyaXhfem9vbV9sZXZlbF9pbnNlcnQnIEJFRk9SRSBJTlNFUlQgT04gJ2dwa2dfdGlsZV9tYXRyaXgnIEZPUiBFQUNIIFJPVyBCRUdJTiBTRUxFQ1QgUkFJU0UoQUJPUlQsICdpbnNlcnQgb24gdGFibGUgJydncGtnX3RpbGVfbWF0cml4JycgdmlvbGF0ZXMgY29uc3RyYWludDogem9vbV9sZXZlbCBjYW5ub3QgYmUgbGVzcyB0aGFuIDAnKSBXSEVSRSAoTkVXLnpvb21fbGV2ZWwgPCAwKTsgRU5EPw0GF1MtAQBpbmRleHNxbGl0ZV9hdXRvaW5kZXhfZ3BrZ190aWxlX21hdHJpeF8xZ3BrZ190aWxlX21hdHJpeA6DQwwHFy0tAYY5dGFibGVncGtnX3RpbGVfbWF0cml4Z3BrZ190aWxlX21hdHJpeA1DUkVBVEUgVEFCTEUgZ3BrZ190aWxlX21hdHJpeCAodGFibGVfbmFtZSBURVhUIE5PVCBOVUxMLHpvb21fbGV2ZWwgSU5URUdFUiBOT1QgTlVMTCxtYXRyaXhfd2lkdGggSU5URUdFUiBOT1QgTlVMTCxtYXRyaXhfaGVpZ2h0IElOVEVHRVIgTk9UIE5VTEwsdGlsZV93aWR0aCBJTlRFR0VSIE5PVCBOVUxMLHRpbGVfaGVpZ2h0IElOVEVHRVIgTk9UIE5VTEwscGl4ZWxfeF9zaXplIERPVUJMRSBOT1QgTlVMTCxwaXhlbF95X3NpemUgRE9VQkxFIE5PVCBOVUxMLENPTlNUUkFJTlQgcGtfdHRtIFBSSU1BUlkgS0VZICh0YWJsZV9uYW1lLCB6b29tX2xldmVsKSxDT05TVFJBSU5UIGZrX3RtbV90YWJsZV9uYW1lIEZPUkVJR04gS0VZICh0YWJsZV9uYW1lKSBSRUZFUkVOQ0VTIGdwa2dfY29udGVudHModGFibGVfbmFtZSkpgx4KBxc1NQGFX3RhYmxlZ3BrZ190aWxlX21hdHJpeF9zZXRncGtnX3RpbGVfbWF0cml4X3NldAtDUkVBVEUgVEFCTEUgZ3BrZ190aWxlX21hdHJpeF9zZXQgKHRhYmxlX25hbWUgVEVYVCBOT1QgTlVMTCBQUklNQVJZIEtFWSxzcnNfaWQgSU5URUdFUiBOT1QgTlVMTCxtaW5feCBET1VCTEUgTk9UIE5VTEwsbWluX3kgRE9VQkxFIE5PVCBOVUxMLG1heF94IERPVUJMRSBOT1QgTlVMTCxtYXhfeSBET1VCTEUgTk9UIE5VTEwsQ09OU1RSQUlOVCBma19ndG1zX3RhYmxlX25hbWUgRk9SRUlHTiBLRVkgKHRhYmxlX25hbWUpIFJFRkVSRU5DRVMgZ3BrZ19jb250ZW50cyh0YWJsZV9uYW1lKSxDT05TVFJBSU5UIGZrX2d0bXNfc3JzIEZPUkVJR04gS0VZIChzcnNfaWQpIFJFRkVSRU5DRVMgZ3BrZ19zcGF0aWFsX3JlZl9zeXMgKHNyc19pZCkpRwsGF1s1AQBpbmRleHNxbGl0ZV9hdXRvaW5kZXhfZ3BrZ190aWxlX21hdHJpeF9zZXRfMWdwa2dfdGlsZV9tYXRyaXhfc2V0DIQABwcXNzcBhx90YWJsZWdwa2dfZ2VvbWV0cnlfY29sdW1uc2dwa2dfZ2VvbWV0cnlfY29sdW1ucwhDUkVBVEUgVEFCTEUgZ3BrZ19nZW9tZXRyeV9jb2x1bW5zICh0YWJsZV9uYW1lIFRFWFQgTk9UIE5VTEwsY29sdW1uX25hbWUgVEVYVCBOT1QgTlVMTCxnZW9tZXRyeV90eXBlX25hbWUgVEVYVCBOT1QgTlVMTCxzcnNfaWQgSU5URUdFUiBOT1QgTlVMTCx6IFRJTllJTlQgTk9UIE5VTEwsbSBUSU5ZSU5UIE5PVCBOVUxMLENPTlNUUkFJTlQgcGtfZ2VvbV9jb2xzIFBSSU1BUlkgS0VZICh0YWJsZV9uYW1lLCBjb2x1bW5fbmFtZSksQ09OU1RSQUlOVCB1a19nY190YWJsZV9uYW1lIFVOSVFVRSAodGFibGVfbmFtZSksQ09OU1RSQUlOVCBma19nY190biBGT1JFSUdOIEtFWSAodGFibGVfbmFtZSkgUkVGRVJFTkNFUyBncGtnX2NvbnRlbnRzKHRhYmxlX25hbWUpLENPTlNUUkFJTlQgZmtfZ2Nfc3JzIEZPUkVJR04gS0VZIChzcnNfaWQpIFJFRkVSRU5DRVMgZ3BrZ19zcGF0aWFsX3JlZl9zeXMgKHNyc19pZCkpSQkGF103AQBpbmRleHNxbGl0ZV9hdXRvaW5kZXhfZ3BrZ19nZW9tZXRyeV9jb2x1bW5zXzJncGtnX2dlb21ldHJ5X2NvbHVtbnMKSQgGF103AQBpbmRleHNxbGl0ZV9hdXRvaW5kZXhfZ3BrZ19nZW9tZXRyeV9jb2x1bW5zXzFncGtnX2dlb21ldHJ5X2NvbHVtbnMJgRYFBxcvLwGBW3RhYmxlZ3BrZ19vZ3JfY29udGVudHNncGtnX29ncl9jb250ZW50cwZDUkVBVEUgVEFCTEUgZ3BrZ19vZ3JfY29udGVudHModGFibGVfbmFtZSBURVhUIE5PVCBOVUxMIFBSSU1BUlkgS0VZLGZlYXR1cmVfY291bnQgSU5URUdFUiBERUZBVUxUIE5VTEwpQQYGF1UvAQBpbmRleHNxbGl0ZV9hdXRvaW5kZXhfZ3BrZ19vZ3JfY29udGVudHNfMWdwa2dfb2dyX2NvbnRlbnRzB4McAgcXJycBhXd0YWJsZWdwa2dfY29udGVudHNncGtnX2NvbnRlbnRzA0NSRUFURSBUQUJMRSBncGtnX2NvbnRlbnRzICh0YWJsZV9uYW1lIFRFWFQgTk9UIE5VTEwgUFJJTUFSWSBLRVksZGF0YV90eXBlIFRFWFQgTk9UIE5VTEwsaWRlbnRpZmllciBURVhUIFVOSVFVRSxkZXNjcmlwdGlvbiBURVhUIERFRkFVTFQgJycsbGFzdF9jaGFuZ2UgREFURVRJTUUgTk9UIE5VTEwgREVGQVVMVCAoc3RyZnRpbWUoJyVZLSVtLSVkVCVIOiVNOiVmWicsJ25vdycpKSxtaW5feCBET1VCTEUsIG1pbl95IERPVUJMRSxtYXhfeCBET1VCTEUsIG1heF95IERPVUJMRSxzcnNfaWQgSU5URUdFUixDT05TVFJBSU5UIGZrX2djX3Jfc3JzX2lkIEZPUkVJR04gS0VZIChzcnNfaWQpIFJFRkVSRU5DRVMgZ3BrZ19zcGF0aWFsX3JlZl9zeXMoc3JzX2lkKSk5BAYXTScBAGluZGV4c3FsaXRlX2F1dG9pbmRleF9ncGtnX2NvbnRlbnRzXzJncGtnX2NvbnRlbnRzBTkDBhdNJwEAaW5kZXhzcWxpdGVfYXV0b2luZGV4X2dwa2dfY29udGVudHNfMWdwa2dfY29udGVudHMEAAAACAAAAACCAwEHFzU1AYMpdGFibGVncGtnX3NwYXRpYWxfcmVmX3N5c2dwa2dfc3BhdGlhbF9yZWZfc3lzAkNSRUFURSBUQUJMRSBncGtnX3NwYXRpYWxfcmVmX3N5cyAoc3JzX25hbWUgVEVYVCBOT1QgTlVMTCxzcnNfaWQgSU5URUdFUiBOT1QgTlVMTCBQUklNQVJZIEtFWSxvcmdhbml6YXRpb24gVEVYVCBOT1QgTlVMTCxvcmdhbml6YXRpb25fY29vcmRzeXNfaWQgSU5URUdFUiBOT1QgTlVMTCxkZWZpbml0aW9uICBURVhUIE5PVCBOVUxMLGRlc2NyaXB0aW9uIFRFWFQpDQmqAAsBswAIXwcDBbcEWwMPAbMPAg6wDRkLggqIAXQJqgCPAIcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAJqgEkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAglkXBxtVLQiEO3RyaWdnZXJncGtnX3RpbGVfbWF0cml4X3BpeGVsX3lfc2l6ZV91cGRhdGVncGtnX3RpbGVfbWF0cml4Q1JFQVRFIFRSSUdHRVIgJ2dwa2dfdGlsZV9tYXRyaXhfcGl4ZWxfeV9zaXplX3VwZGF0ZScgQkVGT1JFIFVQREFURSBPRiBwaXhlbF95X3NpemUgT04gJ2dwa2dfdGlsZV9tYXRyaXgnIEZPUiBFQUNIIFJPVyBCRUdJTiBTRUxFQ1QgUkFJU0UoQUJPUlQsICd1cGRhdGUgb24gdGFibGUgJydncGtnX3RpbGVfbWF0cml4JycgdmlvbGF0ZXMgY29uc3RyYWludDogcGl4ZWxfeV9zaXplIG11c3QgYmUgZ3JlYXRlciB0aGFuIDAnKSBXSEVSRSBOT1QgKE5FVy5waXhlbF95X3NpemUgPiAwKTsgRU5EgkkWBxtVLQiEG3RyaWdnZXJncGtnX3RpbGVfbWF0cml4X3BpeGVsX3lfc2l6ZV9pbnNlcnRncGtnX3RpbGVfbWF0cml4Q1JFQVRFIFRSSUdHRVIgJ2dwa2dfdGlsZV9tYXRyaXhfcGl4ZWxfeV9zaXplX2luc2VydCcgQkVGT1JFIElOU0VSVCBPTiAnZ3BrZ190aWxlX21hdHJpeCcgRk9SIEVBQ0ggUk9XIEJFR0lOIFNFTEVDVCBSQUlTRShBQk9SVCwgJ2luc2VydCBvbiB0YWJsZSAnJ2dwa2dfdGlsZV9tYXRyaXgnJyB2aW9sYXRlcyBjb25zdHJhaW50OiBwaXhlbF95X3NpemUgbXVzdCBiZSBncmVhdGVyIHRoYW4gMCcpIFdIRVJFIE5PVCAoTkVXLnBpeGVsX3lfc2l6ZSA+IDApOyBFTkSCWRUHG1UtCIQ7dHJpZ2dlcmdwa2dfdGlsZV9tYXRyaXhfcGl4ZWxfeF9zaXplX3VwZGF0ZWdwa2dfdGlsZV9tYXRyaXhDUkVBVEUgVFJJR0dFUiAnZ3BrZ190aWxlX21hdHJpeF9waXhlbF94X3NpemVfdXBkYXRlJyBCRUZPUkUgVVBEQVRFIE9GIHBpeGVsX3hfc2l6ZSBPTiAnZ3BrZ190aWxlX21hdHJpeCcgRk9SIEVBQ0ggUk9XIEJFR0lOIFNFTEVDVCBSQUlTRShBQk9SVCwgJ3VwZGF0ZSBvbiB0YWJsZSAnJ2dwa2dfdGlsZV9tYXRyaXgnJyB2aW9sYXRlcyBjb25zdHJhaW50OiBwaXhlbF94X3NpemUgbXVzdCBiZSBncmVhdGVyIHRoYW4gMCcpIFdIRVJFIE5PVCAoTkVXLnBpeGVsX3hfc2l6ZSA+IDApOyBFTkSCSRQHG1UtCIQbdHJpZ2dlcmdwa2dfdGlsZV9tYXRyaXhfcGl4ZWxfeF9zaXplX2luc2VydGdwa2dfdGlsZV9tYXRyaXhDUkVBVEUgVFJJR0dFUiAnZ3BrZ190aWxlX21hdHJpeF9waXhlbF94X3NpemVfaW5zZXJ0JyBCRUZPUkUgSU5TRVJUIE9OICdncGtnX3RpbGVfbWF0cml4JyBGT1IgRUFDSCBST1cgQkVHSU4gU0VMRUNUIFJBSVNFKEFCT1JULCAnaW5zZXJ0IG9uIHRhYmxlICcnZ3BrZ190aWxlX21hdHJpeCcnIHZpb2xhdGVzIGNvbnN0cmFpbnQ6IHBpeGVsX3hfc2l6ZSBtdXN0IGJlIGdyZWF0ZXIgdGhhbiAwJykgV0hFUkUgTk9UIChORVcucGl4ZWxfeF9zaXplID4gMCk7IEVORIJZEwcbVy0IhDl0cmlnZ2VyZ3BrZ190aWxlX21hdHJpeF9tYXRyaXhfaGVpZ2h0X3VwZGF0ZWdwa2dfdGlsZV9tYXRyaXhDUkVBVEUgVFJJR0dFUiAnZ3BrZ190aWxlX21hdHJpeF9tYXRyaXhfaGVpZ2h0X3VwZGF0ZScgQkVGT1JFIFVQREFURSBPRiBtYXRyaXhfaGVpZ2h0IE9OICdncGtnX3RpbGVfbWF0cml4JyBGT1IgRUFDSCBST1cgQkVHSU4gU0VMRUNUIFJBSVNFKEFCT1JULCAndXBkYXRlIG9uIHRhYmxlICcnZ3BrZ190aWxlX21hdHJpeCcnIHZpb2xhdGVzIGNvbnN0cmFpbnQ6IG1hdHJpeF9oZWlnaHQgY2Fubm90IGJlIGxlc3MgdGhhbiAxJykgV0hFUkUgKE5FVy5tYXRyaXhfaGVpZ2h0IDwgMSk7IEVORIJIEgcbVy0IhBd0cmlnZ2VyZ3BrZ190aWxlX21hdHJpeF9tYXRyaXhfaGVpZ2h0X2luc2VydGdwa2dfdGlsZV9tYXRyaXhDUkVBVEUgVFJJR0dFUiAnZ3BrZ190aWxlX21hdHJpeF9tYXRyaXhfaGVpZ2h0X2luc2VydCcgQkVGT1JFIElOU0VSVCBPTiAnZ3BrZ190aWxlX21hdHJpeCcgRk9SIEVBQ0ggUk9XIEJFR0lOIFNFTEVDVCBSQUlTRShBQk9SVCwgJ2luc2VydCBvbiB0YWJsZSAnJ2dwa2dfdGlsZV9tYXRyaXgnJyB2aW9sYXRlcyBjb25zdHJhaW50OiBtYXRyaXhfaGVpZ2h0IGNhbm5vdCBiZSBsZXNzIHRoYW4gMScpIFdIRVJFIChORVcubWF0cml4X2hlaWdodCA8IDEpOyBFTkQAAADeAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACBdxwHFysrAYMldGFibGVncGtnX2V4dGVuc2lvbnNncGtnX2V4dGVuc2lvbnM0Q1JFQVRFIFRBQkxFIGdwa2dfZXh0ZW5zaW9ucyAodGFibGVfbmFtZSBURVhULGNvbHVtbl9uYW1lIFRFWFQsZXh0ZW5zaW9uX25hbWUgVEVYVCBOT1QgTlVMTCxkZWZpbml0aW9uIFRFWFQgTk9UIE5VTEwsc2NvcGUgVEVYVCBOT1QgTlVMTCxDT05TVFJBSU5UIGdlX3RjZSBVTklRVUUgKHRhYmxlX25hbWUsIGNvbHVtbl9uYW1lLCBleHRlbnNpb25fbmFtZSkpgxQbCBuBEVcIhEl0cmlnZ2VydHJpZ2dlcl9kZWxldGVfZmVhdHVyZV9jb3VudF9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc0NSRUFURSBUUklHR0VSICJ0cmlnZ2VyX2RlbGV0ZV9mZWF0dXJlX2NvdW50X0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXMiIEFGVEVSIERFTEVURSBPTiAiRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhcyIgQkVHSU4gVVBEQVRFIGdwa2dfb2dyX2NvbnRlbnRzIFNFVCBmZWF0dXJlX2NvdW50ID0gZmVhdHVyZV9jb3VudCAtIDEgV0hFUkUgbG93ZXIodGFibGVfbmFtZSkgPSBsb3dlcignRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhcycpOyBFTkSDFBoIG4ERVwiESXRyaWdnZXJ0cmlnZ2VyX2luc2VydF9mZWF0dXJlX2NvdW50X0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzQ1JFQVRFIFRSSUdHRVIgInRyaWdnZXJfaW5zZXJ0X2ZlYXR1cmVfY291bnRfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhcyIgQUZURVIgSU5TRVJUIE9OICJFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzIiBCRUdJTiBVUERBVEUgZ3BrZ19vZ3JfY29udGVudHMgU0VUIGZlYXR1cmVfY291bnQgPSBmZWF0dXJlX2NvdW50ICsgMSBXSEVSRSBsb3dlcih0YWJsZV9uYW1lKSA9IGxvd2VyKCdFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzJyk7IEVORFAZBhcrKwFZdGFibGVzcWxpdGVfc2VxdWVuY2VzcWxpdGVfc2VxdWVuY2USQ1JFQVRFIFRBQkxFIHNxbGl0ZV9zZXF1ZW5jZShuYW1lLHNlcSmBexgHF1dXAYJVdGFibGVFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhcxFDUkVBVEUgVEFCTEUgIkVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXMiICggImZpZCIgSU5URUdFUiBQUklNQVJZIEtFWSBBVVRPSU5DUkVNRU5UIE5PVCBOVUxMLCAiZ2VvbSIgTVVMVElQT0xZR09OLCAiTkVSQyIgVEVYVCg1KSwgIk5FUkNfTGFiZWwiIFRFWFQoNzApKQ0AAAABAb4AAb4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB7AQZXFS1xIUVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNnZW9tZ3BrZ19ydHJlZV9pbmRleGh0dHA6Ly93d3cuZ2VvcGFja2FnZS5vcmcvc3BlYzEyMC8jZXh0ZW5zaW9uX3J0cmVld3JpdGUtb25seQoAAAABD8EAD8EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA+BVcVLQlFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzZ2VvbWdwa2dfcnRyZWVfaW5kZXgNAAAAAQstAAstAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIlQAQQAkyQAAAABAAAAAAAAAAHC0SRvwrsEeUHOtEZCDzQCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADQAAAAEP+wAP+wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAQMACQ0LhgALALMAC0cKaQmECJgHpAXDA70CGA2uDAQAswAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgmInBxt7VwiDfXRyaWdnZXJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fZGVsZXRlRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc0NSRUFURSBUUklHR0VSICJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fZGVsZXRlIiBBRlRFUiBERUxFVEUgT04gIkVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXMiIFdIRU4gb2xkLiJnZW9tIiBOT1QgTlVMTCBCRUdJTiBERUxFVEUgRlJPTSAicnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tIiBXSEVSRSBpZCA9IE9MRC4iZmlkIjsgRU5EgyIkBxt9VwiEe3RyaWdnZXJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fdXBkYXRlMkVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNDUkVBVEUgVFJJR0dFUiAicnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tX3VwZGF0ZTIiIEFGVEVSIFVQREFURSBPRiAiZ2VvbSIgT04gIkVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXMiIFdIRU4gT0xELiJmaWQiID0gTkVXLiJmaWQiIEFORCAoTkVXLiJnZW9tIiBJU05VTEwgT1IgU1RfSXNFbXB0eShORVcuImdlb20iKSkgQkVHSU4gREVMRVRFIEZST00gInJ0cmVlX0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNfZ2VvbSIgV0hFUkUgaWQgPSBPTEQuImZpZCI7IEVORIQDIwcbfVcIhj10cmlnZ2VycnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tX3VwZGF0ZTFFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzQ1JFQVRFIFRSSUdHRVIgInJ0cmVlX0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNfZ2VvbV91cGRhdGUxIiBBRlRFUiBVUERBVEUgT0YgImdlb20iIE9OICJFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzIiBXSEVOIE9MRC4iZmlkIiA9IE5FVy4iZmlkIiBBTkQgKE5FVy4iZ2VvbSIgTk9UTlVMTCBBTkQgTk9UIFNUX0lzRW1wdHkoTkVXLiJnZW9tIikpIEJFR0lOIElOU0VSVCBPUiBSRVBMQUNFIElOVE8gInJ0cmVlX0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNfZ2VvbSIgVkFMVUVTIChORVcuImZpZCIsU1RfTWluWChORVcuImdlb20iKSwgU1RfTWF4WChORVcuImdlb20iKSxTVF9NaW5ZKE5FVy4iZ2VvbSIpLCBTVF9NYXhZKE5FVy4iZ2VvbSIpKTsgRU5Eg14iBxt7VwiFdXRyaWdnZXJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21faW5zZXJ0RWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc0NSRUFURSBUUklHR0VSICJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21faW5zZXJ0IiBBRlRFUiBJTlNFUlQgT04gIkVsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXMiIFdIRU4gKG5ldy4iZ2VvbSIgTk9UIE5VTEwgQU5EIE5PVCBTVF9Jc0VtcHR5KE5FVy4iZ2VvbSIpKSBCRUdJTiBJTlNFUlQgT1IgUkVQTEFDRSBJTlRPICJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb20iIFZBTFVFUyAoTkVXLiJmaWQiLFNUX01pblgoTkVXLiJnZW9tIiksIFNUX01heFgoTkVXLiJnZW9tIiksU1RfTWluWShORVcuImdlb20iKSwgU1RfTWF4WShORVcuImdlb20iKSk7IEVORIFxIQcXe3sBgXl0YWJsZXJ0cmVlX0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNfZ2VvbV9wYXJlbnRydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fcGFyZW50OUNSRUFURSBUQUJMRSAicnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tX3BhcmVudCIobm9kZW5vIElOVEVHRVIgUFJJTUFSWSBLRVksIHBhcmVudG5vZGUgSU5URUdFUimBaSAHF3l5AYFtdGFibGVydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fcm93aWRydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fcm93aWQ3Q1JFQVRFIFRBQkxFICJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fcm93aWQiKHJvd2lkIElOVEVHRVIgUFJJTUFSWSBLRVksIG5vZGVubyBJTlRFR0VSKYFiHwcXd3cBgWN0YWJsZXJ0cmVlX0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNfZ2VvbV9ub2RlcnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tX25vZGU2Q1JFQVRFIFRBQkxFICJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fbm9kZSIobm9kZW5vIElOVEVHRVIgUFJJTUFSWSBLRVksIGRhdGEgQkxPQimBWx4HF21tCIFrdGFibGVydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21ydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21DUkVBVEUgVklSVFVBTCBUQUJMRSAicnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tIiBVU0lORyBydHJlZShpZCwgbWlueCwgbWF4eCwgbWlueSwgbWF4eSk9HQYXUSsBAGluZGV4c3FsaXRlX2F1dG9pbmRleF9ncGtnX2V4dGVuc2lvbnNfMWdwa2dfZXh0ZW5zaW9uczUAAAB+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACDJyYHG31XCIUFdHJpZ2dlcnJ0cmVlX0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNfZ2VvbV91cGRhdGU0RWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc0NSRUFURSBUUklHR0VSICJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fdXBkYXRlNCIgQUZURVIgVVBEQVRFIE9OICJFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzIiBXSEVOIE9MRC4iZmlkIiAhPSBORVcuImZpZCIgQU5EIChORVcuImdlb20iIElTTlVMTCBPUiBTVF9Jc0VtcHR5KE5FVy4iZ2VvbSIpKSBCRUdJTiBERUxFVEUgRlJPTSAicnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tIiBXSEVSRSBpZCBJTiAoT0xELiJmaWQiLCBORVcuImZpZCIpOyBFTkSETyUHG31XCIdVdHJpZ2dlcnJ0cmVlX0VsZWN0cmljIFJlbGlhYmlsaXR5IENvdW5jaWwgb2YgVGV4YXNfZ2VvbV91cGRhdGUzRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc0NSRUFURSBUUklHR0VSICJydHJlZV9FbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzX2dlb21fdXBkYXRlMyIgQUZURVIgVVBEQVRFIE9OICJFbGVjdHJpYyBSZWxpYWJpbGl0eSBDb3VuY2lsIG9mIFRleGFzIiBXSEVOIE9MRC4iZmlkIiAhPSBORVcuImZpZCIgQU5EIChORVcuImdlb20iIE5PVE5VTEwgQU5EIE5PVCBTVF9Jc0VtcHR5KE5FVy4iZ2VvbSIpKSBCRUdJTiBERUxFVEUgRlJPTSAicnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tIiBXSEVSRSBpZCA9IE9MRC4iZmlkIjsgSU5TRVJUIE9SIFJFUExBQ0UgSU5UTyAicnRyZWVfRWxlY3RyaWMgUmVsaWFiaWxpdHkgQ291bmNpbCBvZiBUZXhhc19nZW9tIiBWQUxVRVMgKE5FVy4iZmlkIixTVF9NaW5YKE5FVy4iZ2VvbSIpLCBTVF9NYXhYKE5FVy4iZ2VvbSIpLFNUX01pblkoTkVXLiJnZW9tIiksIFNUX01heFkoTkVXLiJnZW9tIikpOyBFTkQNAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA']
        filenames = ['Electric Reliability Council of Texas.gpkg']
        last_modified = [1566767804]
        '''

        if not contents:
            raise PreventUpdate
        if filenames:
            basename = os.path.splitext(filenames[0])[0]
            if len(filenames) == 1:
                from zipfile import ZipFile
                if any(e in filenames[0] for e in ['zip', '.7z']):
                    content_type, shp_element = contents[0].split(',')
                    decoded = base64.b64decode(shp_element)
                    with tempfile.TemporaryFile() as tmp:
                        tmp.write(decoded)
                        tmp.seek(0)
                        archive = ZipFile(tmp, 'r')
                        for file in archive.filelist:
                            fname = file.filename
                            content = archive.read(fname)
                            name, ext = os.path.splitext(fname)
                            fname = 'temp' + ext
                            fdir = 'data/shapefiles/temp/'
                            with open(fdir + fname, 'wb') as f:
                                f.write(content)

            elif len(filenames) > 1:
                content_elements = [c.split(',') for c in contents]
                elements = [e[1] for e in content_elements]
                for i in range(len(elements)):
                    decoded = base64.b64decode(elements[i])
                    fname = filenames[i]
                    name, ext = os.path.splitext(fname)
                    fname = 'temp' + ext
                    fname = os.path.join('data', 'shapefiles', 'temp', fname)
                    with open(fname, 'wb') as f:
                        f.write(decoded)

            # Now let's just rasterize it for a mask
            shp = gpd.read_file('data/shapefiles/temp/temp.shp')

            # Check CRS, reproject if needed
            crs = shp.crs
            try:
                epsg = crs['init']
                epsg = int(epsg[epsg.index(':') + 1:])
            except:
                fshp = fiona.open('data/shapefiles/temp/temp.shp')
                crs_wkt = fshp.crs_wkt
                crs_ref = osr.SpatialReference()
                crs_ref.ImportFromWkt(crs_wkt)
                crs_ref.AutoIdentifyEPSG()
                epsg = crs_ref.GetAttrValue('AUTHORITY', 1)
                epsg = int(epsg)
                fshp.close()

            if epsg != 4326:
                shapeReproject(src='data/shapefiles/temp/temp.shp',
                               dst='data/shapefiles/temp/temp.shp',
                               src_epsg=epsg, dst_epsg=4326)

            # Find a column that is numeric
#            numeric = shp._get_numeric_data()  # <---------------------------- I must've done this for a reason, probabyly looking for an id number
            attr = shp.columns[0]

            # Rasterize
            src = 'data/shapefiles/temp/temp.shp'
            dst = 'data/shapefiles/temp/temp1.tif'
            admin.rasterize(src, dst, attribute=attr, all_touch=False)  # <---- All touch not working.

            # Cut to extent
            tif = gdal.Translate('data/shapefiles/temp/temp.tif',
                                 'data/shapefiles/temp/temp1.tif',
                                 projWin=[-130, 50, -55, 20])
            tif = None

            return basename


    @app.callback(Output('coverage_div_{}'.format(i), 'children'),
                  [Input('series_{}'.format(i), 'hoverData'),
                   Input('dsci_button_{}'.format(i), 'n_clicks'),
                   Input('submit', 'n_clicks')],
                  [State('function_choice', 'value')])
    def hoverCoverage(hover, click1, click2, function):
        '''
        The tooltips on the drought severity coverage area graph were
        overlapping, so this outputs the hover data to a chart below instead.
        '''
        if function == 'oarea':
            try:
                date = dt.datetime.strptime(hover['points'][0]['x'],
                                            '%Y-%m-%d')
                date = dt.datetime.strftime(date, '%b, %Y')
                if click1 % 2 == 0:
                    ds = ['{0:.2f}'.format(hover['points'][i]['y']) for
                          i in range(5)]
                    coverage_df = pd.DataFrame({'D0 - D4 (Dry)': ds[0],
                                                'D1 - D4 (Moderate)': ds[1],
                                                'D2 - D4 (Severe)': ds[2],
                                                'D3 - D4 (Extreme)': ds[3],
                                                'D4 (Exceptional)': ds[4]},
                                               index=[0])

                else:
                    ds = ['{0:.2f}'.format(hover['points'][i]['y']) for
                          i in range(6)]
                    coverage_df = pd.DataFrame({'D0 - D4 (Dry)': ds[0],
                                                'D1 - D4 (Moderate)': ds[1],
                                                'D2 - D4 (Severe)': ds[2],
                                                'D3 - D4 (Extreme)': ds[3],
                                                'D4 (Exceptional)': ds[4],
                                                'DSCI':ds[5]},
                                               index=[0])
                children=[
                    html.H6([date],
                            style={'text-align': 'left'}),
                    dash_table.DataTable(
                      data=coverage_df.to_dict('rows'),
                        columns=[
                          {"name": i, "id": i} for i in coverage_df.columns],
                        style_cell={'textAlign': 'center'},
                        style_header={'fontWeight': 'bold'},
                        style_header_conditional=[
                                {'if': {'column_id': 'D0 - D4 (Dry)'},
                                        'backgroundColor': '#ffff00',
                                        'color': 'black'},
                                {'if': {'column_id': 'D1 - D4 (Moderate)'},
                                            'backgroundColor': '#fcd37f',
                                             'color': 'black'},
                                 {'if': {'column_id': 'D2 - D4 (Severe)'},
                                        'backgroundColor': '#ffaa00',
                                        'color': 'black'},
                                 {'if': {'column_id': 'DSCI'},
                                        'backgroundColor': '#27397F',
                                        'color': 'white',
                                        'width': '75'},
                                 {'if': {'column_id': 'D3 - D4 (Extreme)'},
                                        'backgroundColor': '#e60000',
                                        'color': 'white'},
                                 {'if': {'column_id': 'D4 (Exceptional)'},
                                         'backgroundColor': '#730000',
                                         'color': 'white'}],
                         style_data_conditional=[
                                 {'if': {'column_id': 'D0 - D4 (Dry)'},
                                         'backgroundColor': '#ffffa5',
                                         'color': 'black'},
                                 {'if': {'column_id': 'D1 - D4 (Moderate)'},
                                         'backgroundColor': '#ffe5af',
                                         'color': 'black'},
                                 {'if': {'column_id': 'D2 - D4 (Severe)'},
                                         'backgroundColor': '#ffc554',
                                         'color': 'black'},
                                 {'if': {'column_id': 'DSCI'},
                                         'backgroundColor': '#5c678e',
                                         'color': 'white',
                                         'width': '75'},
                                 {'if': {'column_id': 'D3 - D4 (Extreme)'},
                                         'backgroundColor': '#dd6666',
                                         'color': 'white'},
                                 {'if': {'column_id': 'D4 (Exceptional)'},
                                         'backgroundColor': '#a35858',
                                         'color': 'white'}])]
            except:
                raise PreventUpdate
        else:
            children = None

        return children


    @app.callback([Output('dsci_button_{}'.format(i), 'style'),
                   Output('dsci_button_{}'.format(i), 'children')],
                  [Input('submit', 'n_clicks'),
                   Input('dsci_button_{}'.format(i), 'n_clicks')],
                  [State('function_choice', 'value')])
    def displayDSCI(click1, click2, function):
        '''
        Toggle the blue Drought Severity Coverage Index on and off for the
        drought area option.
        '''
        if function == 'oarea':
            if click2 % 2 == 0:
                style = {'background-color': '#a8b3c4',
                         'border-radius': '4px',
                         'font-family': 'Times New Roman'}
                children = 'Show DSCI: Off'
            else:
                style = {'background-color': '#c7d4ea',
                         'border-radius': '4px',
                         'font-family': 'Times New Roman'}
                children = 'Show DSCI: On'
        else:
            style = {'display': 'none'}
            children = 'Show DSCI: Off'

        return style, children


    # @app.callback(Output('state_{}'.format(i), 'placeholder'),
    #               [Input('update_graphs_1', 'n_clicks'),
    #                Input('update_graphs_2', 'n_clicks'),
    #                Input('location_store_{}'.format(i), 'children')],
    #               [State('key_{}'.format(i), 'children'),
    #                State('click_sync', 'children')])
    # def dropState(update1, update2, location, key, sync):
    #     '''
    #     This is supposed to update the opposite placeholder of the updated map
    #     to reflect the state selection if there was a state selection.
    #     '''
    #     # Temporary, split location up for coordinates
    #     location = json.loads(location)
    #     location, crds = location

    #     # Check which element the selection came from
    #     sel_idx = location[-1]
    #     if 'On' not in sync:
    #         idx = int(key) - 1
    #         if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
    #             raise PreventUpdate
    #     try:
    #         if 'state' in location[0]:
    #             states = location[-2]
    #         return states
    #     except Exception as e:
    #         raise PreventUpdate


    # @app.callback([Output('county_{}'.format(i), 'options'),
    #                Output('county_{}'.format(i), 'placeholder'),
    #                Output('label_store_{}'.format(i), 'children')],
    #               [Input('location_store_{}'.format(i), 'children')],
    #               [State('county_{}'.format(i), 'value'),
    #                State('county_{}'.format(i), 'label'),
    #                State('label_store_{}'.format(i), 'children'),
    #                State('key_{}'.format(i), 'children'),
    #                State('click_sync', 'children')])
    # def dropCounty(location, current_fips, current_label, previous_fips, key,
    #                sync):
    #     '''
    #     As a work around to updating synced dropdown labels and because we
    #     can't change the dropdown value with out creating an infinite loop, we
    #     are temporarily changing the options so that the value stays the same,
    #     but the one label to that value is the synced county name.

    #     So, this has obvious issues. In the case one clicks on the altered
    #     county selector, another one entirely will show.

    #     I wonder how long it will take for someone to find this out :).

    #     Check that we are working with the right selection, and do this first
    #     to prevent update if not syncing
    #     '''
    #     # Temporary, split location up
    #     location = json.loads(location)
    #     location, crds = location

    #     # Check which element the selection came from
    #     sel_idx = location[-1]
    #     if 'On' not in sync:
    #         idx = int(key) - 1
    #         if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
    #             raise PreventUpdate
    #     try:
    #         # Only update if it is a singular point
    #         location[0].index('id')

    #         # Recreate the county options
    #         current_options = copy.deepcopy(county_options)

    #         # Grid id is labeled differently
    #         if location[0] == 'grid_id':
    #             current_label = location[3]
    #             current_county = current_label[:current_label.index(" (")]
    #         elif location[0] == 'county_id':
    #             current_county = location[3]
    #         else:
    #             current_county = 'Multiple Counties'
    #         try:
    #             old_idx = fips_pos[current_fips]
    #         except:
    #             old_idx = label_pos[current_county]

    #         current_options[old_idx]['label'] = current_county

    #         return current_options, current_county, current_fips

    #     except:
    #         raise PreventUpdate


    @app.callback(Output("map_{}".format(i), 'figure'),
                  [Input('choice_1', 'value'),
                   Input('choice_2', 'value'),
                   Input('map_type', 'value'),
                   Input('signal', 'children'),
                   Input('location_store_1'.format(i), 'children'),
                   Input('location_store_2'.format(i), 'children')],
                  [State('function_choice', 'value'),
                   State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children'),
                   State('year_sync', 'children'),
                   State('date_print', 'children'),
                   State('date_print2', 'children'),
                   State('map_{}'.format(i), 'relayoutData')])
    def makeMap(choice1, choice2, map_type, signal,
                l1, l2, function, key, sync, year_sync, date_print,
                date_print2, map_extent):
        '''
        This renders the map.

        Sample arguments:

        map_type = 'dark'
        key = '2'
        signal = '[[[2000, 2019], [2000, 2019], [1, 12], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]], "Default", "no"]'
        l1 = '[["all", "y", "x", "Contiguous United States", 0], 9, "None"]'
        l2 = '[["all", "y", "x", "Contiguous United States", 0], 9, "None"]'
        choice1 = 'vpdmean'
        choice2 = 'vpdmean'
        function = 'pmean'
        date_print = '2000 - 2019'
        date_print2 = '2000 - 2019'
        sync = 'Location Syncing: On'
        year_sync = 'Year Syncing: On'
        map_extent = 'None'
        '''
#        print("map_type = " + str(map_type))
#        print("key = " + str(key))
#        print("signal = " + str(signal))
#        print("l1 = " + str(l1))
#        print("l2 = " + str(l2))
#        print("choice1 = " + str(choice1))
#        print("choice2 = " + str(choice2))
#        print("function = " + str(function))
#        print("date_print = " + str(date_print))
#        print("date_print2 = " + str(date_print2))
#        print("sync = " + str(sync))
#        print("year_sync = " + str(year_sync))
#        print("map_extent = " + str(map_extent))

        # Identify element number
        key = int(key)

        # Temporary, split location up
        locations = [l1, l2]
        location = locations[key-1]
        location = json.loads(location)
        location, crds, pointids = location

        # To save zoom levels and extent between map options (funny how this works)
        if not map_extent:
            map_extent = default_extent
        elif 'mapbox.center' not in map_extent.keys():
            map_extent = default_extent

        # Prevent update if not syncing and not triggered
        trig = dash.callback_context.triggered[0]['prop_id']
        if trig == 'location_store_{}.children'.format(key):
            triggered_element = location[-1]
            if 'On' not in sync:
                if triggered_element != key:
                    raise PreventUpdate

        print("Rendering Map #{}".format(key))

        # Create signal for the global_store
        signal = json.loads(signal)

        # Collect signal elements
        [[year_range, year_range2, [month1, month2], month_filter],
         colorscale, reverse] = signal

        # If we are syncing times, pop the second year range off
        if 'On' in year_sync:
            signal[0].pop(1)
        else:
            if key == 1:
                signal[0].pop(1)
            else:
                signal[0].pop(0)
                date_print = date_print2

        # DASH doesn't seem to like passing True/False as values
        verity = {'no': False, 'yes':True}
        reverse = verity[reverse]

        # Figure which choice is this panel's and which is the other
        key = int(key) - 1
        choices = [choice1, choice2]
        choice = choices[key]
        choice2 = choices[~key]

        # Get/cache data
        data = retrieveData(signal, function, choice, location)
        choice_reverse = data.reverse
        if choice_reverse:
            reverse = not reverse

        # Pull array into memory
        array = data.getFunction(function).compute()

        # Individual array min/max
        amax = np.nanmax(array)
        amin = np.nanmin(array)

        # Now, we want to use the same value range for colors for both maps
        nonindices = ['tdmean', 'tmean', 'tmin', 'tmax', 'ppt',  'vpdmax',
                      'vpdmin', 'vpdmean']
        print(choice in nonindices)
        print(amin)
        if function == 'pmean':
            # Get the data for the other panel for its value range
            data2 = retrieveData(signal, function, choice2, location)
            array2 = data2.getFunction(function).compute()
            amax2 = np.nanmax(array2)
            amin2 = np.nanmin(array2)
            amax = np.nanmax([amax, amax2])
            amin = np.nanmin([amin, amin2])
            del array2
        elif 'min' in function or 'max' in function:
            amax = amax
            amin = amin
        elif choice in nonindices:
            amax = amax
            amin = amin
        else:
            limit = np.nanmax([abs(amin), abs(amax)])
            amax = limit
            amin = limit * -1

        # Get highlight locs
        # Create the scattermapbox object
        flag, y, x, label, idx = location

        # We have a new problem, the index values aren't being masked properly. Maybe this old bit could help
#        if flag == 'state' or flag == 'county':
#            array = array * data.mask
#        elif flag == 'shape':
#            y = np.array(json.loads(y))
#            x = np.array(json.loads(x))
#            gridids = grid[y, x]
#            array[~np.isin(grid, gridids)] = np.nan

        # If it is a correlation recreate the map array
        if 'corr' in function and flag != 'all':
            y = np.array(json.loads(y))
            x = np.array(json.loads(x))
            gridid = grid[y, x]
            amin = 0
            amax = 1
            if type(gridid) is np.ndarray:
                grids = [np.nanmin(gridid), np.nanmax(gridid)]
                title = (indexnames[choice] + '<br>' +
                         function_names[function] + 'With Grids ' +
                         str(int(grids[0]))  + ' to ' + str(int(grids[1])) +
                         '  ('  + date_print + ')')
                title_size = 15
            else:
                title = (indexnames[choice] + '<br>' +
                         function_names[function] + 'With Grid ' +
                         str(int(gridid))  + '  ('  + date_print + ')')

            # This is the only map interaction that alters the map
            array = data.getCorr(location, crdict)  # <------------------------ Expected memory spike
            title_size = 20
        else:
            title = (indexnames[choice] + '<br>' + function_names[function] +
                     ': ' + date_print)
            title_size = 20

        # Replace the source array with the data from above
        source.data[0] = array #* mask

        # Create a data frame of coordinates, index values, labels, etc
        dfs = xr.DataArray(source, name="data")
        pdf = dfs.to_dataframe()
        step = crdict.res
        def to_bin(x):
            return np.floor(x / step) * step
        pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
        pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
        pdf['gridx'] = pdf['lonbin'].map(crdict.londict)
        pdf['gridy'] = pdf['latbin'].map(crdict.latdict)

        # For hover information
        grid2 = np.copy(grid)
        grid2[np.isnan(grid2)] = 0
        pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
        pdf = pd.merge(pdf, admin_df, how='inner')
        pdf['data'] = pdf['data'].astype(float)
        pdf['printdata'] = (pdf['place'] + " (grid: " +
                            pdf['grid'].apply(int).apply(str) + ")<br>     " +
                            pdf['data'].round(3).apply(str))
        df = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
        df['xy'] = df['gridx'].astype(str) + df['gridy'].astype(str)

        # Get Highlighted points
        if flag == 'all':
            pointids = df.index.to_numpy()
        elif pointids == 'None':
            y, x = np.where(~np.isnan(data.mask.data))
            xy = [str(x[i]) + str(y[i]) for i in range(len(x))]
            pointids = df.index[df['xy'].isin(xy)].to_numpy()

        # Build the list of plotly data dictionaries
        data = [dict(type='scattermapbox',
                     lon=df['lonbin'],
                     lat=df['latbin'],
                     text=df['printdata'],
                     mode='markers',
                     hoverinfo='text',
                     hovermode='closest',
                     showlegend=False,
                     selectedpoints=pointids,
                     marker=dict(colorscale=data.color_scale,
                                 reversescale=reverse,
                                 color=df['data'],
                                 cmax=amax,
                                 cmin=amin,
                                 opacity=1.0,
                                 size=source.res[0] * 20,
                                 colorbar=dict(textposition="auto",
                                               orientation="h",
                                               font=dict(size=15,
                                                         fontweight='bold'))))]

        # Set up layout
        layout_copy = copy.deepcopy(layout)
        layout_copy['mapbox'] = dict(
            accesstoken=mapbox_access_token,
            style=map_type,
            center=dict(lon=-95.7, lat=37.1),
            zoom=2)
        layout_copy['mapbox']['center'] = map_extent['mapbox.center']
        layout_copy['mapbox']['zoom'] = map_extent['mapbox.zoom']
        layout_copy['mapbox']['bearing'] = map_extent['mapbox.bearing']
        layout_copy['mapbox']['pitch'] = map_extent['mapbox.pitch']
        layout_copy['titlefont']=dict(color='#CCCCCC', size=title_size,
                                      family='Time New Roman',
                                      fontweight='bold')
        layout_copy['title'] = title
        figure = dict(data=data, layout=layout_copy)

        # Clear memory space
        gc.collect()

        # Check on Memory
        print("\nCPU: {}% \nMemory: {}%\n".format(psutil.cpu_percent(),
                                        psutil.virtual_memory().percent))

        return figure


    @app.callback([Output('series_{}'.format(i), 'figure'),
                   Output('download_link_{}'.format(i), 'href'),
                   Output('area_store_{}'.format(i), 'children')],
                  [Input('submit', 'n_clicks'),
                   Input('signal', 'children'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('choice_store', 'children'),
                   Input('location_store_{}'.format(i), 'children'),
                   Input('dsci_button_{}'.format(i), 'n_clicks')],
                  [State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children'),
                   State('year_sync', 'children'),
                   State('function_choice', 'value'),
                   State('area_store_{}'.format(i), 'children')])
    def makeSeries(submit, signal, choice, choice_store, location, show_dsci,
                   key, sync, year_sync, function, area_store):
        '''
        This makes the time series graph below the map.
        Sample arguments:
            signal = [[[2000, 2017], [1, 12], [5, 6, 7, 8]], 'Viridis', 'no']
            choice = 'pdsi'
            function = 'oarea'
            location =  ['all', 'y', 'x', 'Contiguous United States', 0]
        '''

        # Temporary, split location up
        location = json.loads(location)
        location, crds, pointids = location

        # Identify element number
        key = int(key)

        # Prevent update from location unless it is a state filter
        trig = dash.callback_context.triggered[0]['prop_id']

        # If we aren't syncing or changing the function or color
        if trig == 'location_store_{}.children'.format(key):
            triggered_element = location[-1]
            if 'On' not in sync:
                if triggered_element != key:
                    raise PreventUpdate

        # Create signal for the global_store
        choice_store = json.loads(choice_store)
        signal = json.loads(signal)

        # Collect signals
        [[year_range, year_range2, [month1, month2],
         month_filter], colorscale, reverse] = signal

        # If we are syncing times, pop the second year range
        if 'On' in year_sync:
            signal[0].pop(1)
        else:
            if key == 1:
                signal[0].pop(1)
            else:
                signal[0].pop(0)

        # DASH doesn't seem to like passing True/False as values
        verity = {'no': False, 'yes': True}
        reverse = verity[reverse]

        # Get/cache data
        data = retrieveData(signal, function, choice, location)
        choice_reverse = data.reverse
        if choice_reverse:
            reverse = not reverse
        dates = data.dataset_interval.time.values
        dates = [pd.to_datetime(str(d)).strftime('%Y-%m') for d in dates]
        dmin = data.data_min
        dmax = data.data_max

        # Now, before we calculate the time series, there is some area business
        area_store_key = str(signal) + '_' + choice + '_' + str(location)
        area_store = json.loads(area_store)

        # If the function is oarea, we plot five overlapping timeseries
        label = location[3]
        nonindices = ['tdmean', 'tmean', 'tmin', 'tmax', 'ppt',  'vpdmax',
                      'vpdmin', 'vpdmean']
        if function != 'oarea' or choice in nonindices:
            # Get the time series from the data object
            timeseries = data.getSeries(location, crdict)

            # Create data frame as string for download option
            columns = OrderedDict({'month': dates,
                                   'value': list(timeseries),
                                   'function': function_names[function],  # <-- This doesn't always make sense
                                   'location': location[-2],
                                   'index': indexnames[choice],
                                   'coord_extent': str(crds)})
            df = pd.DataFrame(columns)
            df_str = df.to_csv(encoding='utf-8', index=False)
            href = "data:text/csv;charset=utf-8," + urllib.parse.quote(df_str)
            bar_type = 'bar'
            area_store = ['', '']

            if choice in nonindices and function == 'oarea':
                label = '(Drought Severity Categories Not Available)'

        else:
            bar_type = 'overlay'
            label = location[3]

            # I cannot get this thing to cache! We are storing it in a Div
            if area_store_key == area_store[0]:
                ts_series, ts_series_ninc, dsci = area_store[1]
            else:
                ts_series, ts_series_ninc, dsci = data.getArea(crdict)

            # This needs to be returned either way
            series = [ts_series, ts_series_ninc, dsci]
            area_store = [area_store_key, series, dates]

            # Save to file for download option
            columns = OrderedDict({'month': dates,
                                   'd0': ts_series_ninc[0],
                                   'd1': ts_series_ninc[1],
                                   'd2': ts_series_ninc[2],
                                   'd3': ts_series_ninc[3],
                                   'd4': ts_series_ninc[4],
                                   'dsci': dsci,
                                   'function': 'Percent Area',
                                   'location':  label,
                                   'coord_extent': str(crds),
                                   'index': indexnames[choice]})
            df = pd.DataFrame(columns)
            df_str = df.to_csv(encoding='utf-8', index=False)
            href = "data:text/csv;charset=utf-8," + urllib.parse.quote(df_str)

        # Set up y-axis depending on selection
        if function != 'oarea' or choice in nonindices:
            if 'p' in function:
                yaxis = dict(title='Percentiles', range=[0, 100])
            elif 'o' in function:
                yaxis = dict(range=[dmin, dmax], title=unit_map[choice])

                # Center the color scale
                xmask = data.mask
                sd = data.dataset_interval.where(xmask == 1).std()
                sd = float(sd.compute().value) # Sheesh
                if 'eddi' in choice:
                    sd = sd*-1
                dmin = 3*sd
                dmax = 3*sd*-1

        # A few pieces to incorporate in to Index_Maps later
        if 'corr' in function:
            reverse = not reverse
            if 'p' in function:
                dmin = 0
                dmax = 100

        # The drought area graphs have there own configuration
        elif function == 'oarea' and choice not in nonindices:
            yaxis = dict(title='Percent Area (%)',
                         range=[0, 100],
                         # family='Time New Roman',
                         hovermode='y')

        # Build the plotly readable dictionaries (Two types)
        if function != 'oarea' or choice in nonindices:
            data = [dict(type='bar',
                         x=dates,
                         y=timeseries,
                         marker=dict(color=timeseries,
                                     colorscale=data.color_scale,
                                     reversescale=reverse,
                                     autocolorscale=False,
                                     cmin=dmin,
                                     cmax=dmax,
                                     line=dict(width=0.2,
                                               color="#000000")))]

        else:
            # The drought area data
            colors = ['rgb(255, 255, 0)','rgb(252, 211, 127)',
                      'rgb(255, 170, 0)', 'rgb(230, 0, 0)', 'rgb(115, 0, 0)']
            if year_range[0] != year_range[1]:
                line_width = 1 + ((1/(year_range[1] - year_range[0])) * 25)
            else:
                line_width = 12
            data = []
            for i in range(5):
                trace = dict(type='scatter',
                             fill='tozeroy',
                             mode='none',
                             showlegend=False,
                             x=dates,
                             y=ts_series[i],
                             hoverinfo='x',
                             fillcolor=colors[i])
                data.append(trace)

            # Toggle the DSCI
            if show_dsci % 2 != 0:
                data.insert(5, dict(x=dates,
                                    y=dsci,
                                    yaxis='y2',
                                    hoverinfo='x',
                                    showlegend=False,
                                    line=dict(color='rgba(39, 57, 127, 0.85)',
                                              width=line_width)))

        # Copy and customize Layout
        if label is None:
            label = 'Existing Shapefile'
        layout_copy = copy.deepcopy(layout)
        layout_copy['title'] = indexnames[choice] + "<Br>" + label
        layout_copy['plot_bgcolor'] = "white"
        layout_copy['paper_bgcolor'] = "white"
        layout_copy['height'] = 300
        layout_copy['yaxis'] = yaxis
        layout_copy['font'] = dict(family='Time New Roman')
        if function == 'oarea':
            if type(location[0]) is int:
                layout_copy['title'] = (indexnames[choice] +
                                        '<Br>' + 'Contiguous US ' +
                                        '(point estimates not available)')
            layout_copy['xaxis'] = dict(type='date',
                                        font=dict(family='Times New Roman'))
            layout_copy['yaxis2'] = dict(title='<br>DSCI',
                                         range=[0, 500],
                                         anchor='x',
                                         overlaying='y',
                                         side='right',
                                         position=0.15)
            layout_copy['margin'] = dict(l=55, r=55, b=25, t=90, pad=10)
        layout_copy['hovermode'] = 'x'
        layout_copy['barmode'] = bar_type
        layout_copy['legend'] = dict(orientation='h',
                                     y=-.5,
                                     markers=dict(size=10),
                                     font=dict(size=10))
        layout_copy['titlefont']['color'] = '#636363'
        layout_copy['font']['color'] = '#636363'

        figure = dict(data=data, layout=layout_copy)

        return figure, href, json.dumps(area_store)


# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()
