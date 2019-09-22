#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug 25 15:50:53 2019

@author: travis
"""

import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import json
import copy
import pandas as pd

def generate_table(dataframe, max_rows=10, show_index = True):
    if show_index:
        return html.Table(
            # Header
            [html.Tr([html.Th(dataframe.index.name)] + [html.Th(col) for col in dataframe.columns])] +

            # Body
            [html.Tr([html.Td(dataframe.index[i])] + [
                html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
            ]) for i in range(min(len(dataframe), max_rows))]
        )
    else:
        return html.Table(
            # Header
            [html.Tr([html.Th(col) for col in dataframe.columns])] +

            # Body
            [html.Tr([
                html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
            ]) for i in range(min(len(dataframe), max_rows))]
        )

app = dash.Dash()

FIGURE = {
    'data': [{
        'x': [1, 2, 3],
        'y': [4, 3, 6],
        'mode': 'markers',
        'marker': {
            'size': 12
        }
    }],
    'layout': {
        'xaxis': {},
        'yaxis': {},
    }
}
description = '''
Try clicking on different points. The table updates
with each clicked data point. 

Appending is accomplished by storing
click events in a hidden div, which is accessed through a State variable:

'''
app.layout = html.Div([
    html.H3('Persistent click events'),
    dcc.Markdown(description),

    dcc.Graph(
        id='my-graph',
        figure=FIGURE
    ),
    html.Div(id = 'selected-data'),
    html.Div(id = 'hidden-div', style = {'display': 'none'}),
])

@app.callback(
    Output('hidden-div', 'children'),
    [Input('my-graph', 'clickData')],
    [State('hidden-div', 'children')])
def get_selected_data(clickData, previous):
    if clickData is not None:
        result = clickData['points']
        if previous:
            previous_list = json.loads(previous)
            if previous_list is not None:
                result = previous_list + result
        return json.dumps(result)

@app.callback(
    Output('selected-data', 'children'),
    [Input('hidden-div', 'children')]
    )
def display_selected_data(points):
    if points:
        result = json.loads(points)
        if result is not None:
            return generate_table(pd.DataFrame(result))




app.css.append_css({"external_url": "https://codepen.io/chriddyp/pen/bWLwgP.css"})

if __name__ == '__main__':
    app.run_server()