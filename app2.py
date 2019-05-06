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
       was keeping much of the data on disk. Explicitly setting chunk sizes
       seemed to help only slightly, and not at all for the correlation and
       drought severity calcualtions (in memory numba and reprojection calls).

Created on April 15th 2019

@author: Travis Williams - Earth Lab of the Universty of Colorado Boulder
         Travis.Williams@colorado.edu
"""

# Functions and Libraries
import netCDF4  # Leave this, without it there are problems in Linux
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
from inspect import currentframe, getframeinfo
import json
import numpy as np
import os
from osgeo import gdal, osr
import pandas as pd
import psutil
import sys
import urllib
import warnings
import xarray as xr

# Set Working Directory
frame = getframeinfo(currentframe()).filename
path = os.path.dirname(os.path.abspath(frame))
os.chdir(path)

# Import functions and classes
from functions2 import Admin_Elements, datePrint, Index_Maps, Location_Builder
from functions2 import shapeReproject

# Check if we are working in Windows or Linux to find the data
if sys.platform == 'win32':
    data_path = 'f:/'
else:
    data_path = '/root/Sync/'

# What to do with the mean of empty slice warning?
warnings.filterwarnings("ignore")

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
default_sample = 'leri1'  # Move these down to experiment with "high" res
default_1 = 'leri1'
default_2 = 'leri3'
default_sample = 'spi1'
default_1 = 'pdsi'
default_2 = 'spei6'
default_years = [2000, 2019]
default_location = ['all', 'y', 'x', 'Contiguous United States']

# Default click before the first click for any map (might not be necessary)
default_click = {'points': [{'curveNumber': 0, 'lat': 40.0, 'lon': -105.75,
                             'marker.color': 0, 'pointIndex': 0,
                             'pointNumber': 0, 'text': 'Boulder County, CO'}]}

# Default for click store (includes an index for most recent click)
default_clicks = [list(np.repeat(default_click.copy(), 4)), 0]
default_clicks = json.dumps(default_clicks)

# For scaling
ranges = pd.read_csv('data/tables/index_ranges.csv')

############### The DASH application and server ###############################
app = dash.Dash(__name__)

# Go to stylesheet, styled after a DASH example (how to serve locally?)  # <--- Check out criddyp's response about a third of the way down here <https://community.plot.ly/t/serve-locally-option-with-additional-scripts-and-style-sheets/6974/6>
app.css.append_css({'external_url':
                    'https://codepen.io/williamstravis/pen/maxwvK.css'})
# app.scripts.config.serve_locally = True

# For the Loading screen
app.css.append_css({"external_url":
                    "https://codepen.io/williamstravis/pen/EGrWde.css"})

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
           {'label': 'PDSI-Self Calibrated', 'value': 'pdsisc'},
           {'label': 'Palmer Z Index', 'value': 'pdsiz'},
           {'label': 'SPI-1', 'value': 'spi1'},
           {'label': 'SPI-2', 'value': 'spi2'},
           {'label': 'SPI-3', 'value': 'spi3'},
           {'label': 'SPI-6', 'value': 'spi6'},
           {'label': 'SPEI-1', 'value': 'spei1'},
           {'label': 'SPEI-2', 'value': 'spei2'},
           {'label': 'SPEI-3', 'value': 'spei3'},
           {'label': 'SPEI-6', 'value': 'spei6'},
           {'label': 'EDDI-1', 'value': 'eddi1'},
           {'label': 'EDDI-2', 'value': 'eddi2'},
           {'label': 'EDDI-3', 'value': 'eddi3'},
           {'label': 'EDDI-6', 'value': 'eddi6'},
           {'label': 'LERI-1', 'value': 'leri1'},
           {'label': 'LERI-3', 'value': 'leri3'}]

# Index dropdown labels
indexnames = {'pdsi': 'Palmer Drought Severity Index',
              'pdsisc': 'Self-Calibrated Palmer Drought Severity Index',
              'pdsiz': 'Palmer Z Index',
              'spi1': 'Standardized Precipitation Index - 1 month',
              'spi2': 'Standardized Precipitation Index - 2 month',
              'spi3': 'Standardized Precipitation Index - 3 month',
              'spi6': 'Standardized Precipitation Index - 6 month',
              'spei1': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 1 month',
              'spei2': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 2 month',
              'spei3': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 3 month',
              'spei6': 'Standardized Precipitation-Evapotranspiration Index' +
                       ' - 6 month',
              'eddi1': 'Evaporative Demand Drought Index - 1 month',
              'eddi2': 'Evaporative Demand Drought Index - 2 month',
              'eddi3': 'Evaporative Demand Drought Index - 3 month',
              'eddi6': 'Evaporative Demand Drought Index - 6 month',
              'leri1': 'Landscape Evaporative Response Index - 1 month',
              'leri3': 'Landscape Evaporative Response Index - 3 month'}

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

# County data frame and options
counties_df = pd.read_csv('data/tables/unique_counties.csv')
rows = [r for idx, r in counties_df.iterrows()]
county_options = [{'label': r['place'], 'value': r['fips']} for r in rows]
fips_pos = {county_options[i]['value']: i for i in range(len(county_options))}
label_pos = {county_options[i]['label']: i for i in range(len(county_options))}

# State options
states_df = pd.read_table('data/tables/state_fips.txt', sep='|')
states_df = states_df.sort_values('STUSAB')
nconus = ['AK', 'AS', 'DC', 'GU', 'HI', 'MP', 'PR', 'UM', 'VI']  # <----------- I'm reading a book about how we ignore most of these D: ... In the future we'll have to include them.
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
min_year = pd.Timestamp(min_date).year
max_month = pd.Timestamp(max_date).month

# Get spatial dimensions from the sample data set above
admin = Admin_Elements(resolution)
[state_array, county_array, grid, mask,
 source, albers_source, crdict, admin_df] = admin.getElements()  # <----------- remove albers source here

# Date options
years = [int(y) for y in range(min_year, max_year + 1)]
{'label': '0°C', 'style': {'color': '#77b0b1'}}
yearmarks = {y: {'label': y, 'style': {"transform": "rotate(45deg)"}} for
             y in years}        
# yearmarks = dict(zip(years, years))
monthmarks = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
monthmarks_full = {1: 'January', 2: 'February', 3: 'March', 4: 'April',
                   5: 'May', 6: 'June', 7: 'July', 8: 'August', 9: 'September',
                   10: 'October', 11: 'November', 12: 'December'}
monthoptions = [{'label': monthmarks[i], 'value': i} for
                 i in range(1, 13)]
monthoptions_full = [{'label': monthmarks_full[i], 'value': i} for
                      i in range(1, 13)]

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
    paper_bgcolor="#0D347C",
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
selected_style = {'color': 'black', 'box-shadow': '1px 1px 0px white',
                  'border-left': '1px solid lightgrey',
                  'border-right': '1px solid lightgrey',
                  'border-top': '3px solid #e36209'}
unselected_style = {'border-top-left-radius': '3px',
                    'background-color': '#f9f9f9',
                    'padding': '0px 24px',
                    'border-bottom': '1px solid #d6d6d6'}
on_button_style = {'background-color': '#C7D4EA',
                   'border-radius': '4px',
                   'font-family': 'Times New Roman'}
off_button_style =  {'background-color': '#a8b3c4',
                     'border-radius': '4px',
                     'font-family': 'Times New Roman'}

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
                                 label='Drought Index',
                                 style=tablet_style,
                                 selected_style=tablet_style)),
              dcc.Dropdown(id='choice_{}'.format(id_num),
                           options=indices, value=index)],
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
                                 selected_style=tablet_style),
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
                            style={'width': '55%',
                                   'float': 'left'}),

            html.Div([
              html.Button(
                id='reset_map_{}'.format(id_num),
                children='Reset',
                title=('Remove area filters.'),
                style={'width': '20%',
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
                style={'width': '20%',
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


# Static Elements
app.layout = html.Div([
      html.Div([

         # Sponsers
         html.A(
           html.Img(
             src=("https://github.com/WilliamsTravis/Pasture-Rangeland-" +
                  "Forage/blob/master/data/earthlab.png?raw=true"),
             className='one columns',
             style={'height': '40',
                    'width': '100',
                    'float': 'right',
                    'position': 'static'}),
             href="https://www.colorado.edu/earthlab/",
             target="_blank"),
         html.A(
           html.Img(
             src=('https://github.com/WilliamsTravis/Pasture-Rangeland-' +
                  'Forage/blob/master/data/wwa_logo2015.png?raw=true'),
             className='one columns',
             style={'height': '50',
                    'width': '150',
                    'float': 'right',
                    'position': 'static'}),
             href="http://wwa.colorado.edu/",
             target="_blank"),
         html.A(
           html.Img(
             src=("https://github.com/WilliamsTravis/Pasture-Rangeland-" +
                  "Forage/blob/master/data/nidis.png?raw=true"),
             className='one columns',
             style={'height': '50',
                    'width': '200',
                    'float': 'right',
                    'position': 'relative'}),
             href="https://www.drought.gov/drought/",
             target="_blank"),
         html.A(
           html.Img(
             src=("https://github.com/WilliamsTravis/Pasture-Rangeland-" +
                  "Forage/blob/master/data/cires.png?raw=true"),
             className='one columns',
             style={'height': '50',
                    'width': '100',
                    'float': 'right',
                    'position': 'relative',
                    'margin-right': '20'}),
             href="https://cires.colorado.edu/",
             target="_blank")],
         className='row'),

        # Title
        html.Div([
            html.H1('Drought Index Comparison Portal'),
            html.Hr()],
            className='twelve columns',
            style={'font-weight': 'bolder',
                   'text-align': 'center',
                   'font-size': '50px',
                   'font-family': 'Times New Roman',
                   'margin-top': '25'}),

        # Toggle Options
        html.Div([
                html.Button(id='toggle_options',
                            children='Toggle Options: Off',
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
                            style={'display': 'none'})],
                style={'margin-bottom': '30',
                       'text-align': 'center'}),

       # Description
       html.Div([
         html.Div([
           dcc.Markdown(id='description')],
                        style={'text-align':'center',
                               'width':'70%',
                               'margin':'0px auto'}),
           html.Hr()],
           style={'text-align':'center',
                  'margin': '0 auto',
                  'width': '100%'}),

       # Date Options
       html.Div(id='options',
                children=[

                  # Year Slider
                  html.Div([
                    html.H3(id='date_range',
                            children=['Year Range']),
                    html.Div([
                      dcc.RangeSlider(id='year_slider',
                                      value=default_years,
                                      min=min_year,
                                      max=max_year,
                                      updatemode='drag',
                                      marks=yearmarks)],
                      style={'margin-top': '0',
                             'margin-bottom': '80'})]),

                  # Month Slider
                  html.Div(id='month_slider',
                           children=[
                             html.Div([
                               html.H5('Beginning Month'),
                               dcc.Dropdown(id='month_1',
                                            options=monthoptions_full,
                                            value=1)],
                               className='two columns',
                               title=('Choose the first month of the first ' +
                                      'year of the study period.')),
                             html.Div([
                               html.H5('Ending Month'),
                               dcc.Dropdown(id='month_2',
                                            options=monthoptions_full,
                                            value=12)],
                               className='two columns',
                               title=('Choose the last month of the last ' +
                                      'year of the study period.')),
                            html.Div(
                              id='month_slider_holder',
                              children=[
                                html.H5('Included Months'),
                                  dcc.Checklist(
                                    className='check_blue',
                                    id='month',
                                    options=monthoptions,
                                    values=list(range(1, 13)),
                                    labelStyle={'display':
                                                'inline-block'})],
                               className='eight columns',
                               title=('Choose which months of the year to ' +
                                      'be included.'))])],
                    className="row",
                   style={'margin-bottom': '75'}),

       # Rendering Options
       html.Div(id='options_div',
                children=[
                  # Maptype
                  html.Div([
                    html.H3("Map Type"),
                    dcc.Dropdown(id="map_type",
                                 value="basic",
                                 options=maptypes)],
                    className='two columns'),

                  # Functions
                  html.Div([
                    html.H3("Function"),
                    dcc.Tabs(
                      id='function_type',
                      value='index',
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
                                 value='pmean')],
                    className='three columns'),

                  # Customize Color Scales
                  html.Div([
                    html.H3('Color Gradient'),
                    dcc.Tabs(
                      id='reverse',
                      value=False,
                      style=tab_style,
                      children=[
                        dcc.Tab(value=False,
                                label="Not Reversed",
                                style=tab_style,
                                selected_style=tablet_style),
                        dcc.Tab(value=True,
                                label='Reversed',
                                style=tab_style,
                                selected_style=tablet_style)]),
                    dcc.Dropdown(id='colors',
                                 options=color_options,
                                 value='Default')],
                    className='three columns')],
                className='row',
                style={'margin-bottom': '50',
                       'margin-top': '50'}),

       # Break
       html.Br(style={'line-height': '500%'}),

       # Submission Button
       html.Div([
         html.Button(id='submit',
                     title=('Submit the option settings ' +
                            'above and update the graphs below.'),
                     children='Submit Options',
                     type='button',
                     style={'background-color': '#C7D4EA',
                            'border-radius': '2px',
                            'font-family': 'Times New Roman'})],
         style={'text-align': 'center'}),

       # Break line
       html.Hr(),

       # Two by two map layout
       # Row 1
       html.Div([divMaker(1, default_1), divMaker(2, default_2)],
                className='row'),

       # Signals
       html.Div(id='signal', style={'display': 'none'}),
       html.Div(id='location_store', style={'display': 'none'}),
       html.Div(id='choice_store', style={'display': 'none'})],

    className='ten columns offset-by-one')  # The end!


# In[]: App Callbacks
@app.callback(Output('date_range', 'children'),
              [Input('year_slider', 'value')])
def adjustYear(year_range):
    '''
    If users select one year, only print it once
    '''
    if year_range[0] == year_range[1]:
        string = 'Year Range: {}'.format(year_range[0])
    else:
        string = 'Year Range: {} - {}'.format(year_range[0], year_range[1])
    return string


@app.callback([Output('options', 'style'),
               Output('toggle_options', 'style'),
               Output('toggle_options', 'children')],
              [Input('toggle_options', 'n_clicks')])
def toggleOptions(click):
    '''
    Toggle options on/off
    '''
    if not click:
        click = 0
    if click % 2 == 0:
        div_style = {}
        button_style = {'background-color': '#c7d4ea',
                        'border-radius': '4px',
                        'font-family': 'Times New Roman'}
        children = "Display Options: On"
    else:
        div_style = {'display': 'none'}
        button_style = {'background-color': '#a8b3c4',
                        'border-radius': '4px',
                        'font-family': 'Times New Roman'}
        children = "Display Options: Off"
    return div_style, button_style, children


@app.callback([Output('click_sync', 'style'),
               Output('click_sync', 'children')],
              [Input('click_sync', 'n_clicks')])
def toggleSyncButton(click):
    '''
    Change the color of on/off location syncing button  - for css
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
        style = {'background-color': '#a8b3c4',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman'}
        button_children = "Description: Off"

    else:
        desc_children = open('data/tables/description.txt').read()
        style = {'background-color': '#c7d4ea',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman'}
        button_children = "Description: On"

    return desc_children, style, button_children


@app.callback([Output('function_choice', 'options'),
               Output('function_choice', 'value')],
              [Input('function_type', 'value')])
def functionOptions(function_type):
    '''
    Use the Percentile/Index tab to decide which functions options to
    display.
    '''
    if function_type == 'perc':
        return function_options_perc, 'pmean'
    else:
        return function_options_orig, 'omean'


@cache.memoize()
def retrieveData(signal, function, choice): 
    '''
    This takes the user defined signal and uses the Index_Map class to filter'
    by the selected dates and return the singular map, the 3d timeseries array,
    and the colorscale.
    
    sample arguments:
        signal = [[[2000, 2017], [1, 12], [ 4, 5, 6, 7]], 'Viridis', 'no']
        choice = 'pdsi'
        function = 'omean'
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

    # Retrieve data package (how to only update time_data)
    data = Index_Maps(choice, choice_type, time_data, colorscale)

    return data


# @cache2.memoize()
# def retrieveAreaData(arrays, choice):
#     '''
#     This is here just to cache the output of 'droughtArea', which returns both
#     the 5 categorical drought coverages (% area) and the singlular DSCI. The
#     DSCI cannot be calculated from the 5 coverages because these are inclusive
#     for display purposes while the DSCI uses only the percentage of area in
#     each category. 

#     When there is enough memory to use this, toggling the DSCI on and off will
#     be immediate because it will not need to be recalculated each time.
#     '''
#     return droughtArea(arrays, choice)


# Output list of all index choices for syncing
@app.callback(Output('choice_store', 'children'),
              [Input('choice_1', 'value'),
               Input('choice_2', 'value')])
def choiceStore(choice1, choice2):
    ''' 
    Collect and hide both data choices in the hidden 'choice_store' div
    '''
    return (json.dumps([choice1, choice2]))


@app.callback(Output('signal', 'children'),
              [Input('submit', 'n_clicks')],
              [State('colors', 'value'),
               State('reverse', 'value'),
               State('year_slider', 'value'),
               State('month_1', 'value'),
               State('month_2', 'value'),
               State('month', 'values')])
def submitSignal(click, colorscale, reverse, year_range, month1, month2,
                 month_filter):
    '''
    Collect and hide the options signal in the hidden 'signal' div.
    '''
    # print(str(month_filter))
    signal = [[year_range, [month1, month2], month_filter], colorscale,
              reverse]
    return json.dumps(signal)


@app.callback(Output('location_store', 'children'),
              [Input('map_1', 'clickData'),
               Input('map_2', 'clickData'),
               Input('map_1', 'selectedData'),
               Input('map_2', 'selectedData'),
               Input('county_1', 'value'),
               Input('county_2', 'value'),
               Input('shape_store_1', 'children'),
               Input('shape_store_2', 'children'),
               Input('update_graphs_1', 'n_clicks'),
               Input('update_graphs_2', 'n_clicks')],
              [State('state_1', 'value'),
               State('state_2', 'value')])
def locationPicker(click1, click2, select1, select2, county1, county2, shape1,
                   shape2, update1, update2, state1, state2):
        '''
        The new context method allows us to select which input was most
        recently changed. However, it is still necessary to have an
        independent callback that identifies the most recent selection. Because
        there are many types of buttons and clicks that could trigger a graph
        update we would have to work through each input to check if it is a
        location. It's still much nicer than setting up a dozen hidden divs,
        timing callbacks, and writing long lines of logic to determine which
        was most recently updated.
        '''
        # package the selections for indexing
        locations = [click1, click2, select1, select2, county1, county2,
                     shape1, shape2, state1, state2]
        updates = [update1, update2]
        context = dash.callback_context
        triggered_value = context.triggered[0]['value']
        trigger = context.triggered[0]['prop_id']

        # The update graph button activates state selections
        if 'update_graph' in trigger:
            # When you switch from county to state, there is no initial value 
            if triggered_value is None:
                triggered_value = 'all'
                sel_idx = 0
            else:
                # The position of the most recent update needs to be -2 or -1
                update_idx = updates.index(triggered_value) - 2
                if locations[update_idx] is None:
                    raise PreventUpdate
                triggered_value = locations[update_idx]
                sel_idx = locations.index(triggered_value)
        else:
            sel_idx = locations.index(triggered_value)

        selector = Location_Builder(trigger, triggered_value, crdict, admin_df,
                                    state_array, county_array)
        location = selector.chooseRecent()
        if 'shape' in location[0] and location[3] is None:
            default_loc = copy.deepcopy(default_location)
            location = default_loc
        try:
            location.append(sel_idx)
        except:
            raise PreventUpdate

        return location


# In[] Any callback with multiple instances goes here
for i in range(1, 3):
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
        if filenames:
            basename = os.path.splitext(filenames[0])[0]
            if len(filenames) == 1:
                from zipfile import ZipFile
                from tempfile import SpooledTemporaryFile
                if '.zip' in filenames[0] or '.7z' in filenames[0]:
                    content_type, shp_element = contents[0].split(',')
                    decoded = base64.b64decode(shp_element)
                    with SpooledTemporaryFile() as tmp:
                        tmp.write(decoded)
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
                    fname = os.path.join('data', 'shapefiles', 'temp',
                                         fname)
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
            numeric = shp._get_numeric_data()
            attr = numeric.columns[0]

            # Rasterize
            src = 'data/shapefiles/temp/temp.shp'
            dst = 'data/shapefiles/temp/temp1.tif'
            admin.rasterize(src, dst, attribute=attr, all_touch=False)  # <---- All touch not working.

            # Cut to extent
            tif = gdal.Translate('data/shapefiles/temp/temp.tif',
                                 'data/shapefiles/temp/temp1.tif',
                                  projWin=[-130, 50, -55, 20])
            del tif

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


    @app.callback(Output('state_{}'.format(i), 'placeholder'),
                  [Input('update_graphs_1', 'n_clicks'),
                   Input('update_graphs_2', 'n_clicks'), 
                   Input('location_store', 'children')],
                  [State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children')])
    def dropState(update1, update2, location, key, sync):
        '''
        This is supposed to update the opposite placeholder of the updated map
        to reflect the state selection if there was a state selection. 
        '''
        # Check which element the selection came from
        sel_idx = location[-1]
        if 'On' not in sync:
            idx = int(key) - 1
            if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
                raise PreventUpdate
        try:
            if 'state' in location[0]:
                states = location[-2]
            return states
        except Exception as e:
            raise PreventUpdate


    @app.callback([Output('county_{}'.format(i), 'options'),
                   Output('county_{}'.format(i), 'placeholder'),
                   Output('label_store_{}'.format(i), 'children')],
                  [Input('location_store', 'children')],
                  [State('county_{}'.format(i), 'value'),
                   State('county_{}'.format(i), 'label'),
                   State('label_store_{}'.format(i), 'children'),
                   State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children')])
    def dropCounty(location, current_fips, current_label, previous_fips, key,
                   sync):
        '''
        As a work around to updating synced dropdown labels and because we
        can't change the dropdown value with out creating an infinite loop, we
        are temporarily changing the options so that the value stays the same,
        but the one label to that value is the synced county name.

        So, this has obvious issues. In the case one clicks on the altered
        county selector, another one entirely will show.

        I wonder how long it will take for someone to find this out :).

        Check that we are working with the right selection, and do this first
        to prevent update if not syncing
        '''
        # Check which element the selection came from
        sel_idx = location[-1]
        if 'On' not in sync:
            idx = int(key) - 1
            if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
                raise PreventUpdate
        try: 
            # Only update if it is a singular point
            location[0].index('id')

            # Recreate the county options
            current_options = copy.deepcopy(county_options)

            # Grid id is labeled differently
            if location[0] == 'grid_id':
                current_label = location[3]
                current_county = current_label[:current_label.index(" (")]
            elif location[0] == 'county_id':
                current_county = location[3]
            else:
                current_county = 'Multiple Counties'
            try:
                old_idx = fips_pos[current_fips]
            except:
                old_idx = label_pos[current_county]
    
            current_options[old_idx]['label'] = current_county
            
            return current_options, current_county, current_fips

        except:
            raise PreventUpdate


    @app.callback(Output("map_{}".format(i), 'figure'),
                  [Input('choice_1', 'value'),
                   Input('choice_2', 'value'),
                   Input('map_type', 'value'),
                   Input('signal', 'children'),
                   Input('location_store', 'children'),
                   Input('reset_map_1', 'n_clicks'),
                   Input('reset_map_2', 'n_clicks')],
                  [State('function_choice', 'value'),
                   State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children')])
    def makeGraph(choice1, choice2, map_type, signal, location, reset1, reset2,
                  function, key, sync):
        '''
        This actually renders the map. I want to modularize, but am struggling
        on this.
        
        Sample arguments
        location =  ['all', 'y', 'x', 'Contiguous United States', 0]

        '''
        # Prevent update from location unless it is a state or shape filter
        trig = dash.callback_context.triggered[0]['prop_id']

        if trig == 'location_store.children':
            if 'corr' not in function:
                if 'grid' in location[0] or 'county' in location[0]:
                    raise PreventUpdate

            # Check which element the selection came from
            sel_idx = location[-1]
            if 'On' not in sync:
                idx = int(key) - 1
                if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
                    raise PreventUpdate

        if 'reset_map' in trig:
            sel_idx = location[-1]
            location = ['all', 'y', 'x', 'CONUS', sel_idx]
            if 'On' not in sync:
                idx = int(key) - 1
                if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
                    raise PreventUpdate

        print("Rendering Map #{}".format(int(key)))

        # Create signal for the global_store
        signal = json.loads(signal)

        # Collect signal elements
        [[year_range, [month1, month2], month_filter],
         colorscale, reverse] = signal

        # Figure which choice is this panel's and which is the other
        key = int(key) - 1
        choices = [choice1, choice2]
        choice = choices[key]
        choice2 = choices[~key]

        # Get/cache data <----------------------------------------------------- Is this caching properly with the Index_Maps object?
        data = retrieveData(signal, function, choice)

        # Pull array into memory
        array = data.getFunction(function).compute()

        # Individual array min/max
        amax = np.nanmax(array)
        amin = np.nanmin(array)

        # Now, we want to use the same value range for colors for both maps
        if function == 'pmean':
            # Get the data for the other panel for its value range
            data2 = retrieveData(signal, function, choice2)
            array2 = data2.getFunction(function).compute()
            amax2 = np.nanmax(array2)
            amin2 = np.nanmin(array2)        
            amax = np.nanmax([amax, amax2])        
            amin = np.nanmin([amin, amin2])
            del array2
        else:
            limit = np.nanmax([abs(amin), abs(amax)])
            amax = limit
            amin = limit * -1


        # Experimenting with leri  # <----------------------------------------- Temporary
        if 'leri' in choice:
            amin = 0

        # EDDI has an inverse scale
        if 'eddi' in choice:
            print("Reversing EDDI")
            reverse = not reverse
 
        # Filter for state filters
        # print("location: " + str(location))
        flag, y, x, label, idx = location
        if flag == 'state':
            data.setMask(location, crdict)
            array = array * data.mask
        elif flag == 'shape':
            y = np.array(json.loads(y))
            x = np.array(json.loads(x))        
            gridids = grid[y, x]
            array[~np.isin(grid, gridids)] = np.nan

        # Get the right print statement for the date used
        date_print = datePrint(year_range[0], year_range[1], month1, month2,
                               month_filter, monthmarks)

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
        source.data[0] = array * mask

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
        df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
        df = df_flat[np.isfinite(df_flat['data'])]

        # Create the scattermapbox object
        data = [dict(type='scattermapbox',
                     lon=df['lonbin'],
                     lat=df['latbin'],
                     text=df['printdata'],
                     mode='markers',
                     hoverinfo='text',
                     hovermode='closest',
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

        layout_copy = copy.deepcopy(layout)
        layout_copy['mapbox'] = dict(
            accesstoken=mapbox_access_token,
            style=map_type,
            center=dict(lon=-95.7, lat=37.1),
            zoom=2)
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
                   Output('download_link_{}'.format(i), 'href')],
                  [Input('submit', 'n_clicks'),
                   Input('signal', 'children'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('choice_store', 'children'),
                   Input('location_store', 'children'),
                   Input('dsci_button_{}'.format(i), 'n_clicks'),
                   Input('reset_map_1', 'n_clicks'),
                   Input('reset_map_2', 'n_clicks')],
                  [State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children'),
                   State('function_choice', 'value')])
    def makeSeries(submit, signal, choice, choice_store, location, show_dsci,
                   reset1, reset2, key, sync, function):
        '''
        This makes the time series graph below the map.  
        
        Smaple arguments:
            signal = [[[2000, 2017], [1, 12], [5, 6, 7, 8]], 'Viridis', 'no']
            choice = 'pdsi'
            function = 'oarea'
        '''
        # Prevent update from location unless it is a state filter
        trig = dash.callback_context.triggered[0]['prop_id']

        # Check which element the selection came from
        if trig == 'location_store.children':
            sel_idx = location[-1]
            if 'On' not in sync:
                idx = int(key) - 1
                if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
                    raise PreventUpdate

        # Reset Everything
        if 'reset_map' in trig:
            sel_idx = location[-1]
            location = ['all', 'y', 'x', 'Contiguous United States', sel_idx]
            if 'On' not in sync:
                idx = int(key) - 1
                if sel_idx not in idx + np.array([0, 2, 4, 6, 8]):
                    raise PreventUpdate

        # Create signal for the global_store
        choice_store = json.loads(choice_store)
        signal = json.loads(signal)

        # Collect signals
        [[year_range, [month1, month2], 
         month_filter], colorscale, reverse] = signal

        # Get/cache data
        data = retrieveData(signal, function, choice)
        dates = data.dataset_interval.time.values
        dates = [pd.to_datetime(str(d)).strftime('%Y-%m') for d in dates]
        dmin = data.data_min
        dmax = data.data_max
        data.setMask(location, crdict)

        # Experimenting with LERI
        if 'leri' in choice:  # <---------------------------------------------- Temporary
            dmin = 0
            dmax = 100

        # If the function is oarea, we plot five overlapping timeseries
        label = location[3]
        print(str(location))
        if function != 'oarea':
            # Get the time series from the data object
            timeseries = data.getSeries(location, crdict)

            # Create data frame as string for download option
            columns = OrderedDict({'month': dates,
                                   'value': list(timeseries), 
                                   'function': function_names[function],  # <-- This doesn't always make sense
                                   'location': location[-2],
                                   'index': indexnames[choice]})
            df = pd.DataFrame(columns)
            df_str = df.to_csv(encoding='utf-8', index=False)
            href = "data:text/csv;charset=utf-8," + urllib.parse.quote(df_str)
            bar_type = 'bar'
        else:
            bar_type = 'overlay'
            if location[0] == 'grid':
                location = ['all', 'y', 'x',
                    'Contiguous United States (point estimates not available)',
                    0]

            # ts_series, ts_series_ninc, dsci = retrieveAreaData(arrays, choice) # <------------ For caching later, when we have more space
            ts_series, ts_series_ninc, dsci = data.getArea(crdict)  # <- Temporary fix

            # Save to file for download option
            df_dates = [pd.to_datetime(str(d)).strftime('%Y-%m') for
                        d in dates]
            columns = OrderedDict({'month': df_dates,
                                   'd0': list(ts_series_ninc[0]),
                                   'd1': list(ts_series_ninc[1]),
                                   'd2': list(ts_series_ninc[2]),
                                   'd3': list(ts_series_ninc[3]),
                                   'd4': list(ts_series_ninc[4]),
                                   'dsci': list(dsci),
                                   'function': 'Percent Area',
                                   'location':  label,
                                   'index': indexnames[choice]})
            df = pd.DataFrame(columns)
            df_str = df.to_csv(encoding='utf-8', index=False)
            href = "data:text/csv;charset=utf-8," + urllib.parse.quote(df_str)

        # Set up y-axis depending on selection
        if function != 'oarea':
            if 'p' in function:
                yaxis = dict(title='Percentiles', range=[0, 100])
            elif 'o' in function:
                yaxis = dict(range=[dmin, dmax], title='Index')

                # Center the color scale
                xmask = data.mask
                sd = float(data.dataset_interval.where(xmask == 1).std().compute().value) # Sheesh
                if 'eddi' in choice:
                    sd = sd*-1
                dmin = 3*sd
                dmax = 3*sd*-1

        # A few pieces to incorporate in to Index_Maps later
        if 'corr' in function:
            reverse = not reverse

        # The drought area graphs have there own configuration
        elif function == 'oarea':
            yaxis = dict(title='Percent Area (%)',
                         range=[0, 100],
                         hovermode='y')

        # Build the plotly readable dictionaries (Two types)
        if function != 'oarea':
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
        if function == 'oarea':
            if type(location[0]) is int:
                layout_copy['title'] = (indexnames[choice] +
                                        '<Br>' + 'Contiguous US ' +
                                        '(point estimates not available)')
            layout_copy['xaxis'] = dict(type='date')
            layout_copy['yaxis2'] = dict(title='<br>DSCI',
                                         range=[0, 500],
                                         anchor='x',
                                         overlaying='y',
                                         side='right',
                                         position=0.15,
                                         font=dict(size=8))
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

        return figure, href


# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()
