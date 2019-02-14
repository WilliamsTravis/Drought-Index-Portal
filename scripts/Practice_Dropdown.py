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

layout = app.layout(
        html.Div([
                dcc.Dropdown(id='county_1',
                             options=county_options),
                html.Div(id='output_1'),
                dcc.Dropdown(id='county_2',
                             options=county_options),
                # html.Div(id='output_2'),
                # dcc.Dropdown(id='county_3',
                #              options=county_options),
                # html.Div(id='output_3'),
                # dcc.Dropdown(id='county_4',
                #              options=county_options)
                # html.Div(id='output_4'),
                ])
                

@app.callback(Output('output_1', 'children'),
              [Input('county_1', 'value'),
               Input('county_2')])
