# -*- coding: utf-8 -*-
"""DrIP DASH application objects.

Created on Sat Mar  5 10:46:28 2022

@author: travis
"""
import os

import dash

from dash import dcc, html
from flask_caching import Cache

from drip.app.pages.main.view import LAYOUT
from drip.app.layouts.navbar import NAVBAR
from drip import Paths


app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True
)
app.scripts.config.serve_locally = True
server = app.server
cache = Cache(
    config={
        "CACHE_TYPE": "filesystem",
        "CACHE_DIR": os.path.join(
                          os.path.dirname(__file__),
                          "data/cache1",
                      ),
        "CACHE_THRESHOLD": 10
    }
)
cache.init_app(server)

app.layout = html.Div([
    NAVBAR,
    dcc.Location(id="url", refresh=False),
    html.Div(id="page_content", children=LAYOUT)
])
