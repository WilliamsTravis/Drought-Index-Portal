# -*- coding: utf-8 -*-
"""
An Application to visualize time series of drought indices (or others soon).

Created on Fri Jan  4 12:39:23 2019

@author: Travis Williams

Sync Check: 01/20/2019
"""

# In[] Functions and Libraries
import os
import sys
import copy
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
from flask_caching import Cache
import gc
from inspect import currentframe, getframeinfo
import json
import numpy as np
import pandas as pd
from plotly import graph_objs as go
import psutil
# import redis
import time
import warnings
import xarray as xr

# Where should this go?
f = getframeinfo(currentframe()).filename
p = os.path.dirname(os.path.abspath(f))
os.chdir(p)

from functions import Index_Maps, outLine, readRaster
from functions import coordinateDictionaries, makeMap

# Check if we are working in Windows or Linux to find the data
if sys.platform == 'win32':
    data_path = 'f:/'
else:
    data_path = '/root/Sync'

# What to do with the mean of empty slice warning?
warnings.filterwarnings("ignore")

# In[] Create the DASH App object
app = dash.Dash(__name__)

# Go to stylesheet, styled after a DASH example (how to serve locally?)
app.css.append_css({'external_url':
                    'https://codepen.io/williamstravis/pen/maxwvK.css'})
app.scripts.config.serve_locally = True

# For the Loading screen
app.css.append_css({"external_url":
                    "https://codepen.io/williamstravis/pen/EGrWde.css"})

# Create Server Object
server = app.server

# Disable exceptions (attempt to speed things up)
app.config['suppress_callback_exceptions'] = True

# Create a simple file storeage cache, holds unique outputz of Index_Maps()
cache = Cache(config={'CACHE_TYPE': 'filesystem',
                      'CACHE_DIR': 'data/cache',
                      'CACHE_THRESHOLD': 2})

#cache = Cache(config={'CACHE_TYPE': 'redis',
#                      'CACHE_REDIS_URL': os.environ.get('localhost:6379')})

cache.init_app(server)

# In[] Drought and Climate Indices (looking to include any raster time series)
# Drought Severity Categories in percentile space
drought_cats = {0: [20, 30], 1: [10, 20], 2: [5, 10], 3: [2, 5], 4: [0, 2]}

# Index Paths (for npz files)
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
           {'label': 'EDDI-6', 'value': 'eddi6'}]

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
              'eddi6': 'Evaporative Demand Drought Index - 6 month'}

# Function options
function_options_perc = [{'label': 'Mean', 'value': 'pmean'},
                         {'label': 'Maximum', 'value': 'pmax'},
                         {'label': 'Minimum', 'value': 'pmin'},
                         {'label': 'Drought Severity Area', 'value':'parea'}]

function_options_orig = [{'label': 'Mean', 'value': 'omean'},
                         {'label': 'Maximum', 'value': 'omax'},
                         {'label': 'Minimum', 'value': 'omin'},
                         {'label': 'Coefficient of Variation', 'value': 'ocv'}]

function_names = {'pmean': 'Average Percentiles',
                  'pmax': 'Maxmium Percentile',
                  'pmin': 'Minimum Percentile',
                  'omean': 'Average Original Index Values',
                  'omax': 'Maximum Original Value',
                  'omin': 'Minimum Original Value',
                  'ocv': 'Coefficient of Variation for Original Values',
                  'parea': 'Drought Severity Area'}

################## Move to Maps Section #######################################
# Set up initial signal and raster to scatterplot conversion
# A source grid for scatterplot maps - will need more for optional resolution
source = xr.open_dataarray(os.path.join(data_path,
                                        "data/droughtindices/source_array.nc"))

# This converts array coordinates into array positions
londict, latdict, res = coordinateDictionaries(source)

# Some more support functions <------------------------------------------------ Create class, include coordinateDictionaries, grid, and other conversion functions
def pointToGrid(point):
    lon = point['points'][0]['lon']
    lat = point['points'][0]['lat']
    x = londict[lon]
    y = latdict[lat]
    gridid = grid.copy()[y, x]
    return gridid

# Let's say we also a list of gridids
def gridToPoint(grid, gridid):
    y, x = np.where(grid == gridid)
    lon = londict_rev[int(x[0])]
    lat = latdict_rev[int(y[0])]
    point = {'points': [{'lon': lon, 'lat': lat}]}
    return point

###############################################################################

#################### Clean Up #################################################
# For the county names - need to get a more complete data set
grid = np.load("data/npy/prfgrid.npz")["grid"]
mask = grid * 0 + 1

# County Data Frame and options
counties_df = pd.read_csv('data/tables/counties3.csv')
c_df = pd.read_csv('data/tables/unique_counties.csv')
rows = [r for idx, r in c_df.iterrows()]
county_options = [{'label': r['place'], 'value': r['grid']} for r in rows]
options_pos = {county_options[i]['label']: i for
               i in range(len(county_options))}
just_counties = [d['label'] for d in county_options]

# State options
states_df = counties_df[['STATE_NAME',
                         'STUSAB', 'FIPS State']].drop_duplicates().dropna()
states_df = states_df.sort_values('STUSAB')
rows = [r for idx, r in states_df.iterrows()]
state_options = [{'label': r['STUSAB'], 'value': r['FIPS State']} for
                  r in rows]
# state_options.insert(0, {'label': 'CONUS',
#                          'value': 'all'})
state_arrays = readRaster('data/rasters/us_states.tif', 1, -9999)[0]

# This is to associate grid ids with points, only once
# point_dict = {gridid: gridToPoint(grid, gridid) for  # Takes too long
#               gridid in grid[~np.isnan(grid)]}

