# -*- coding: utf-8 -*-
"""
Created on Thu Feb 14 07:14:06 2019

@author: User
"""
import os
import sys
import copy
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import gc
from inspect import currentframe, getframeinfo
import json
import pandas as pd
import numpy as np
import psutil
import time
import warnings
import xarray as xr

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

# Choices
c_df = pd.read_csv('data/unique_counties.csv')
rows = [r for idx, r in c_df.iterrows()]
county_options = [{'label': r['place'], 'value': r['grid']} for r in rows]
just_values = [d['value'] for d in county_options]
just_counties = [d['label'] for d in county_options]


app.layout = html.Div([
                html.Div([
                    html.Div([dcc.Dropdown(id='county_1',
                                           options=county_options),
                             html.Div(id='output_1')],
                             style={'float': 'left',
                                    'width': '20%'}),

                    html.Div([dcc.Dropdown(id='county_2',
                                           options=county_options),
                             html.Div(id='output_2')],
                             style={'float': 'left',
                                    'width': '20%'})],
                    className='row'),
                html.Br(),
                html.Br(),
                html.Br(),
                html.Br(),
                html.Br(),
                html.Br(),
                html.Br(),
                html.Br(),
                html.Br(),
    html.Div(id='most_recent', style={'display': 'None'}),
    html.H4('Click Time #1'),
    html.Div(id='time_1'),
    html.H4('Click Time #2'),
    html.Div(id='time_2')

])

@app.callback(Output('time_1', 'children'),
              [Input('county_1', 'value')])
def dropOne(county):
    return time.time()

@app.callback(Output('time_2', 'children'),
              [Input('county_2', 'value')])
def dropOne(county):
    return time.time()
#
@app.callback(Output('output_1', 'children'),
              [Input('most_recent', 'children')])
def dropOne(county):
    return county

@app.callback(Output('output_2', 'children'),
              [Input('most_recent', 'children')])
def dropOne(county):
    return county




@app.callback(Output('county_1', 'options'),
             [Input('most_recent', 'children'),
              Input('county_1', 'value')])
def dropOne(recent, current):
    options = county_options
    recent_idx = just_values.index(recent)
    current_idx = just_values.index(current)
    target_county = just_counties[recent_idx]
    options[current_idx]['label'] = target_county
    return options

@app.callback(Output('county_2', 'options'),
             [Input('most_recent', 'children'),
              Input('county_2', 'value')])
def dropOne(recent, current):
    options = county_options
    recent_idx = just_values.index(recent)
    current_idx = just_values.index(current)
    target_county = just_counties[recent_idx]
    options[current_idx]['label'] = target_county
    return options


#
# @app.callback(Output('county_2', 'options'),
#              [Input('most_recent', 'children')])
# def dropOne(county):
#     return county_options[1]
# #
@app.callback(Output('most_recent', 'children'),
              [Input('time_1' , 'children'),
               Input('time_2', 'children')],
              [State('county_1', 'value'),
               State('county_2', 'value')])
def clickPicker( time_1, time_2, county_1, county_2):
    counties = [county_1, county_2]
    times = [time_1, time_2]
    print(times)
    county = counties[times.index(max(times))]
    return county

if __name__ == '__main__':
    app.run_server()
