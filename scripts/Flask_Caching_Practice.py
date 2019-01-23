# -*- coding: utf-8 -*-
"""
Like Practice_Memoization, I'd like to practice with Flask Caching specifically
    Apparently a simple cache like mine, or the one in flask-caching, cannot
    handle multiple workers. I wonder if filesystem can...

Created on Mon Jan 21 12:06:07 2019

@author: User
"""
import copy
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import json
from flask_caching import Cache
import os
import pandas as pd
import psutil
import sys
import time
import xarray as xr

# Check if we are working in Windows or Linux
if sys.platform == 'win32':
    home_path = 'z:/Sync'
    data_path = 'd:/'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
else:
    home_path = '/root/Sync'
    os.chdir(os.path.join(home_path, 'Ubuntu-Practice-Machine'))
    data_path = '/root'

sys.path.insert(0, os.path.join(home_path,
                                'Ubuntu-Practice-Machine', 'scripts'))
sys.path.insert(0, os.path.join(home_path,
                                'Ubuntu-Practice-Machine'))
from Index_Map import Index_Maps
from functions import calculateCV

# In[] These are three optional signals to build data with
signal1 = [[[2000, 2017], [1, 12]], 'mean_perc', 'Viridis', 'no', 'pdsi', 1]
signal2 = [[[1950, 1955], [1, 12]], 'mean_perc', 'Viridis', 'no', 'pdsi', 2]
signal3 = [[[1985, 2017], [1, 12]], 'mean_perc', 'Viridis', 'no', 'pdsi', 3]
signal1 = json.dumps(signal1)
signal2 = json.dumps(signal2)
signal3 = json.dumps(signal3)
data_options = [{'label': 'Data Set #1', 'value': signal1},
                {'label': 'Data Set #2', 'value': signal2},
                {'label': 'Data Set #3', 'value': signal3}]

# A source grid for scatterplot maps - will need more for optional resolution
source = xr.open_dataarray(os.path.join(data_path,
                                        "data/droughtindices/source_array.nc"))
# Mapbox Access
mapbox_access_token = ('pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNk' +
                       'MnptaWlwcHZvdzdoIn0.9pxpgXxyyhM6qEF_dcyjIQ')
grid = np.load(data_path + "/data/prfgrid.npz")["grid"]
mask = grid*0+1
counties_df = pd.read_csv("data/counties.csv")
counties_df = counties_df[['grid', 'county', 'state']]
counties_df['place'] = (counties_df['county'] +
                        ' County, ' + counties_df['state'])

# Create Coordinate index positions from xarray
# Geometry
x_length = source.shape[2]
y_length = source.shape[1]
res = source.res[0]
lon_min = source.transform[0]
lat_max = source.transform[3] - res

# Make dictionaires with coordinates and array index positions
xs = range(x_length)
ys = range(y_length)
lons = [lon_min + res*x for x in xs]
lats = [lat_max - res*y for y in ys]
londict = dict(zip(lons, xs))
latdict = dict(zip(lats, ys))
londict2 = {y: x for x, y in londict.items()}
latdict2 = {y: x for x, y in latdict.items()}

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

# In[] Build little dash app and the cache
app = dash.Dash(__name__)
server = app.server

# cache = Cache(config={'CACHE_TYPE': 'memcached',
#                       'CACHE_MEMCACHED_SERVERS': ['127.0.0.1:8000']})
# cache = Cache(config={'CACHE_TYPE': 'filesystem',
#                       'CACHE_DIR': 'cache-directory'})
# cache.init_app(server)


class Cacher:
    def __init__(self):
        self.cache={}
    def memoize(self, function):
        def cacher(x):
            key = json.dumps(x)
            if key not in self.cache.keys():
                print("Generating/replacing dataset...")
                self.cache = {}
                self.cache[key] = function(x)
            else:
                print("Returning existing dataset...")
            return self.cache[key]
        return cacher

cache1 = Cacher()


