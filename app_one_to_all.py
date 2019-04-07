# -*- coding: utf-8 -*-
"""
One-to-all correlation. I am curious to see what happens when we create a field
of correlation coefficients across CONUS for between one cell and each other
cell in our drought index time series.

Teleconnections (American Meteorological Society):

1. A linkage between weather changes occurring in widely separated regions of
   the globe.
2. A significant positive or negative correlation in the fluctuations of a
   field at widely separated points. Most commonly applied to variability on
   monthly and longer timescales, the name refers to the fact that such
   correlations suggest that information is propagating between the distant
   points through the atmosphere.”


Created on Sun Apr  7 09:44:09 2019

@author: User
"""
import copy
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import datetime as dt
import os
from osgeo import gdal, osr
from flask_caching import Cache
import geopandas as gpd
import json
from inspect import currentframe, getframeinfo
import numpy as np
import pandas as pd
import sys
import warnings
import xarray as xr

# In[] Set environment
frame = getframeinfo(currentframe()).filename
path = os.path.dirname(os.path.abspath(frame))
os.chdir(path)

# Import functions and classes
from functions import makeMap, areaSeries, correlationField, shapeReproject
from functions import Index_Maps, Admin_Elements, Location_Builder 

# Check if we are working in Windows or Linux to find the data
if sys.platform == 'win32':
    data_path = 'f:/'
else:
    data_path = '/root/Sync/'

# What to do with the mean of empty slice warning?
warnings.filterwarnings("ignore")

# In[] The application server
app = dash.Dash(__name__)

# Go to stylesheet, styled after a DASH example (how to serve locally?)  # <--- Check out criddyp's response about a third of the way down here <https://community.plot.ly/t/serve-locally-option-with-additional-scripts-and-style-sheets/6974/6>
app.css.append_css({'external_url':
                    'https://codepen.io/williamstravis/pen/maxwvK.css'})

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
cache.init_app(server)

# In[] Options
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

# Get time dimension from the first data set, assuming everything is uniform
with xr.open_dataset(
        os.path.join(data_path,
             'data/droughtindices/netcdfs/spi1.nc')) as data:
    sample_nc = data.load()
    

min_date = sample_nc.time.data[0]
max_date = sample_nc.time.data[-1]
max_year = pd.Timestamp(max_date).year
min_year = pd.Timestamp(min_date).year
max_month = pd.Timestamp(max_date).month
resolution = sample_nc.crs.GeoTransform[1]
admin = Admin_Elements(resolution)
[state_array, county_array, grid, mask,
 source, albers_source, cd, admin_df] = admin.getElements()
del sample_nc

# Create the date options
years = [int(y) for y in range(min_year, max_year + 1)]
yearmarks = dict(zip(years, years))
monthmarks = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
for y in yearmarks:
    if y % 5 != 0:
        yearmarks[y] = ""

# In[] Base Map
# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')
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


# In[] Element builder
def divMaker(id_num, index='pdsi'):
    div = html.Div([
            html.Div([
                dcc.Dropdown(
                    id='choice_{}'.format(id_num),
                    options=indices, value=index),
                dcc.Graph(id='map_{}'.format(id_num),
                          config={'showSendToCloud': True})]),            
            ])

    return div


# In[] Application Layout
app.layout = html.Div([
        html.Div([
            html.H3(id='date_range',
                    children=['Study Period Year Range']),
            html.Div([
                dcc.RangeSlider(
                    id='year_slider',
                    value=[1950, 2019],
                    min=min_year,
                    max=max_year,
                    updatemode='drag',
                    marks=yearmarks)],
                style={'margin-top': '0',
                       'margin-bottom': '40'}),
            html.Div([divMaker(1, 'pdsi')],
                      className='row'),
            html.Div([dcc.Graph(id='corr_map')])
                    ])
                ])
                

# In[] Application Callbacks
@cache.memoize()
def retrieve_data(year_range, choice):
    time_range = [year_range, [1, 12]]
    data = Index_Maps(time_range, 'Viridis', 'no', choice)
    delivery = makeMap(data, 'omean')
    return delivery

