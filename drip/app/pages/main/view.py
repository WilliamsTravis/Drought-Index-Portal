# -*- coding: utf-8 -*-
"""Drip main page layout."""
import json

from dash import html, dcc

from drip import Paths
from drip.app.options.options import Options, DEFAULT_LOCATION, DEFAULT_SIGNAL
from drip.app.options.styles import STYLES



# Dynamic Elements
def divMaker(id_num, index="noaa"):
    div = html.Div(
        style={
            "position": "relative",
            "margin-top": "-1px",
            "border-radius": "5px",
            "box-shadow": ("0 4px 8px 0 rgba(0, 0, 0, 0.2), 0 6px 20px 0 "
                           "rgba(0, 0, 0, 0.19)")
        },
        children=[
        html.Div([

            # Tabs and dropdowns
            html.Div([
                dcc.Tabs(id="choice_tab_{}".format(id_num),
                         value="index",
                         style=STYLES["tab"],
                         children=dcc.Tab(value="index",
                                          label="Drought Index/Indicator",
                                          style=STYLES["tab"],
                                          selected_style=STYLES["tab"])),
                dcc.Dropdown(id="choice_{}".format(id_num),
                             options=Options.index_options,
                             value=index,
                             clearable=False)],
                     style={"width": "25%", "float": "left"},
                     title="Select a drought index for this element"),
            html.Div([
                dcc.Tabs(id="location_tab_{}".format(id_num),
                         value="county",
                         style=STYLES["tab"],
                         children=[
                    dcc.Tab(value="county",
                            label="County",
                            style=STYLES["tab"],
                            selected_style=STYLES["tab"]
                            ),
                    dcc.Tab(value="state",
                            label="State/States",
                            style=STYLES["tab"],
                            selected_style=STYLES["tab"]),
                    dcc.Tab(value="shape",
                            label="Shapefile",
                            style=STYLES["tab"],
                            selected_style=STYLES["tab"])
                ]),
                html.Div(id="location_div_{}".format(id_num),
                         children=[
                    html.Div(
                        id="county_div_{}".format(id_num),
                        children=[
                            dcc.Dropdown(
                                id="county_{}".format(id_num),
                                clearable=False,
                                options=Options.counties,
                                multi=False,
                                value=24098)]),
                    html.Div(
                        id="state_div_{}".format(id_num),
                        children=[
                            dcc.Dropdown(
                                id="state_{}".format(id_num),
                                options=Options.states,
                                clearable=False,
                                multi=True,
                                placeholder=("Contiguous United States"),
                                value=None)],
                        style={"display": "none"}),
                    html.Div(
                        id="shape_div_{}".format(id_num),
                        title=(
                            "To use a shapefile as an area filter, upload " 
                            "one as either a zipfile or a grouped selection "
                            "that includes the .shp, .shx, .sbn, .sbx, "
                            ".proj, and .sbx files. Make sure the file is "
                            "unprojected for now."
                        ),
                        children=[
                            dcc.Upload(
                                id="shape_{}".format(id_num),
                                children=[
                                    "Drag and drop or ",
                                    html.A("select files")
                                ],
                                multiple=True,
                                style={
                                    "borderWidth": "2px",
                                    "borderStyle": "dashed",
                                    "borderRadius": "3px",
                                    "borderColor": "#CCCCCC",
                                    "textAlign": "center",
                                    "margin": "2px",
                                    "padding": "2px"
                                }
                            )
                        ]
                    )
                ])],
                style={
                    "width": "60%",
                    "float": "left"
                }
            ),

            html.Div(
                children=[
                    html.Button(
                        id="reset_map_{}".format(id_num),
                        children="Reset",
                        title="Remove area filters.",
                        style={
                            "width": "15%",
                            "font-size": "10",
                            "height": "30px",
                            "line-height": "4px",
                            "background-color": "#ffff",
                            "font-family": "Times New Roman"
                        }
                    ),
                    html.Button(
                        id="update_graphs_{}".format(id_num),
                        children="Update",
                        title=(
                            "Update the map and  graphs with location choices "
                            "(state selections do not update automatically)."
                        ),
                        style={
                            "width": "15%",
                            "height": "34px",
                            "font-size": "11",
                            "line-height": "6px",
                            "background-color": "#F9F9F9",
                            "border-bottom": "2px solid gray",
                            "border-top": "0px solid gray",
                            "font-family": "Times New Roman"
                        }
                    )
                ]
            )],
            className="row"
        ),

        # Maps
        html.Div([
            dcc.Graph(
                id="map_{}".format(id_num),
                config={"showSendToCloud": True}
            ),
            html.Div(
                  style={
                    "border": "3px solid black",
                },
                children=html.Div(
                    style={
                        "width": "94%",
                        "border-top": "0px",
                        "margin-top": "5px",
                        "margin-bottom": "-1px",
                        "margin-left": "40px"
                    },
                    children=[
                        dcc.RangeSlider(
                            id=f"color_slider_{id_num}",
                            min=0,
                            max=1,
                            step=.01,
                            marks=None,
                            tooltip={
                                "placement": "bottom",
                                "always_visible": True
                            },
                            className="margin20"
                        ),
                        html.P(
                            id=f"color_slider_print_{id_num}",
                            children="Color Sider",
                            style={
                                "text-align": "center",
                                "margin-top": "-10px"
                            }
                        )
                    ]
                )
            ),
            html.Div([
                html.Div([
                    html.P(
                        children="Point Size:",
                        className="two columns",
                        style={
                            "margin-top": 5.5,
                            "margin-left": 2,
                            "padding": 0,
                            "float": "left",
                        }
                    ),
                    dcc.Input(
                        id="point_size_{}".format(id_num),
                        type="number",
                        value=4,
                        size="3",
                        className="two columns",
                        style={
                            "background-color": "white",
                            "font-family": "Times New Roman",
                            "float": "left",
                            "margin-left": "-20px",
                            "jutifyContent": "center",
                            "height": "80%"
                        }
                    ),
                    html.P(
                        children="Bounding Box:",
                        className="three columns",
                        style={
                            "margin-top": 5.5,
                            "padding": 0,
                            "float": "left"
                        }
                    ),
                    dcc.Input(
                        id="bbox_{}".format(id_num),
                        type="text",
                        className="five columns",
                        placeholder="lon min, lat min, lon max, lat max",
                        debounce=True,
                        style={
                            "background-color": "white",
                            "font-family": "Times New Roman",
                            "float": "left",
                            "margin-left": "-55px",
                            "jutifyContent": "center",
                            "height": "80%"
                        }
                    ),
                ], className="row",
                   style={"margin-top": "10px"} 
            ),
            ], className="row", style={
                "border": "3px solid black",
            }),
        ]),

        # Graph
        html.Div([
            dcc.Graph(
                id="series_{}".format(id_num),
                config={"showSendToCloud": True}
            )
        ]),
        html.Div(
            id="coverage_div_{}".format(id_num),
            style={"margin-bottom": "25"}
        ),
        html.Button(
            id="dsci_button_{}".format(id_num),
            children=["Show DSCI: Off"],
            title=("The Drought Severity Coverage Index (DSCI) is a way to " +
                   "aggregate the five drought severity classifications into a " +
                   "single number. It is calculated by taking the percentage " +
                   "of an area in each drought category, weighting each by " +
                   "their severity, and adding them together:                 " +
                   "%D0*1 + %D1*2 + %D2*3 + %D3*4 + %D4*5"),
            type="button",
            n_clicks=2,
            style={
                "background-color": "#C7D4EA",
                "border-radius": "2px",
                "font-family": "Times New Roman",
                "border-bottom": "2px solid gray",
                "margin-top": "100px",
                "margin-bottom": "-15px"
            }
        ),
        html.Hr(),

        # Download link
        html.A(
            id="download_link_{}".format(id_num),
            children="Download Selected Data",
            download="timeseries_{}.csv".format(id_num),
            title=(
                "This csv includes data resulting from the selections made "
                f"for the element above and is titled timeseries_{id_num}.csv"
            ),
            href="",
            target="_blank",
            style={"margin-left": "10px"}
        ),
        html.A(
            id="download_all_link_{}".format(id_num),
            children="Download Selected Data (All Indicators)",
            download="timeseries_all_{}.csv".format(id_num),
            title=(
                "This csv includes data for all available indices/indicators "
                "given the selections made for the element above and is "
                f"titled timeseries_all_{id_num}.csv. This can take a moment."
          ),
          href="", target="_blank",
          style={"margin-left": "15px"}
        ),

        # Storage
        dcc.Store(id="download_store_{}".format(id_num)),
        html.Div(
            id="key_{}".format(id_num),
            children="{}".format(id_num),
            style={"display": "none"}
        ),
        html.Div(
            id="label_store_{}".format(id_num),
            style={"display": "none"}
        ),
        html.Div(
            id="shape_store_{}".format(id_num),
            style={"display": "none"}
        )],
        className="six columns"
    )

    return div


