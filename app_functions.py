# -*- coding: utf-8 -*-
"""
Created on Thu Feb 14 21:14:55 2019

@author: User
"""
import numpy as np

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
                                           # placeholder='Moffat County, CO',
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


def makeMap(signal, choice):
    '''
    To choose which function to return from Index_Maps
    '''
    gc.collect()

    [time_range, function, colorscale, reverse] = signal

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


# For making outlines...move to css, maybe
def outLine(color, width):
    string = ('-{1}px -{1}px 0 {0}, {1}px -{1}px 0 {0}, ' +
              '-{1}px {1}px 0 {0}, {1}px {1}px 0 {0}').format(color, width)
    return string




