# -*- coding: utf-8 -*-
"""
Just an app to visualize raster time series.

Created on Fri Jan  4 12:39:23 2019

@author: User

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
import pandas as pd
import numpy as np
import psutil
import time
import warnings
import xarray as xr

# Where should this go?
f = getframeinfo(currentframe()).filename
p = os.path.dirname(os.path.abspath(f))
os.chdir(p)

import functions
from functions import Index_Maps, makeMap, outLine

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

# Create four simple caches, each holds one large array, one for each map
cache = Cache(config={'CACHE_TYPE': 'filesystem',
                      'CACHE_DIR': 'data/cache',
                      'CACHE_THRESHOLD': 4})
cache.init_app(server)

# In[] Drought and Climate Indices (looking to include any raster time series)
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
function_options = [{'label': 'Mean - Percentiles', 'value': 'mean_perc'},
                    {'label': 'Maximum - Percentiles', 'value': 'max'},
                    {'label': 'Minimum - Percentiles', 'value': 'min'},
                    {'label': 'Mean - Original Values',
                     'value': 'mean_original'},
                    {'label': 'Maximum - Original Values', 'value': 'omax'},
                    {'label': 'Minimum - Original Values', 'value': 'omin'},
                    {'label': 'Coefficient of Variation - Original Value',
                     'value': 'ocv'}]

function_names = {'mean_perc': 'Average Percentiles',
                  'max': 'Maxmium Percentile',
                  'min': 'Minimum Percentile',
                  'mean_original': 'Average Original Index Values',
                  'omax': 'Maximum Original Value',
                  'omin': 'Minimum Original Value',
                  'ocv': 'Coefficient of Variation for Original Values'}

# Set up initial signal and raster to scatterplot conversion
# A source grid for scatterplot maps - will need more for optional resolution
source = xr.open_dataarray(os.path.join(data_path,
                                        "data/droughtindices/source_array.nc"))

# This converts array coordinates into array positions
londict, latdict, res = functions.coordinateDictionaries(source)
londict_rev = {value: key for key, value in londict.items()}
latdict_rev = {value: key for key, value in latdict.items()}


# Some more support functions
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

# For the county names - need to get a more complete data set
grid = np.load(data_path + "/data/prfgrid.npz")["grid"]
mask = grid*0+1

# County Data Frame
# counties_df = pd.read_csv("data/counties.csv")
# counties_df = counties_df[['grid', 'county', 'state']]
# counties_df['place'] = (counties_df['county'] +
#                         ' County, ' + counties_df['state'])
# #  This will append a gradient value to each cell entry for labeling
# # Only need to do this once
# gradient = mask.copy()
# for i in range(gradient.shape[0]):
#     for j in range(gradient.shape[1]):
#         gradient[i, j] = i*j
# gradient = gradient * mask
# gradient_dict = dict(zip(list(grid.flatten()), list(gradient.flatten())))
# counties_df['gradient'] = counties_df['grid'].apply(lambda x: gradient_dict[x])
# counties_df.to_csv("data/counties2.csv", index=False)

counties_df = pd.read_csv("data/counties2.csv")
c_df = pd.read_csv('data/unique_counties.csv')
rows = [r for idx, r in c_df.iterrows()]
county_options = [{'label': r['place'], 'value': r['grid']} for r in rows]
options_pos = {county_options[i]['label']: i for
               i in range(len(county_options))}
just_counties = [d['label'] for d in county_options]

# This is to associate grid ids with points, only once
# point_dict = {gridid: gridToPoint(grid, gridid) for  # Takes too long
#               gridid in grid[~np.isnan(grid)]}
# np.save('data/point_dict.npy', point_dict)
point_dict = np.load('data/point_dict.npy').item()        
grid_dict = {json.dumps(y): x for x, y in point_dict.items()}

# county_dict = {r['grid']: r['place'] for idx, r in counties_df.iterrows()}
# np.save('data/county_dict.npy', county_dict)
county_dict = np.load('data/county_dict.npy').item()

# Get Max/Min data frame for time series colorscale
index_ranges = pd.read_csv('data/index_ranges.csv')

# For when EDDI before 1980 is selected
with np.load("data/NA_overlay.npz") as data:
    na = data.f.arr_0
    data.close()

# Make the color scale stand out
for i in range(na.shape[0]):
    na[i] = na[i]*i

# Default click before the first click for any map
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
source_signal = [[[2000, 2017], [1, 12]], 'mean_perc', 'Viridis', 'no', 'pdsi']

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


# Map Layout:
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


# In[]: Create App Layout
# Create a Div maker
def divMaker(id_num, index='noaa'):
    div = html.Div([
                html.Div([
                    html.Div([dcc.Dropdown(id='choice_{}'.format(id_num),
                                           options=indices, value=index)],
                             style={'width': '30%',
                                    'float': 'left'}),
                    html.Div([dcc.Dropdown(id='county_{}'.format(id_num),
                                           options=county_options,
                                           clearable=False,
                                           value=24098.0)],
                             style={'width': '30%',
                                    'float': 'left'})],
                    className='row'),
                 dcc.Graph(id='map_{}'.format(id_num),
                           config={'staticPlot': False}),
                 html.Div([dcc.Graph(id='series_{}'.format(id_num))]),

              ], className='six columns')
    return div

app.layout = html.Div([
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
                                    'border-radius': '4px'}),
                html.Button(id="click_sync",
                            children="Location Syncing: On",
                            title=("Toggle on and off to sync the location " +
                                   "of the time series between each map"),
                            style={'background-color': '#c7d4ea',
                                   'border-radius': '4px',
                                   'margin-bottom': '30'})],
                style={'margin-bottom': '30',
                       'text-align': 'center'}),
        html.Div([html.Div([dcc.Markdown(id='description')],
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
                                 value=[1985, max_year],
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
                              )
                     ],
                     className="row",
                     style={'margin-bottom': '55'}),

            # Options
            html.Div([
                # Maptype
                html.Div([
                        html.H3("Map Type"),
                         dcc.RadioItems(
                                id="map_type",
                                value="basic",
                                options=maptypes)],
                         className='two columns'),

                # Function
                html.Div([
                         html.H3("Function"),
                         dcc.RadioItems(id='function_choice',
                                        options=function_options,
                                        value='mean_perc')],
                         className='three columns'),

                # Customize Color Scales
                html.Div([
                        html.H3('Color Gradient'),
                        dcc.Dropdown(id='colors',
                                     options=color_options,
                                     value='Default'),
                        html.H4("Reverse"),
                        dcc.RadioItems(id='reverse',
                                       options=[{'label': 'Yes',
                                                 'value': 'yes'},
                                                {'label': 'No',
                                                 'value': 'no'}],
                                       value='no')],
                         className='two columns'),
                ],
               className='row',
               style={'margin-bottom': '50',
                      'margin-top': '0'}),
        ]),

        # Break line
        html.Hr(),

        # Submission Button
        html.Div([html.Button(id='submit',
                    children='Submit Options',
                    type='button',
                    title='It updates automatically without this.',
                    style={'background-color':'rgb(3,101,224)',
                           'color': 'white',
                           'text-align':'center',
                           'margin': '0 auto',
                           'max-width': '20%',
                           'text-shadow': outLine('black', .5)})],
                    style={'text-align':'center',
                           'margin': '0 auto',
                           'width': '100%',
                           'margin-buttom': '50',}),

        # Break
        html.Br(style={'line-height': '150%'}),

        # Four by Four Map Layout
        # Row 1
        html.Div([divMaker(1, 'pdsi'), divMaker(2, 'spei1')],
                 className='row'),

        # Row 2
        html.Div([divMaker(3, 'spei6'), divMaker(4, 'spi3')],
                 className='row'),

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
        html.Div(id='county_time_1', style={'display': 'none'}),
        html.Div(id='county_time_2', style={'display': 'none'}),
        html.Div(id='county_time_3', style={'display': 'none'}),
        html.Div(id='county_time_4', style={'display': 'none'}),
        # html.Div(id='cache_check_1', style={'display': 'none'}),
        # html.Div(id='cache_check_2', style={'display': 'none'}),
        # html.Div(id='cache_check_3', style={'display': 'none'}),
        # html.Div(id='cache_check_4', style={'display': 'none'}),
        html.Div(id='choice_store', style={'display': 'none'}),

        # The end!
        ], className='ten columns offset-by-one')


# In[]: App callbacks
@cache.memoize() # To be replaced with something more efficient
def retrieve_data(signal, choice):
    return makeMap(signal, choice)

# def chooseCache(key, signal, choice):
#     if key == '1':
#         return retrieve_data1(signal, choice)
#     elif key == '2':
#         return retrieve_data2(signal, choice)
#     elif key == '3':
#         return retrieve_data3(signal, choice)
#     else:
#         return retrieve_data4(signal, choice)


# Store data in the cache and hide the signal to activate it in the hidden div
@app.callback(Output('signal', 'children'),
              [Input('submit', 'n_clicks')],
              [State('function_choice', 'value'),
               State('colors', 'value'),
               State('reverse', 'value'),
               State('year_slider', 'value'),
               State('month', 'value'),
               State('map_type', 'value')])
def submitSignal(click, function, colorscale, reverse, year_range,
                 month_range, map_type):
    if not month_range:
        month_range = [1, 1]
    signal = [[year_range, month_range], function,
                       colorscale, reverse, map_type]
    return json.dumps(signal)


# Allow users to select a month range if the year slider is set to one year
@app.callback(Output('month_slider', 'style'),
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

# Toggle options on/off
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
                  'border-radius': '4px'}
    else:
        style = {'background-color': '#c7d4ea',
                  'border-radius': '4px'}
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

# change the color of on/off location syncing button
@app.callback(Output('click_sync', 'style'),
              [Input('click_sync', 'n_clicks')])
def toggleSyncColor(click):
    if not click:
        click = 0
    if click % 2 == 0:
        style = {'background-color': '#c7d4ea',
                 'border-radius': '4px'}
    else:
        style = {'background-color': '#a8b3c4',
                  'border-radius': '4px'}
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
                  'border-radius': '4px'}
    else:
        style = {'background-color': '#c7d4ea',
                 'border-radius': '4px'}
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


# Output list of all index choices for syncing
@app.callback(Output('choice_store', 'children'),
              [Input('choice_1', 'value'),
               Input('choice_2', 'value'),
               Input('choice_3', 'value'),
               Input('choice_4', 'value')])
def choiceStore(choice1, choice2, choice3, choice4):
    return (json.dumps([choice1, choice2, choice3, choice4]))


# In[] Any callback with four parts goes here
for i in range(1, 5):
    @app.callback(Output('time_{}'.format(i), 'children'),
                  [Input('map_{}'.format(i), 'clickData')])
    def clickTime(click):
        clicktime = time.time()
        return(clicktime)


    @app.callback(Output('county_time_{}'.format(i), 'children'),
                  [Input('county_{}'.format(i), 'value')])
    def countyTime(county):
        countytime = time.time()
        return(countytime)

    @app.callback(Output('selection_time_{}'.format(i), 'children'),
                  [Input('map_{}'.format(i), 'selectedData')])
    def selectionTime(selection):
        selected_time = time.time()
        return(selected_time)

    @app.callback(Output('county_{}'.format(i), 'options'),
                  [Input('time_1', 'children'),
                   Input('time_2', 'children'),
                   Input('time_3', 'children'),
                   Input('time_4', 'children'),
                   Input('county_time_1', 'children'),
                   Input('county_time_2', 'children'),
                   Input('county_time_3', 'children'),
                   Input('county_time_4', 'children'),
                   Input('selection_time_1', 'children'),
                   Input('selection_time_2', 'children'),
                   Input('selection_time_3', 'children'),
                   Input('selection_time_4', 'children'),
                   Input('signal', 'children'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('choice_store', 'children')],
                  [State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children'),
                   State('map_1', 'clickData'),
                   State('map_2', 'clickData'),
                   State('map_3', 'clickData'),
                   State('map_4', 'clickData'),
                   State('county_1', 'value'),
                   State('county_2', 'value'),
                   State('county_3', 'value'),
                   State('county_4', 'value'),
                   State('map_1', 'selectedData'),
                   State('map_2', 'selectedData'),
                   State('map_3', 'selectedData'),
                   State('map_4', 'selectedData')])
    def dropOne(cl_time1, cl_time2, cl_time3, cl_time4,
                co_time1, co_time2, co_time3, co_time4,
                sl_time1, sl_time2, sl_time3, sl_time4,
                signal, choice, choice_store, key, sync,
                cl1, cl2, cl3, cl4, co1, co2, co3, co4,
                sl1, sl2, sl3, sl4):
        '''
        As a work around to updating synced dropdown labels
        and because we can't change the dropdown value with out
        creating an infinite loop, we are temporarily changing
        the options each time such that the value stays the same,
        but the one label to that value is the synced county name
        Selecting the right selection, do this first to prevent update
        if not syncing
        '''

        # List of all selections
        sels = [cl1, cl2, cl3, cl4, co1, co2, co3, co4, sl1, sl2, sl3, sl4]
        sels = [default_click if s is None else s for s in sels]
        
        # List of all selection times
        times = [cl_time1, cl_time2, cl_time3, cl_time4,
                 co_time1, co_time2, co_time3, co_time4,
                 sl_time1, sl_time2, sl_time3, sl_time4]

        # Index position of most recent selection
        sel_idx = times.index(max(times))

        # Find the current county value
        idx = int(key) - 1  # Graph ID
        co_sels = [co1, co2, co3, co4]
        sel = co_sels[idx]
        current_county = county_dict[sel]

        # Get the appropriate selection
        if 'On' not in sync:
            if sel_idx not in idx + np.array([0, 4, 8]):  # Associated sels
                raise PreventUpdate
            else:
                idxs = [idx, idx + 4, idx + 8]
                key_sels = list(np.array(sels)[idxs])
                key_times = list(np.array(times)[idxs])
                sel_idx = key_times.index(max(key_times))
                click = key_sels[sel_idx]

        else:
            # Get the most recent selection and continue
            click = sels[sel_idx]
        
        # Is it a grid id, single point or a list of points
        if type(click) is int:
            click = gridToPoint(grid, click)

        if type(click) is dict and len(click['points']) > 1:
            county = 'Multiple Counties'
        else:
            lon = click['points'][0]['lon']
            lat = click['points'][0]['lat']
            x = londict[lon]
            y = latdict[lat]
            gridid = grid[y, x]
            counties = counties_df['place'][counties_df.grid == gridid]
            county = counties.unique()

        options = county_options.copy()

        # if 'On' in sync:  # Try making dictionaries for all of these, too long
        current_idx = options_pos[current_county]
        options[current_idx]['label'] = county

        return options


    @app.callback(Output("map_{}".format(i), 'figure'),
                  [Input('choice_{}'.format(i), 'value'),
                   Input('signal', 'children')],
                  [State('key_{}'.format(i), 'children')])
    def makeGraph(choice, signal, key):

        print("Rendering Map #{}".format(int(key)))

        # Clear memory space...what's the best way to do this?
        gc.collect()


        # Create signal for the global_store
        signal = json.loads(signal)

        # Collect and adjust signal
        [[year_range, month_range], function, colorscale,
         reverse_override, map_type] = signal
        signal.pop(4)

        # Split the time range up
        y1 = year_range[0]
        y2 = year_range[1]
        m1 = month_range[0]
        m2 = month_range[1]

        # Get data
        [[array, arrays, dates],
         colorscale, dmax, dmin, reverse] = retrieve_data(signal, choice)
        print("\nCPU: {}% \nMemory: {}%\n".format(psutil.cpu_percent(),
                                       psutil.virtual_memory().percent))

        # There's a lot of colorscale switching in the default settings
        if reverse_override == 'yes':
            reverse = not reverse

        # Individual array min/max
        amax = np.nanmax(array)
        amin = np.nanmin(array)

        # Because EDDI only extends back to 1980
        if len(arrays) == 0:
            source.data[0] = na
            colorscale = [[0.0, 'rgb(50, 50, 50)'],
                          [1.0, 'rgb(50, 50, 50)']]
        else:
            source.data[0] = array * mask

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
        pdf['data'] = pdf['data'].astype(float).round(3)
        pdf['printdata'] = pdf['place'] + ":<br>     " + pdf['data'].apply(str)

        df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
        df = df_flat[np.isfinite(df_flat['data'])]

        # Trying to free up space for more workers
        del array
        del arrays

        # There are several possible date ranges to display
        if y1 != y2:
            date_print = '{} - {}'.format(y1, y2)
        elif y1 == y2 and m1 != m2:
            date_print = "{} - {}, {}".format(monthmarks[m1],
                                              monthmarks[m2], y1)
        else:
            date_print = "{}, {}".format(monthmarks[m1], y1)

        # The y-axis depends on the chosen function
        labels = {d['value']: d['label'] for d in function_options}
        if 'Percentiles' in labels[function]:
            yaxis = dict(title='Percentiles',
                         range=[0, 100])
            df['data'] = df['data'] * 100
            amin = amin * 100
            amax = amax * 100
        elif 'Original' in labels[function]:
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
                   Input('time_1', 'children'),
                   Input('time_2', 'children'),
                   Input('time_3', 'children'),
                   Input('time_4', 'children'),
                   Input('county_time_1', 'children'),
                   Input('county_time_2', 'children'),
                   Input('county_time_3', 'children'),
                   Input('county_time_4', 'children'),
                   Input('selection_time_1', 'children'),
                   Input('selection_time_2', 'children'),
                   Input('selection_time_3', 'children'),
                   Input('selection_time_4', 'children'),
                   Input('signal', 'children'),
                   Input('choice_{}'.format(i), 'value'),
                   Input('choice_store', 'children')],
                  [State('key_{}'.format(i), 'children'),
                   State('click_sync', 'children'),
                   State('map_1', 'clickData'),
                   State('map_2', 'clickData'),
                   State('map_3', 'clickData'),
                   State('map_4', 'clickData'),
                   State('county_1', 'value'),
                   State('county_2', 'value'),
                   State('county_3', 'value'),
                   State('county_4', 'value'),
                   State('map_1', 'selectedData'),
                   State('map_2', 'selectedData'),
                   State('map_3', 'selectedData'),
                   State('map_4', 'selectedData'),
                   ])
    def makeSeries(submit,
                   cl_time1, cl_time2, cl_time3, cl_time4,
                   co_time1, co_time2, co_time3, co_time4,
                   sl_time1, sl_time2, sl_time3, sl_time4,
                   signal, choice, choice_store,
                   key, sync,
                   cl1, cl2, cl3, cl4, co1, co2, co3, co4,
                   sl1, sl2, sl3, sl4
                   ):
        '''
        Each callback is called even if this isn't synced...It would require
         a whole new set of callbacks to avoid the lag from that. Also, the
         synced click process is too slow...what can be done?
        '''

        # Selecting the right selection, do this first to prevent update
        # if not syncing
        # List of all selections
        sels = [cl1, cl2, cl3, cl4, co1, co2, co3, co4, sl1, sl2, sl3, sl4]
        sels = [default_click if s is None else s for s in sels]
        
        # List of all selection times
        times = [cl_time1, cl_time2, cl_time3, cl_time4,
                 co_time1, co_time2, co_time3, co_time4,
                 sl_time1, sl_time2, sl_time3, sl_time4]

        # Index position of most recent selection
        sel_idx = times.index(max(times))

        # Get the appropriate selection
        if 'On' not in sync:
            idx = int(key) - 1  # Graph ID
            if sel_idx not in idx + np.array([0, 4, 8]):  # Associated sels
                raise PreventUpdate
            else:
                idxs = [idx, idx + 4, idx + 8]
                key_sels = list(np.array(sels)[idxs])
                key_times = list(np.array(times)[idxs])
                sel_idx = key_times.index(max(key_times))
                click = key_sels[sel_idx]

        else:
            # Get the most recent selection and continue
            click = sels[sel_idx] 

        #  Check if we are syncing clicks, prevent update if needed
        # print("Rendering Time Series #" + key)
        choice_store = json.loads(choice_store)

        # Create signal for the global_store
        signal = json.loads(signal)

        # Collect signals
        [[year_range, month_range], function, colorscale,
         reverse_override, map_type] = signal
        signal.pop(4)

        # Get data - check which cache first
        [[array, arrays, dates],
         colorscale, dmax, dmin, reverse] = retrieve_data(signal, choice)

        # There's a lot of colorscale switching in the default settings...
        # ...so sorry any one who's trying to figure this out, I will fix this
        if reverse_override == 'yes':
            reverse = not reverse

        # Is it a grid id, single point or a list of points
        if type(click) is int:
            click = gridToPoint(grid, click)

        if type(click) is dict and len(click['points']) > 1:
            selections = click['points']
            ys = np.array([latdict[d['lat']] for d in selections])
            xs = np.array([londict[d['lon']] for d in selections])
            timeseries = np.array([round(np.nanmean(a[ys, xs]), 4) for
                                   a in arrays])
            counties = np.array([d['text'][:d['text'].index(':')] for
                                   d in selections])
            county_df = counties_df[counties_df['place'].isin(
                                    list(np.unique(counties)))]
            # Use grid id to print NW and SW most counties as a range
            NW = county_df['place'][
                    county_df['gradient'] == min(county_df['gradient'])].item()
            SE = county_df['place'][
                    county_df['gradient'] == max(county_df['gradient'])].item()
            if NW != SE:
                county = NW + " to " + SE
            else:
                county = NW
        else:
            lon = click['points'][0]['lon']
            lat = click['points'][0]['lat']
            x = londict[lon]
            y = latdict[lat]
            gridid = grid[y, x]
            counties = counties_df['place'][counties_df.grid == gridid]
            county = counties.unique()
            if len(county) == 0:
                county = ""
            else:
                county = county[0]
            timeseries = np.array([round(a[y, x], 4) for a in arrays])

        # Get time series
        dates = [pd.to_datetime(str(d)) for d in dates]
        dates = [d.strftime('%Y-%m') for d in dates]

        # The y-axis depends on the chosen function
        labels = {d['value']: d['label'] for d in function_options}
        if 'Percentiles' in labels[function]:
            yaxis = dict(title='Percentiles',
                         range=[0, 100])
            timeseries = timeseries * 100
            dmin = dmin * 100
            dmax = dmax * 100
        elif 'Original' in labels[function]:
            yaxis = dict(range=[dmin, dmax],
                         title='Index')
            sd = np.nanstd(arrays)
            if 'eddi' in choice:
                sd = sd*-1
            dmin = 3*sd
            dmax = -3*sd
        else:
            yaxis = dict(title='C.V.')

        # Trying to free up space for more workers
        del array
        del arrays

        # Build the data dictionaries that plotly reads
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
                            line=dict(width=0.2, color="#000000")),
            )]

        # Copy and customize Layout
        layout_copy = copy.deepcopy(layout)
        layout_copy['title'] = (indexnames[choice] +
                                "<Br>" + county)
        layout_copy['plot_bgcolor'] = "white"
        layout_copy['paper_bgcolor'] = "white"
        layout_copy['height'] = 250
        layout_copy['yaxis'] = yaxis
        layout_copy['hovermode'] = 'closest',
        layout_copy['titlefont']['color'] = '#636363'
        layout_copy['font']['color'] = '#636363'
        figure = dict(data=data, layout=layout_copy)

        return figure


# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()