# Static Elements
LAYOUT = html.Div([

    # Title
    html.Div(
        id="title_div",
        children=[
            html.H1("Drought Index Portal (DrIP)"),
            html.H4(
                "A tool to display, compare, and extract time series for "
                "various indicators of drought in the Contiguous United States"
            ),
            html.Hr()
        ],
        className="twelve columns",
        style={
            "font-weight": "bolder",
            "text-align": "center",
            "font-size": "50px",
            "font-family": "Times New Roman",
            "margin-top": "100"
        }
    ),

    # Description
    html.Div(
        children=[
            html.Div(
                [
                    dcc.Markdown(id="description")
                ],
                style={
                    "text-align": "center",
                    "width": "70%",
                    "margin": "0px auto"
                }
            ),
            html.Hr(style={"margin-bottom": "1px"})
        ],
        style={
            "text-align": "center",
            "margin": "0 auto",
            "width": "100%"
        }
    ),

    # Other Portal Links
    html.Div([
        html.Div([
             dcc.Markdown(id="other_links")],
            style={"text-align": "center",
                   "width": "70%",
                   "margin": "0px auto"}),
        html.Hr(style={"margin-bottom": "1px"})],
        style={"text-align": "center",
               "margin": "0 auto",
               "width": "100%"}
    ),

    # Options
    html.Div(id="options",
             children=[

                 # Year Sliders
                 html.Div([
                     html.H3(
                        id="date_range_1",
                        children="Date Range"
                    ),
                    html.Div(
                        children=[
                            dcc.RangeSlider(
                                id="year_slider_1",
                                value=[1980, Options.dates["max_year"]],
                                min=Options.dates["min_year"],
                                max=Options.dates["max_year"],
                                updatemode="drag",
                                step=1,
                                marks=Options.date_marks["years"]
                            )
                        ],
                        style={
                            "margin-top": "0",
                            "margin-bottom": "80px"
                        }
                    ),
                    html.Div(
                        id="year_div2",
                        children=[
                            html.H3(
                                id="date_range_2",
                                children="Date Range #2"
                            ),
                            dcc.RangeSlider(
                                id="year_slider_2",
                                value=[1980, Options.dates["max_year"]],
                                min=Options.dates["min_year"],
                                max=Options.dates["max_year"],
                                updatemode="drag",
                                marks=Options.date_marks["years"]
                            )
                        ],
                        style={
                            "display": "none",
                            "margin-top": "0",
                            "margin-bottom": "80px"
                        }
                    )
                ]
            ),

                 # Month Options #1
                 html.Div(
                     children=[
                         html.Div([
                             html.H5(
                                  id="month_start_print_1",
                                  children="Start Month"
                                  ),
                             dcc.Slider(
                                 id="month_slider_1a",
                                 value=1,
                                 marks=Options.date_marks["months_slanted"],
                                 min=1,
                                 max=12,
                                 updatemode="drag",
                                 included=False
                             )],
                             className="three columns",
                             title=("Choose the first month of the first " +
                                    "year of the study period.")),
                         html.Div([
                             html.H5(
                                  id="month_end_print_1",
                                  children="End Month"
                                  ),
                             dcc.Slider(
                                 id="month_slider_1b",
                                 value=1,
                                 marks=Options.date_marks["months_slanted"],
                                 min=1,
                                 max=12,
                                 updatemode="drag",
                                 included=False
                             )],
                             className="three columns",
                             title=("Choose the last month of the last year " +
                                    "of the study period.")),
                         html.Div(
                             children=[
                                 html.H5(
                                     id="month_filter_print_1",
                                     children="Included Months"
                                 ),
                                 dcc.Checklist(
                                     className="check_blue",
                                     id="month_check_1",
                                     value=list(range(1, 13)),
                                     options=Options.date_marks["months"],
                                     labelStyle={"display": "inline-block"}
                                 ),
                                 html.Button(
                                    id="all_months_1", type="button",
                                    children="All",
                                    style={
                                        "height": "25px",
                                        "line-height": "25px",
                                        "background-color": "#C7D4EA",
                                        "border-radius": "2px",
                                        "font-family": "Times New Roman",
                                        "border-bottom": "2px solid gray",
                                    }
                                ),
                                 html.Button(
                                    id="no_months_1",
                                    type="button",
                                    children="None",
                                    style={
                                        "height": "25px",
                                        "line-height": "25px",
                                        "background-color": "#C7D4EA",
                                        "border-radius": "2px",
                                        "font-family": "Times New Roman",
                                        "border-bottom": "2px solid gray",
                                    }
                                )
                            ],
                            className="six columns",
                            title=(
                                "Choose which months of the year to be "
                                "included."
                            )
                        )
                    ],
                     className="row"),

                 # Month Options  #2
                 html.Div(
                     id="month_div2",
                     children=[
                         html.Div([
                             html.H5("Start Month #2"),
                             dcc.Slider(
                                  id="month_slider_2a",
                                  value=1,
                                  marks=Options.date_marks["months_slanted"],
                                  min=1,
                                  max=12,
                                  updatemode="drag",
                                  included=False
                                  )],
                                  className="three columns",
                                  title=("Choose the first month of the first " +
                                         "year of the study period.")),
                        html.Div([
                            html.H5("End Month #2"),
                            dcc.Slider(
                                id="month_slider_2b",
                                value=1,
                                marks=Options.date_marks["months_slanted"],
                                min=1,
                                max=12,
                                updatemode="drag",
                                included=False
                            )
                        ],
                        className="three columns",
                        title=(
                            "Choose the last month of the last year of the "
                            "study period."
                        )
                    ),
                    html.Div(
                        children=[
                            html.H5("Included Months #2"),
                            dcc.Checklist(
                                className="check_blue",
                                id="month_check_2",
                                value=list(range(1, 13)),
                                options=Options.date_marks["months"],
                                labelStyle={"display": "inline-block"}
                            ),
                            html.Button(
                                id="all_months_2",
                                type="button",
                                children="All",
                                style={
                                    "height": "25px",
                                    "line-height": "25px"
                                }
                            ),
                            html.Button(
                                id="no_months_2",
                                type="button",
                                children="None",
                                style={
                                    "height": "25px",
                                    "line-height": "25px"
                                }
                            )
                        ],
                        className="six columns",
                        title=("Choose which months of the year to " +
                            "be included."))],
                style={"display": "none", "margin-top": "30",
                    "margin-bottom": "30"},
                className="row"),

                 # Rendering Options
                html.Div(id="options_div",
                         children=[

                             # Map type
                             html.Div([
                                 html.H3("Map Type"),
                                 dcc.Dropdown(
                                     id="map_type",
                                     value="light",
                                     options=Options.base_maps
                                 )],
                                 className="two columns"
                             ),

                             # Functions
                             html.Div([
                                 html.H3("Function"),
                                 dcc.Tabs(
                                     id="function_type",
                                     value="index",
                                     style=STYLES["tab"],
                                     children=[
                                         dcc.Tab(
                                           label="Index Values",
                                           value="index",
                                           style=STYLES["tab"],
                                           selected_style=STYLES["tab"]
                                         ),
                                         dcc.Tab(
                                             label="Percentiles",
                                             value="perc",
                                             style=STYLES["tab"],
                                             selected_style=STYLES["tab"]
                                         )]
                                 ),
                                 dcc.Dropdown(
                                     id="function_choice",
                                     options=Options.functions["percentile"],
                                     value="pmean"
                                 )],
                                className="three columns"),

                             # Color Scales
                             html.Div([
                                 html.H3("Color Gradient"),
                                 dcc.Tabs(
                                     id="reverse",
                                     value="no",
                                     style=STYLES["tab"],
                                     children=[
                                         dcc.Tab(value="no",
                                                 label="Not Reversed",
                                                 style=STYLES["tab"],
                                                 selected_style=STYLES["tab"]),
                                         dcc.Tab(value="yes",
                                                 label="Reversed",
                                                 style=STYLES["tab"],
                                                 selected_style=STYLES["tab"])]),
                                 dcc.Dropdown(id="colors",
                                              options=Options.colors,
                                              value="Default")],
                                      className="three columns")],

                         style={"margin-bottom": "50",
                                "margin-top": "50",
                                "text-align": "center"})],
             style={"text-align": "center"},
             className="row"),

    # Submission Button
    html.Div(
        children=[
            html.Button(
                id="submit",
                title=(
                    "Submit the option settings above and update the graphs "
                    "below."
                ),
                children="Submit Options",
                type="button",
                style={
                    "background-color": "#C7D4EA",
                    "border-radius": "2px",
                    "font-family": "Times New Roman",
                    "border-bottom": "2px solid gray",
                    "margin-top": "100px",
                    "margin-bottom": "35px"
                }
            )
        ],
        style={"text-align": "center"}
    ),

    # Break line
    html.Hr(style={"margin-top": "1px"}),

    # The Map divs
    html.Div(
        children=[
            divMaker(1, Options.index_keys[0]),
            divMaker(2, Options.index_keys[1])
        ],
        className="row"
    ),

    # Signals
    html.Div(
      id="signal",
      children=json.dumps(DEFAULT_SIGNAL),
      style={"display": "none"}
    ),
    html.Div(
      id="date_print_1",
      children=f"1980 - {Options.dates['max_year']}",
      style={"display": "none"}
    ),
    html.Div(
      id="date_print_2",
      children=f"1980 - {Options.dates['max_year']}",
      style={"display": "none"}
    ),
    html.Div(
      id="location_store_1",
      children=DEFAULT_LOCATION,
      style={"display": "none"}
    ),
    html.Div(
      id="location_store_2",
      children=DEFAULT_LOCATION,
      style={"display": "none"}
    ),
    html.Div(
      id="choice_store",
      style={"display": "none"}
    ),
    html.Div(
      id="area_store_1",
      children="[0, 0]",
      style={"display": "none"}
    ),
    html.Div(
      id="area_store_2",
      children="[0, 0]",          
      style={"display": "none"}
    )

],
    className="eleven columns",
    style={
        "width": "98%",
        "margin-bottom": "50px",
        "margin-top": "100px",
        "margin-left": "25px",
        "margin-right": "100px"
    }
)