# In[] Layout
app.layout = html.Div([
        html.H1("Cache/Memoization Practice"),
        html.H2("Select Data:"),
        html.Div([dcc.Dropdown(id='options',
                               options=data_options,
                               value=signal1,
                               # placeholder="Data Set #1"
                               )],
                style={'width': '15%'}),
        html.H2("Memory:"),
        html.H3(id='memory'),
        html.H2("Output #1:"),
        dcc.Graph(id='output'),
        html.Div([html.H2("Output #2:")],
                 style={'height': '50%'}),
        dcc.Graph(id="output2")
    ])


# In[] Functions
@cache1.memoize
def makeMap1(signal):
    '''
    To choose which function to return from Index_Maps
    '''
    # print("Generating New Data Set")
    time.sleep(3)
    [time_range, function, colorscale, reverse, choice, key] = signal

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
    
    return data


@app.callback(Output('memory', 'children'),
              [Input('output', 'clickData')])
def displayMemory(click):
    return ("\nCPU: {}% \nMemory: {}%\n".format(psutil.cpu_percent(),
                                         psutil.virtual_memory().percent))

@app.callback(Output('output', 'figure'),
              [Input('options', 'value')])
def makeGraph(signal):
    signal = json.loads(signal)
    [[array, arrays, dates],
     colorscale, dmax, dmin, reverse] = makeMap1(signal)
    
    # Set to this thing
    source.data[0] = array
    
    # For Title
    time_range = signal[0]
    year1 = time_range[0][0]
    year2 = time_range[0][1]
    
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
    # pdf['grid'] = pdf['grid'].apply(int).apply(str)
    pdf = pd.merge(pdf, counties_df, how='inner')
    pdf['data'] = pdf['data'].astype(float).round(3)
    pdf['printdata'] = pdf['place'] + ":<br>     " + pdf['data'].apply(str)

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
                cmax=dmax,
                cmin=dmin,
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

    layout['title'] = ("Palmer Drought Severity Index <br>" +
                       "{} - {}".format(year1, year2))
    figure = dict(data=data, layout=layout)
        
    return figure


@app.callback(Output('output2', 'figure'),
              [Input('output', 'clickData'),
               Input('options', 'value')])
def makeSeries(click, signal):
    if not click:
        click = {"points": [{"lon": -107.5, "lat": 40.5}]}

    signal = json.loads(signal)

    [[array, arrays, dates],
     colorscale, dmax, dmin, reverse] = makeMap1(signal)

    lon = click['points'][0]['lon']
    lat = click['points'][0]['lat']
    x = londict[lon]
    y = latdict[lat]
    gridid = grid[y, x]
    county = counties_df['place'][counties_df.grid == gridid].unique()

   # Get time series
    dates = [pd.to_datetime(str(d)) for d in dates]
    dates = [d.strftime('%Y-%m') for d in dates]
    timeseries = np.array([round(a[y, x], 4) for a in arrays])
    yaxis=dict(range=[dmin, dmax])

    # Build the data dictionaries that plotly reads
    data = [
        dict(
            type='bar',
            x=dates,
            y=timeseries,
            marker=dict(color=timeseries,
                        colorscale=colorscale,
                        reversescale=reverse,
                        line=dict(width=0.2, color="#000000")),
        )]

    # Copy and customize Layout
    layout_copy = copy.deepcopy(layout)
    layout_copy['title'] = ("Time Series - Individual Observations" +
                            "<Br>" + county)
    layout_copy['plot_bgcolor'] = "white"
    layout_copy['paper_bgcolor'] = "white"
    layout_copy['height'] = 250
    layout_copy['yaxis'] = yaxis
    layout_copy['titlefont']['color'] = '#636363'
    layout_copy['font']['color'] = '#636363'
    figure = dict(data=data, layout=layout_copy)

    return figure    
    

# In[] Run Server
if __name__ == '__main__':
    app.run_server()