# np.save('data/point_dict.npy', point_dict)
point_dict = np.load('data/npy/point_dict.npy').item()
grid_dict = {json.dumps(y): x for x, y in point_dict.items()}

# county_dict = {r['grid']: r['place'] for idx, r in counties_df.iterrows()}
# np.save('data/county_dict.npy', county_dict)
county_dict = np.load('data/npy/county_dict.npy').item()

# Get Max/Min data frame for time series colorscale
index_ranges = pd.read_csv('data/tables/index_ranges.csv')

###############################################################################
# For when EDDI before 1980 is selected
with np.load("data/npy/NA_overlay.npz") as data:  # <------------------------------ Redo this to look more professional
    na = data.f.arr_0
    data.close()

# Make the color scale stand out
for i in range(na.shape[0]):
    na[i] = na[i]*i

# Default click before the first click for any map  # <------------------------ Perhaps include the gridid in the click data?
default_click = {'points': [{'curveNumber': 0, 'lat': 40.0, 'lon': -105.75,  
                             'marker.color': 0, 'pointIndex': 0,
                             'pointNumber': 0, 'text': 'Boulder County, CO'}]}

# Default for click store (includes an index for most recent click)
default_clicks = [list(np.repeat(default_click.copy(), 4)), 0]
default_clicks = json.dumps(default_clicks)


# In[] The map
# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')

# For testing
source_signal = [[[2000, 2017], [1, 12]], 'Viridis', 'no']
source_choice = 'pdsi'

# Map types
maptypes = [{'label': 'Light', 'value': 'light'},
            {'label': 'Dark', 'value': 'dark'},
            {'label': 'Basic', 'value': 'basic'},
            {'label': 'Outdoors', 'value': 'outdoors'},
            {'label': 'Satellite', 'value': 'satellite'},
            {'label': 'Satellite Streets', 'value': 'satellite-streets'}]

colorscales = ['Default', 'Blackbody', 'Bluered', 'Blues', 'Earth', 'Electric',
               'Greens', 'Greys', 'Hot', 'Jet', 'Picnic', 'Portland',
               'Rainbow', 'RdBu', 'Reds', 'Viridis', 'RdWhBu',
               'RdWhBu (NOAA PSD Scale)', 'RdYlGnBu', 'BrGn']
color_options = [{'label': c, 'value': c} for c in colorscales]

# Year Marks for Slider
with xr.open_dataset(
        os.path.join(data_path,
                     'data/droughtindices/netcdfs/spi1.nc')) as data:
    sample_nc = data
    data.close()
max_date = sample_nc.time.data[-1]
del sample_nc
max_year = pd.Timestamp(max_date).year
max_month = pd.Timestamp(max_date).month
years = [int(y) for y in range(1948, max_year + 1)]
yearmarks = dict(zip(years, years))
monthmarks = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
for y in yearmarks:
    if y % 5 != 0:
        yearmarks[y] = ""


########################### Map Section #######################################
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
    margin=dict(
        l=55,
        r=35,
        b=65,
        t=90,
        pad=4),
    hovermode="closest",
    plot_bgcolor="#083C04",
    paper_bgcolor="#0D347C",
    legend=dict(font=dict(size=10, fontweight='bold'), orientation='h'),
    title='<b>Index Values/b>',
    mapbox=dict(
        accesstoken=mapbox_access_token,
        style="satellite-streets",
        center=dict(
            lon=-95.7,
            lat=37.1),
        zoom=2,
    )
)
###############################################################################

# In[]: Create App Layout
# For css later  <------------------------------------------------------------- Move all styling to css
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

# Create a Div maker
def divMaker(id_num, index='noaa'):
    div = html.Div([
                html.Div([
                    html.Div([
                            dcc.Tabs(id='choice_tab_{}'.format(id_num),
                                     value='index',
                                     style=tab_style,
                                     children=dcc.Tab(value='index',
                                                      label='Drought Index',
                                                      style=tablet_style,
                                                      selected_style=
                                                                tablet_style)),
                            dcc.Dropdown(id='choice_{}'.format(id_num),
                                         options=indices, value=index)],
                            style={'width': '30%',
                                   'float': 'left'}),
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
                                                  selected_style=tablet_style
                                                  )]),
                                html.Div(id='location_div_{}'.format(id_num),
                                         children=[
                                             dcc.Dropdown(
                                                id='location_{}'.format(id_num),
                                                options=county_options,
                                                clearable=False,
                                                multi=False,
                                                value=24098)])],
                                style={'width': '50%',
                                       'float': 'left',
                                       'display': ''}),
                        html.Button(id='update_map_{}'.format(id_num),
                                    children=['Update Map'],
                                    style={'width': '20%',
                                           'background-color': '#C7D4EA',
                                           'font-family': 'Times New Roman',
                                           'padding': '0px',
                                           'margin-top': '26'
                                           })],
                        className='row'),

                 dcc.Graph(id='map_{}'.format(id_num),
                           config={'staticPlot': False}),
                 html.Div([dcc.Graph(id='series_{}'.format(id_num))]),

              ], className='six columns')
    return div