@app.callback(Output('map_1', 'figure'),
              [Input('choice_1', 'value'),
               Input('year_slider', 'value')])
def makeGraph1(choice, year_range):
    [array, arrays, dates, colorscale,
     dmax, dmin, reverse, res] = retrieve_data(year_range, choice)

    # Individual array min/max
    amax = np.nanmax(array)
    amin = np.nanmin(array)    

    # Replace source array
    source.data[0] = array * mask

    # Create a data frame of coordinates, index values, labels, etc
    dfs = xr.DataArray(source, name="data")
    pdf = dfs.to_dataframe()
    step = cd.res
    to_bin = lambda x: np.floor(x / step) * step
    pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
    pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
    pdf['gridx'] = pdf['lonbin'].map(cd.londict)
    pdf['gridy'] = pdf['latbin'].map(cd.latdict)

    # For hover information
    grid2 = np.copy(grid)
    grid2[np.isnan(grid2)] = 0
    pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
    pdf = pd.merge(pdf, admin_df, how='inner')
    pdf['data'] = pdf['data'].astype(float)
    pdf['printdata'] = (pdf['place'] + " (grid: " + 
                        pdf['grid'].apply(int).apply(str) + ")<br>      " + 
                        pdf['data'].round(3).apply(str))

    df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
    df = df_flat[np.isfinite(df_flat['data'])]

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
                opacity=1.0,
                size=source.res[0] * 20,
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
        style='dark',
        center=dict(lon=-95.7, lat=37.1),
        zoom=2)
    layout_copy['title'] = (indexnames[choice])

    figure = dict(data=data, layout=layout_copy)
    return figure


@app.callback(Output('corr_map', 'figure'),
              [Input('map_1', 'clickData'),
               Input('choice_1', 'value'),
               Input('year_slider', 'value')])
def makeGraph2(point, choice, year_range):
    [array, arrays, dates, colorscale,
     dmax, dmin, reverse, res] = retrieve_data(year_range, choice)
    print(str(point))

    # Individual array min/max
    amax = 1
    amin = 0    

    # Replace array with the correlation field
    try:
        location = point['points'][0]['text'][:point['points'][0]['text'].index('<')]
    except:
        location = ''

    gridid = cd.pointToGrid(point)
    grid = cd.grid
    start = time.time()
    array = correlationField(gridid, grid, arrays)
    end = time.time()
    seconds = end - start
    print('{} seconds'.format(seconds))

    # Replace source array
    source.data[0] = array * mask

    # Create a data frame of coordinates, index values, labels, etc
    dfs = xr.DataArray(source, name="data")
    pdf = dfs.to_dataframe()
    step = cd.res
    to_bin = lambda x: np.floor(x / step) * step
    pdf["latbin"] = pdf.index.get_level_values('y').map(to_bin)
    pdf["lonbin"] = pdf.index.get_level_values('x').map(to_bin)
    pdf['gridx'] = pdf['lonbin'].map(cd.londict)
    pdf['gridy'] = pdf['latbin'].map(cd.latdict)

    # For hover information
    grid2 = np.copy(grid)
    grid2[np.isnan(grid2)] = 0
    pdf['grid'] = grid2[pdf['gridy'], pdf['gridx']]
    pdf = pd.merge(pdf, admin_df, how='inner')
    pdf['data'] = pdf['data'].astype(float)
    pdf['printdata'] = (pdf['place'] + " (grid: " + 
                        pdf['grid'].apply(int).apply(str) + ")<br>      " + 
                        pdf['data'].round(3).apply(str))

    df_flat = pdf.drop_duplicates(subset=['latbin', 'lonbin'])
    df = df_flat[np.isfinite(df_flat['data'])]

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
                opacity=1.0,
                size=source.res[0] * 20,
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
        style='dark',
        center=dict(lon=-95.7, lat=37.1),
        zoom=2)
    layout_copy['title'] = (indexnames[choice] + '<br>' +
                            'Pearson Correlation Coefficient with: ' +
                            location)

    figure = dict(data=data, layout=layout_copy)
    return figure


# In[] Run Application through the server
if __name__ == '__main__':
    app.run_server()