# -*- coding: utf-8 -*-
"""
Created on Sun Mar  3 12:44:39 2019

@author: User
"""


import dash
import dash_table
import pandas as pd

df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/solar.csv')
df = pd.DataFrame({'D0': 100, 'D1': 100, 'D2': 100, 'D3': 100, 'D4': 100},
                   index=[0])

app = dash.Dash(__name__)

app.layout = dash_table.DataTable(
    id='table',
    columns=[{"name": i, "id": i} for i in df.columns],
    data=df.to_dict("rows"),
)

if __name__ == '__main__':
    app.run_server(debug=True)