app.layout = html.Div([   # <-------------------------------------------------- Line all brackets and parens up
             html.Div([
                # Sponsers
                html.A(html.Img(
                    src = ("https://github.com/WilliamsTravis/" +
                            "Pasture-Rangeland-Forage/blob/master/" +
                            "data/earthlab.png?raw=true"),
                    className='one columns',
                    style={
                        'height': '40',
                        'width': '100',
                        'float': 'right',
                        'position': 'static'
                           },
                                ),
                        href="https://www.colorado.edu/earthlab/",
                        target="_blank"
                        ),
                html.A(html.Img(
                    src = ('https://github.com/WilliamsTravis/Pasture-' +
                           'Rangeland-Forage/blob/master/data/' +
                           'wwa_logo2015.png?raw=true'),
                    className='one columns',
                    style={
                        'height': '50',
                        'width': '150',
                        'float': 'right',
                        'position': 'static',
                        },
                            ),
                        href = "http://wwa.colorado.edu/",
                        target = "_blank"
                            ),
                 html.A(html.Img(
                    src =( "https://github.com/WilliamsTravis/Pasture-" +
                          "Rangeland-Forage/blob/master/data/" +
                          "nidis.png?raw=true"),
                    className='one columns',
                    style={
                        'height': '50',
                        'width': '200',
                        'float': 'right',
                        'position': 'relative',
                        },
                            ),
                        href = "https://www.drought.gov/drought/",
                        target = "_blank"
                        ),
                 html.A(html.Img(
                    src = ("https://github.com/WilliamsTravis/Pasture-" +
                           "Rangeland-Forage/blob/master/data/" +
                           "cires.png?raw=true"),
                    className='one columns',
                    style={
                        'height': '50',
                        'width': '100',
                        'float': 'right',
                        'position': 'relative',
                        'margin-right': '20',
                        },
                            ),
                        href = "https://cires.colorado.edu/",
                        target = "_blank"
                        ),
                ],
                className = 'row'
                ),

        # Title
        html.Div([html.H1('Drought Index Comparison Portal'),
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
                            title='Click to collapse the options above'),
                html.Button(id="desc_button",
                            children="Project Description: Off",
                            title=("Toggle this on and off to show a " +
                                   "description of the project with " +
                                   "some instructions."),
                            style={'background-color': '#c7d4ea',
                                   'border-radius': '2px'}),
                html.Button(id="click_sync",
                            children="Location Syncing: On",
                            title=("Toggle on and off to sync the location " +
                                   "of the time series between each map"),
                            style={'background-color': '#c7d4ea',
                                   'border-radius': '2px',
                                   'margin-bottom': '30'})],
                style={'margin-bottom': '30',
                       'text-align': 'center'}),

        html.Div([
            html.Div([dcc.Markdown(id='description')],
                     style={'text-align':'center',
                            'width':'70%',
                            'margin':'0px auto'})],
            style={'text-align':'center',
                   'margin': '0 auto',
                   'width': '100%'}),

        # Year Slider
        html.Div(id='options',
                 children=[
                     html.Div([
                             html.H3(id='date_range',
                                     children=['Study Period Year Range']),
                             html.Div([dcc.RangeSlider(
                                                     id='year_slider',
                                                     value=[1990, max_year],
                                                     min=1948,
                                                     max=max_year,
                                                     updatemode='drag',
                                                     marks=yearmarks)],
                                      style={'margin-top': '0',
                                             'margin-bottom': '40'}),

                     # Month Slider
                     html.Div(id='month_slider',
                              children=[
                                      html.H3(id='month_range',
                                              children=['Month Range']),
                                      html.Div(id='month_slider_holder',
                                               children=[
                                               dcc.RangeSlider(id='month',
                                                               value=[1, 12],
                                                               min=1, max=12,
                                                               updatemode='drag',
                                                               marks=monthmarks)],
                                               style={'width': '35%'})],
                              style={'display': 'none'},
                              )],
                     className="row",
                     style={'margin-bottom': '55'}),

            # Options
            html.Div(id='options_div', 
                     children=[
                        # Maptype
                        html.Div([
                                html.H3("Map Type"),
                                 dcc.Dropdown(
                                        id="map_type",
                                        value="basic",
                                        options=maptypes)],
                                 className='two columns'),
        
                        # Function
                        html.Div([
                                 html.H3("Function"),
                                 dcc.Tabs(
                                    id='function_type', value='perc',
                                    style=tab_style,
                                    children=[
                                        dcc.Tab(label='Percentiles',
                                                value='perc',
                                                style=tablet_style,
                                                selected_style=tablet_style),
                                        dcc.Tab(label='Index Values',
                                                value='index',
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
                                    id='reverse', value='no',
                                    style=tab_style,
                                    children=[
                                        dcc.Tab(value='yes',
                                                label='Reversed',
                                                style=tab_style,
                                                selected_style=tablet_style),
                                        dcc.Tab(value='no',
                                                label="Not Reversed",
                                                style=tab_style,
                                                selected_style=tablet_style)]),
                                dcc.Dropdown(id='colors',
                                             options=color_options,
                                             value='Default')],
                                 className='three columns')],
                       className='row',
                       style={'margin-bottom': '50',
                              'margin-top': '0'}),
        ]),

        # Break
        html.Br(style={'line-height': '500%'}),

        # Submission Button
        html.Div([
            html.Button(id='submit',
                        children='Submit Options',
                        type='button',
                        style={'background-color': '#C7D4EA',
                               'border-radius': '2px',
                               'font-family': 'Times New Roman',})],
            style={'text-align': 'center'}),

        # Break line
        html.Hr(),

        # Four by Four Map Layout
        # Row 1
        html.Div([divMaker(1, 'pdsi'), divMaker(2, 'spei1')],
                 className='row'),

        # Row 2
        # html.Div([divMaker(3, 'spei6'), divMaker(4, 'spi3')],  # <----------- Consider only including two until we free more memory/get better machine
        #          className='row'),

        # Signals
        html.Div(id='signal', style={'display': 'none'}),
        html.Div(id='click_store',
                 children=default_clicks,
                 style={'display': 'none'}),
        html.Div(id='key_1', children='1', style={'display': 'none'}),
        html.Div(id='key_2', children='2', style={'display': 'none'}),
        html.Div(id='key_3', children='3', style={'display': 'none'}),
        html.Div(id='key_4', children='4', style={'display': 'none'}),
        html.Div(id='time_1', style={'display': 'none'}),
        html.Div(id='time_2', style={'display': 'none'}),
        html.Div(id='time_3', style={'display': 'none'}),
        html.Div(id='time_4', style={'display': 'none'}),
        html.Div(id='selection_time_1', style={'display': 'none'}),
        html.Div(id='selection_time_2', style={'display': 'none'}),
        html.Div(id='selection_time_3', style={'display': 'none'}),
        html.Div(id='selection_time_4', style={'display': 'none'}),
        html.Div(id='location_time_1', style={'display': 'none'}),
        html.Div(id='location_time_2', style={'display': 'none'}),
        html.Div(id='location_time_3', style={'display': 'none'}),
        html.Div(id='location_time_4', style={'display': 'none'}),
        html.Div(id='location_store', style={'display': 'none'}),
        html.Div(id='choice_store', style={'display': 'none'}),

        # The end!
        ], className='ten columns offset-by-one')


################ Options ######################################################
# Allow users to select a month range if the year slider is set to one year
@app.callback(Output('month_slider', 'style'),  # <---------------------------- Can we output the entire object with one callback?
              [Input('year_slider', 'value')])
def monthStyle(year_range):
    if year_range[0] == year_range[1]:
          style={}
    else:
          style={'display': 'none'}
    return style

# If users select the most recent, adjust available months
@app.callback(Output('month_slider_holder', 'children'),
              [Input('year_slider', 'value')])
def monthSlider(year_range):
    if year_range[0] == year_range[1]:
        if year_range[1] == max_year:
            month2 = max_month
            marks = {key: value for key, value in monthmarks.items() if
                     key <= month2}
        else:
            month2 = 12
            marks = monthmarks
        slider = dcc.RangeSlider(id='month',
                                 value=[1, month2],
                                 min=1, max=month2,
                                 updatemode='drag',
                                 marks=marks)
    else:

        slider = dcc.RangeSlider(id='month',
                                 value=[1, 12],
                                 min=1, max=12,
                                 updatemode='drag',
                                 marks=monthmarks)
    return [slider]

# Output text of the year range/single year selection
@app.callback(Output('date_range', 'children'),
              [Input('year_slider', 'value')])
def printYearRange(years):
    if years[0] != years[1]:
        string = 'Study Period Year Range: {} - {}'.format(years[0], years[1])
    else:
        string = 'Study Period Year Range: {}'.format(years[0])
    return string

# Output text of the month range/single month selection
@app.callback(Output('month_range', 'children'),
              [Input('month', 'value')])
def printMonthRange(months):
    if months[0] != months[1]:
        string = 'Month Range: {} - {}'.format(monthmarks[months[0]],
                                               monthmarks[months[1]])
    else:
        string = 'Month Range: {}'.format(monthmarks[months[0]])
    return string

# Toggle options on/off  <---------------------------------------------------- combine each button into one callback and improve style
@app.callback(Output('options', 'style'),
              [Input('toggle_options', 'n_clicks')])
def toggleOptions(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'display': 'none'}
    else:
        style = {}
    return style

# Change the color of on/off options button
@app.callback(Output('toggle_options', 'style'),
              [Input('toggle_options', 'n_clicks')])
def toggleToggleColor(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'background-color': '#a8b3c4',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman',}
    else:
        style = {'background-color': '#c7d4ea',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman',}
    return style

# Change the text of on/off options
@app.callback(Output('toggle_options', 'children'),
              [Input('toggle_options', 'n_clicks')])
def toggleOptionsLabel(click):
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Display Options: Off"
    else:
        children = "Display Options: On"
    return children

# change the color of on/off location syncing button  - for css
@app.callback(Output('click_sync', 'style'),
              [Input('click_sync', 'n_clicks')])
def toggleSyncColor(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'background-color': '#c7d4ea',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman',  # Specified in css?
                 }
    else:
        style = {'background-color': '#a8b3c4',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman',}
    return style

# change the text of on/off location syncing button
@app.callback(Output('click_sync', 'children'),
              [Input('click_sync', 'n_clicks')])
def toggleSyncLabel(click):
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Location Syncing: On"
    else:
        children = "Location Syncing: Off"
    return children

# Toggle description on/off
@app.callback(Output('description', 'children'),
              [Input('desc_button', 'n_clicks')])
def toggleDescription(click):
    if not click:
        click = 0
    if click % 2 == 0:
        children = ""
    else:
        children = open('data/description.txt').read()
    return children

# Change color of on/off description button
@app.callback(Output('desc_button', 'style'),
              [Input('desc_button', 'n_clicks')])
def toggleDescColor(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'background-color': '#a8b3c4',
                  'border-radius': '4px',
                  'font-family': 'Times New Roman',}
    else:
        style = {'background-color': '#c7d4ea',
                 'border-radius': '4px',
                 'font-family': 'Times New Roman',}
    return style

# Change text of on/off description button
@app.callback(Output('desc_button', 'children'),
              [Input('desc_button', 'n_clicks')])
def toggleDescLabel(click):
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Description: Off"
    else:
        children = "Description: On"
    return children

@app.callback(Output('function_choice', 'options'),
              [Input('function_type', 'value')])
def functionOptions(function_type):
    '''
    This uses the Percentile/Index tab to decide which functions options to
    display.
    '''
    if function_type == 'perc':
        return function_options_perc
    else:
        return function_options_orig


@app.callback(Output('function_choice', 'value'),
              [Input('function_type', 'value')])
def functionValue(function_type):
    '''
    This uses the Percentile/Index tab to decide which functions options to
    display.
    '''
    if function_type == 'perc':
        return 'pmean'
    else:
        return 'omean'


# In[]: App callbacks
@cache.memoize() # To be replaced with something more efficient
def retrieve_data(signal, function, choice):
    [time_range, colorscale, reverse_override] = signal
    data = Index_Maps(time_range, colorscale, reverse_override, choice)
    delivery = makeMap(data, function)
    return delivery

@app.callback(Output('location_store', 'children'),
              [Input('time_1', 'children'),
               Input('time_2', 'children'),
               # Input('time_3', 'children'), 
               # Input('time_4', 'children'),
               Input('location_time_1', 'children'), 
               Input('location_time_2', 'children'),
               # Input('location_time_3', 'children'),
               # Input('location_time_4', 'children'),
               Input('selection_time_1', 'children'),
               Input('selection_time_2', 'children'),
               # Input('selection_time_3', 'children'),
               # Input('selection_time_4', 'children'),
               Input('map_1', 'clickData'),
               Input('map_2', 'clickData'),
               # Input('map_3', 'clickData'),
               # Input('map_4', 'clickData'),
               Input('location_1', 'value'),
               Input('location_2', 'value'),
               # Input('location_3', 'value'),
               # Input('location_4', 'value'),
               Input('map_1', 'selectedData'),
               Input('map_2', 'selectedData'),
               # Input('map_3', 'selectedData'),
               # Input('map_4', 'selectedData')
               ])
def locationPicker(cl_time1, cl_time2,
                   # cl_time3, cl_time4,
                   loc_time1, loc_time2,
                   # loc_time3, loc_time4,
                   sl_time1, sl_time2,
                   # sl_time3, sl_time4,
                   cl1, cl2,
                   # cl3, cl4,
                   loc1, loc2,
                   # loc3, loc4,
                   sl1, sl2,
                   # sl3, sl4
                   ):
    '''
    Because there is no time stamp on these selections, we are making one
    ourselves. This is the list of selections (in various formats) and the list
    of times they were selected. The function will return the most recent
    selection to be used across all elements if syncing is on. 
    
    It would be best if the selection as in a standard format. Perhaps just
    x, y coords and a label.

    Also, to help unsync, I'm adding an index position of the click to the
    location object.
        
    '''
    times = [cl_time1, cl_time2,
             # cl_time3, cl_time4,
             loc_time1, loc_time2,
             # loc_time3, loc_time4,
             sl_time1, sl_time2,
             # sl_time3, sl_time4
             ]
    times = [0 if t is None else t for t in times]
    sels = [cl1, cl2,
            # cl3, cl4,
            loc1, loc2, 
            # loc3, loc4, 
            sl1, sl2, 
            # sl3, sl4
            ]
    sels = [default_click if s is None else s for s in sels]
    idx = times.index(max(times))
    location = sels[idx]

    # 1: Selection is a grid ID  # <------------------------------------------- Move to function
    if type(location) is int and len(str(location)) >= 3:
        county = counties_df['place'][counties_df.grid == location].item()
        y, x = np.where(grid == location)
        location = [int(y), int(x), county, idx]

    # 2: location is a list of states
    elif type(location) is list:
        # Empty, default to CONUS
        if len(location) == 0:
            location = ['state_mask', 'all', 'Contiguous United States', idx]

        elif len(location) == 1 and location[0] == 'all':
            location = ['state_mask', 'all', 'Contiguous United States', idx]

        # Single or multiple, not all or empty, state or list of states
        elif len(location) >= 1:
            # Return the mask, a flag, and the state names
            state = list(states_df['STUSAB'][
                         states_df['FIPS State'].isin(location)])
            if len(state) < 4:
                state = [states_df['STATE_NAME'][
                         states_df['STUSAB'] == s].item() for s in state]
            states = ", ".join(state)
            location = ['state_mask', str(location), states, idx]

    elif type(location) is str:
        location = ['state_mask', 'all', 'Contiguous United States', idx]

    # 4: Location is a point object
    elif type(location) is dict:
        if len(location['points']) == 1:
            lon = location['points'][0]['lon']
            lat = location['points'][0]['lat']
            x = londict[lon]
            y = latdict[lat]
            gridid = grid[y, x]
            counties = counties_df['place'][counties_df.grid == gridid]
            county = counties.unique()
            if len(county) == 0:
                label = ""
            else:
                label = county[0]
            location = [y, x, label, idx]

        elif len(location['points']) > 1:
            selections = location['points']
            y = list([latdict[d['lat']] for d in selections])
            x = list([londict[d['lon']] for d in selections])
            counties = np.array([d['text'][:d['text'].index(':')] for
                                 d in selections])
            county_df = counties_df[counties_df['place'].isin(
                                    list(np.unique(counties)))]

            # Use gradient to print NW and SE most counties as a range
            NW = county_df['place'][
                    county_df['gradient'] == min(county_df['gradient'])].item()
            SE = county_df['place'][
                    county_df['gradient'] == max(county_df['gradient'])].item()
            if NW != SE:
                label = NW + " to " + SE
            else:
                label = NW
            location = [str(y), str(x), label, idx]
    else:
        location = [50, 50, 'No Selection Found', idx]

    return location

# Output list of all index choices for syncing
@app.callback(Output('choice_store', 'children'),
              [Input('choice_1', 'value'),
               Input('choice_2', 'value'),
               # Input('choice_3', 'value'),
               # Input('choice_4', 'value')
               ])
def choiceStore(choice1, choice2): # choice3, choice4):
    return (json.dumps([choice1, choice2])) # choice3, choice4]))

# Store data in the cache and hide the signal to activate it in the hidden div
@app.callback(Output('signal', 'children'),
              [Input('submit', 'n_clicks')],
              [State('colors', 'value'),
               State('reverse', 'value'),
               State('year_slider', 'value'),
               State('month', 'value')])
def submitSignal(click, colorscale, reverse, year_range,
                 month_range):
    if not month_range:
        month_range = [1, 1]
    signal = [[year_range, month_range], colorscale, reverse]
    return json.dumps(signal)


# In[] Any callback with multiple instances goes here
for i in range(1, 3):
    @app.callback(Output('time_{}'.format(i), 'children'),
                  [Input('map_{}'.format(i), 'clickData')])
    def clickTime(click):
        clicktime = time.time()
        return(clicktime)

    @app.callback(Output('location_time_{}'.format(i), 'children'),
                  [Input('location_{}'.format(i), 'value')])
    def locationTime(location):
        loctime = time.time()
        return(loctime)

    @app.callback(Output('selection_time_{}'.format(i), 'children'),
                  [Input('map_{}'.format(i), 'selectedData')])
    def selectionTime(selection):
        selected_time = time.time()
        return(selected_time)
        
    @app.callback(Output('location_{}'.format(i), 'options'),
                  [Input('location_tab_{}'.format(i), 'value')])
    def displayLocOptions(tab_choice):
        if tab_choice == 'county':
            options = county_options
        else:
              options = state_options
        return options


    @app.callback(Output('location_{}'.format(i), 'value'),
                  [Input('location_tab_{}'.format(i), 'value')])
    def displayLocValue(tab_choice):
        if tab_choice == 'county':
            value = 24098
        else:
            value = 'all'
        return value
    
    
    @app.callback(Output('location_{}'.format(i), 'multi'),
                  [Input('location_tab_{}'.format(i), 'value')])
    def displayLoMulti(tab_choice):
        if tab_choice == 'county':
            multi = False
        else:
            multi = True
        return multi


    @app.callback(Output('location_{}'.format(i), 'placeholder'),
                  [Input('location_tab_{}'.format(i), 'value')])
    def displayLocHolder(tab_choice):
        if tab_choice == 'county':
            placeholder = 'Boulder County, CO'
        else:
            placeholder = 'Contiguous United States'
        return placeholder

    # @app.callback(Output('county_a{}'.format(i), 'options'),  # <------------ Dropdown label updates, old version
    #               [Input('time_1', 'children'),
    #                 Input('time_2', 'children'),
    #                 Input('time_3', 'children'),
    #                 Input('time_4', 'children'),
    #                 Input('location_time_1', 'children'),
    #                 Input('location_time_2', 'children'),
    #                 Input('location_time_3', 'children'),
    #                 Input('location_time_4', 'children'),
    #                 Input('selection_time_1', 'children'),
    #                 Input('selection_time_2', 'children'),
    #                 Input('selection_time_3', 'children'),
    #                 Input('selection_time_4', 'children'),
    #                 Input('signal', 'children'),
    #                 Input('choice_{}'.format(i), 'value'),
    #                 Input('choice_store', 'children')],
    #               [State('key_{}'.format(i), 'children'),
    #                 State('click_sync', 'children'),
    #                 State('map_1', 'clickData'),
    #                 State('map_2', 'clickData'),
    #                 State('map_3', 'clickData'),
    #                 State('map_4', 'clickData'),
    #                 State('locaiton_1', 'value'),
    #                 State('location_2', 'value'),
    #                 State('location_3', 'value'),
    #                 State('location_4', 'value'),
    #                 State('map_1', 'selectedData'),
    #                 State('map_2', 'selectedData'),
    #                 State('map_3', 'selectedData'),
    #                 State('map_4', 'selectedData')])
    # def dropOne(cl_time1, cl_time2, cl_time3, cl_time4,
    #             co_time1, co_time2, co_time3, co_time4,
    #             sl_time1, sl_time2, sl_time3, sl_time4,
    #             signal, choice, choice_store, key, sync,
    #             cl1, cl2, cl3, cl4, co1, co2, co3, co4,
    #             sl1, sl2, sl3, sl4):
    #     '''
    #     As a work around to updating synced dropdown labels
    #     and because we can't change the dropdown value with out
    #     creating an infinite loop, we are temporarily changing
    #     the options each time such that the value stays the same,
    #     but the one label to that value is the synced county name
    #     Selecting the right selection, do this first to prevent update
    #     if not syncing
    #     '''

    #     # List of all selections
    #     sels = [cl1, cl2, cl3, cl4, co1, co2, co3, co4, sl1, sl2, sl3, sl4]
    #     sels = [default_click if s is None else s for s in sels]
        
    #     # List of all selection times
    #     times = [cl_time1, cl_time2, cl_time3, cl_time4,
    #               co_time1, co_time2, co_time3, co_time4,
    #               sl_time1, sl_time2, sl_time3, sl_time4]

    #     # Index position of most recent selection
    #     sel_idx = times.index(max(times))

    #     # Find the current county value
    #     idx = int(key) - 1  # Graph ID
    #     co_sels = [co1, co2, co3, co4]
    #     sel = co_sels[idx]
    #     current_county = county_dict[sel]

    #     # Get the appropriate selection
    #     if 'On' not in sync:
    #         if sel_idx not in idx + np.array([0, 4, 8]):  # Associated sels
    #             raise PreventUpdate
    #         else:
    #             idxs = [idx, idx + 4, idx + 8]
    #             key_sels = list(np.array(sels)[idxs])
    #             key_times = list(np.array(times)[idxs])
    #             sel_idx = key_times.index(max(key_times))
    #             click = key_sels[sel_idx]

    #     else:
    #         # Get the most recent selection and continue
    #         click = sels[sel_idx]
        
    #     # Is it a grid id, single point or a list of points
    #     if type(click) is int:
    #         click = gridToPoint(grid, click)

    #     if type(click) is dict and len(click['points']) > 1:
    #         county = 'Multiple Counties'
    #     else:
    #         lon = click['points'][0]['lon']
    #         lat = click['points'][0]['lat']
    #         x = londict[lon]
    #         y = latdict[lat]
    #         gridid = grid[y, x]
    #         counties = counties_df['place'][counties_df.grid == gridid]
    #         county = counties.unique()

    #     options = county_options.copy()

    #     # if 'On' in sync:  # Try making dictionaries for all of these, too long
    #     current_idx = options_pos[current_county]
    #     options[current_idx]['label'] = county

    #     return options


    @app.callback(Output("map_{}".format(i), 'figure'),
                  [Input('choice_{}'.format(i), 'value'),
                   Input('map_type', 'value'),
                   Input('signal', 'children'),
                   Input('update_map_1', 'n_clicks'),
                   Input('update_map_2', 'n_clicks')],
                  [State('location_store', 'children'),
                   State('function_choice', 'value'),
                   State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children')])
    def makeGraph(choice, map_type, signal, click1, click2,
                   location, function, key, sync):
        if 'On' not in sync:
            sel_idx = location[3]
            idx = int(key) - 1
            if sel_idx not in idx + np.array([0, 2, 4]):  # <------------------[0, 4, 8] for the full panel
                raise PreventUpdate

        print("Rendering Map #{}".format(int(key)))

        # Clear memory space...what's the best way to do this?
        gc.collect()

        # Create signal for the global_store
        signal = json.loads(signal)

        # Collect and adjust signal
        [[year_range, month_range], colorscale, reverse_override] = signal

        # Get/cache data
        [array, arrays, dates, colorscale,
         dmax, dmin, reverse] = retrieve_data(signal, function, choice)

        #Filter by state
        if location:
            if location[0] == 'state_mask':
                flag, states, label, sel_idx = location
                if states != 'all':
                    states = json.loads(states)
                    state_mask = state_arrays.copy()
                    state_mask[~np.isin(state_mask, states)] = np.nan
                    state_mask = state_mask * 0 + 1
                else:
                    state_mask = mask
            else:
                state_mask = mask
        else:
            state_mask = mask
        array = array * state_mask

        # Check on Memory
        print("\nCPU: {}% \nMemory: {}%\n".format(psutil.cpu_percent(),
                                        psutil.virtual_memory().percent))

        # Individual array min/max
        amax = np.nanmax(array)
        amin = np.nanmin(array)

        # There's a lot of colorscale switching in the default settings
        if reverse_override == 'yes':
            reverse = not reverse

        # Because EDDI only extends back to 1980
        if len(arrays) == 0:
            source.data[0] = na
        else:
            source.data[0] = array * mask

        # Trying to free up space for more workers
        del array
        del arrays

        # Now all this
        dfs = xr.DataArray(source, name="data")
        pdf = dfs.to_dataframe()
        step = res
        to_bin = lambda x: np.floor(x / step) * step
        pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
        pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
        pdf['gridx'] = pdf['lonbin'].map(londict)
        pdf['gridy'] = pdf['latbin'].map(latdict)

        # For hover information
        grid2 = np.copy(grid)
        grid2[np.isnan(grid2)] = 0
        pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
        pdf = pd.merge(pdf, counties_df, how='inner')
        pdf['data'] = pdf['data'].astype(float)
        pdf['printdata'] = (pdf['place'] + ":<br>    " +
                            pdf['data'].round(3).apply(str))

        df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
        df = df_flat[np.isfinite(df_flat['data'])]

        # There are several possible date ranges to display
        y1 = year_range[0]
        y2 = year_range[1]
        m1 = month_range[0]
        m2 = month_range[1]

        if y1 != y2:
            date_print = '{} - {}'.format(y1, y2)
        elif y1 == y2 and m1 != m2:
            date_print = "{} - {}, {}".format(monthmarks[m1],
                                              monthmarks[m2], y1)
        else:
            date_print = "{}, {}".format(monthmarks[m1], y1)

        # The y-axis depends on the chosen function
        if 'p' in function:
            yaxis = dict(title='Percentiles',
                          range=[0, 100])
        elif 'o' in function and 'cv' not in function:
            dmin = index_ranges['min'][index_ranges['index'] == choice]
            dmax = index_ranges['max'][index_ranges['index'] == choice]
            yaxis = dict(range=[dmin, dmax],
                          title='Index')
        else:
            yaxis = dict(title='C.V.')

        # Create the scattermapbox object
        data = [
            dict(
                type='scattermapbox',
                lon=df['lonbin'],
                lat=df['latbin'],
                text=df['printdata'],
                mode='markers',
                hoverinfo='text',
                hovermode='closest',
                marker=dict(
                    colorscale=colorscale,
                    reversescale=reverse,
                    color=df['data'],
                    cmax=amax,
                    cmin=amin,
                    opacity=0.85,
                    size=5,
                    colorbar=dict(
                        textposition="auto",
                        orientation="h",
                        font=dict(size=15,
                                  fontweight='bold')
                    )
                )
            )]

        layout_copy = copy.deepcopy(layout)
        layout_copy['mapbox'] = dict(
            accesstoken=mapbox_access_token,
            style=map_type,
            center=dict(lon=-95.7, lat=37.1),
            zoom=2)
        layout_copy['yaxis'] = yaxis
        layout_copy['title'] = (indexnames[choice] + '<br>' +
                                function_names[function] + ': ' +
                                date_print)

        figure = dict(data=data, layout=layout_copy)
        return figure


    @app.callback(Output('series_{}'.format(i), 'figure'),
                  [Input('submit', 'n_clicks'),
                   Input('signal', 'children'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('choice_store', 'children'),
                   Input('location_store', 'children'),
                   Input('click_sync', 'children')],
                  [State('key_{}'.format(i), 'children'),
                   State('function_choice', 'value')])
    def makeSeries(submit, signal, choice, choice_store, location,
                   sync, key, function):
        '''
        Each callback is called even if this isn't synced...It would require
          a whole new set of callbacks to avoid the lag from that. Also, the
          synced click process is too slow...what can be done?
        '''
        # Get the appropriate selection
        sel_idx = location[3]
        if 'On' not in sync:
            idx = int(key) - 1  # Graph ID
            if sel_idx not in idx + np.array([0, 2, 4]):  # [0, 4, 8] for the full panel
                raise PreventUpdate

        # Create signal for the global_store
        choice_store = json.loads(choice_store)
        signal = json.loads(signal)

        # Collect signals
        [[year_range, month_range], colorscale, reverse_override] = signal

        # Get/cache data
        [array, arrays, dates, colorscale,
         dmax, dmin, reverse] = retrieve_data(signal, function, choice)

        # There's a lot of color scale switching in the default settings...
        # ...so sorry any one who's trying to figure this out, I will fix this
        if reverse_override == 'yes':
            reverse = not reverse

        # From the location, whatever it is, we need only need y, x and a label
        # Whether x and y are singular or vectors
        def timeSeries(location, arrays):   # <-------------------------------- Move to functions
            if location[0] != 'state_mask':
                y, x, label, sel_idx = location
                if type(y) is int:
                    timeseries = np.array([round(a[y, x], 4) for a in arrays])
                else:
                    x = json.loads(x)
                    y = json.loads(y)
                    timeseries = np.array([round(np.nanmean(a[y, x]), 4) for
                                           a in arrays])
            else:
                flag, states, label, sel_idx = location
                if states != 'all':
                    states = json.loads(states)
                    state_mask = state_arrays.copy()
                    state_mask[~np.isin(state_mask, states)] = np.nan
                    state_mask = state_mask * 0 + 1
                else:
                    state_mask = mask
                arrays = arrays*state_mask
                timeseries = np.array([round(np.nanmean(a), 4) for a in arrays])

            return [timeseries, label]

        # If the function is parea, we plot five overlapping timeseries
        if function != 'parea':
            timeseries, label = timeSeries(location, arrays)
            bar_type = 'bar'
        else:
            dm_arrays = arrays.copy()
            bar_type = 'overlay'
            ts_series = {}
            for i in range(5):  # 5 drought categories
                ts_series[i] = timeSeries(location, dm_arrays[i])

        # Format dates
        dates = [pd.to_datetime(str(d)) for d in dates]
        dates = [d.strftime('%Y-%m') for d in dates]

        # The y-axis depends on the chosen function
        if 'p' in function and function != 'parea':
            yaxis = dict(title='Percentiles',
                         range=[0, 100])
        elif 'o' in function and 'cv' not in function:
            yaxis = dict(range=[dmin, dmax],
                          title='Index')
            sd = np.nanstd(arrays)
            if 'eddi' in choice:
                sd = sd*-1
            dmin = 3*sd
            dmax = 3*sd*-1
        elif function == 'parea':
            yaxis = dict(title='Percent Area',
                          range=[0, 100])
        else:
            yaxis = dict(title='C.V.')

        # Trying to free up space for more workers
        del array
        del arrays

        # Build the data dictionaries that plotly reads
        if function != 'oarea':
            data = [
                dict(
                    type='bar',
                    x=dates,
                    y=timeseries,
                    marker=dict(color=timeseries,
                                colorscale=colorscale,
                                reversescale=reverse,
                                autocolorscale=False,
                                cmin=dmin,
                                cmax=dmax,
                                line=dict(width=0.2, color="#000000")))]
        else:
############################# Construction Zone ###############################
            label = ts_series[0][1] # these are all too consistent
            xs = [i for i in range(len(dates))]
            ts = [ts_series[i][0] for i in range(5)]
            colors = ['#ffff00', '#fcd37f', '#ffaa00', '#e60000', '#730000']
            widths = list(np.linspace(1, .25, 5))
            cats = ['D0 (dry)', 'D1 (moderate)', 'D2 (severe)',
                    'D3 (extreme)', 'D4 (exceptional)']
            data = []
            for i in range(5):
                trace = go.Bar(x=xs, y=ts[i], name=cats[i], width=widths[i],
                               marker=dict(
                                        color=colors[i],
                                        line=dict(width=.2,
                                                  color="#000000")))
                data.append(trace)
###############################################################################

        # Copy and customize Layout
        layout_copy = copy.deepcopy(layout)
        layout_copy['title'] = (indexnames[choice] +
                                "<Br>" + label)
        layout_copy['plot_bgcolor'] = "white"
        layout_copy['paper_bgcolor'] = "white"
        layout_copy['height'] = 250
        layout_copy['yaxis'] = yaxis
        # layout_copy['xaxis'] = dict(tickvals=xs,
        #                             ticktext=dates)
        layout_copy['hovermode'] = 'compare'
        layout_copy['barmode'] = bar_type
        layout_copy['legend'] = dict(orientation='h',
                                     y=-.5, markers=dict(size=8),
                                     font=dict(size=8))
        layout_copy['titlefont']['color'] = '#636363'
        layout_copy['font']['color'] = '#636363'

        figure = dict(data=data, layout=layout_copy)

        return figure


# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()
