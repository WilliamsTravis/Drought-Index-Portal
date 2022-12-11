"""Navigation bar HTML Layout."""
from dash import html

from drip.app.pseudo_css import CSS



ACRONYM_TEXT = """
    INDEX/INDICATOR ACRONYMS
    
    
    PDSI:            Palmer Drought Severity Index
    
    PDSI-SC:         Self-Calibrating PDSI
    
    Palmer Z Index:  Palmer Z Index
    
    SPI:             Standardized Precipitation Index
    
    SPEI:            Standardized Precip-ET Index
    
    EDDI:            Evaporative Demand Drought Index
    
    TMIN:            Average Daily Minimum Temp (°C)
    
    TMAX:            Average Daily Maximum Temp (°C)
    
    TDMEAN:          Mean Dew Point Temperature (°C)
    
    PPT:             Average Precipitation (mm)
    
    VPDMAX:          Max Vapor Pressure Deficit (hPa)
    
    VPDMIN:          Min Vapor Pressure Deficit (hPa)
"""

BUTTON_STYLE = {
    "height": "45px",
    "padding": "7px",
    "background-color": "#cfb87c",
    "border-radius": "4px",
    "font-family": "Times New Roman",
    "font-size": "10px",
    "margin-top": "-5px",
    "margin-left": "5px",
    "float": "left"
}

NAVBAR = html.Nav(
    className="top-bar fixed",
    style=CSS["navbar"]["container"],
    children=[
        html.Div(
            children=[
                html.A(
                    html.Img(
                        src=("/static/earthlab.png"),
                        className="one columns",
                        style={
                            "height": "100%",
                            "width": "110px",
                            "float": "right",
                            "position": "static"
                        }
                    ),
                    href="https://www.colorado.edu/earthlab/",
                    target="_blank"
                ),
                html.A(
                    html.Img(
                        src=("/static/wwa_logo2015.png"),
                        className="one columns",
                        style={
                            "height": "100%",
                            "width": "130px",
                            "float": "right",
                            "position": "static"
                        }
                    ),
                    href="http://wwa.colorado.edu/",
                    target="_blank"
                ),
                html.A(
                    html.Img(
                        src=("/static/nccasc_logo.png"),
                        className="one columns",
                        style={
                            "height": "100%",
                            "width": "130px",
                            "float": "right",
                            "position": "relative"
                        }
                    ),
                    href="https://www.drought.gov/drought/",
                    target="_blank"
                ),
                html.A(
                    html.Img(
                        src=("/static/cires.png"),
                        className="one columns",
                        style={
                            "height": "100%",
                            "width": "70px",
                            "float": "right",
                            "position": "relative",
                            "margin-right": "20"
                        }
                    ),
                    href="https://cires.colorado.edu/",
                    target="_blank"
                ),
                html.A(
                    html.Img(
                        src="static/culogo.png",
                        className="one columns",
                        style={
                            "height": "100%",
                            "width": "50px",
                            "float": "right",
                            "border-bottom-left-radius": "3px"
                        }
                    ),
                    href="https://www.colorado.edu/",
                    target="_blank"
                )
            ],
            style=CSS["navbar"]["link-container"],
            className="row"
        ),
        html.Button(
            children="ACRONYMS (HOVER)",
            type="button",
            title=ACRONYM_TEXT,
            style=CSS["navbar"]["button"]
        ),

        html.Div(
            children=[
                html.Button(
                    id="toggle_options",
                    children="Options: Off",
                    n_clicks=0,
                    type="button",
                    title="Display/hide options that apply to each map below.",
                    style={
                        **CSS["navbar"]["button"], **{"margin-left": "25px"}
                    }
                ),
                html.Button(
                    id="desc_button",
                    n_clicks=0,
                    children="Project Description: Off",
                    title=(
                        "Display/hide a description of the application with "
                        "instructions."
                    ),
                    style={
                        **CSS["navbar"]["button"], **{"margin-left": "25px"}
                    }
                ),
                html.Button(
                    id="tutorial_button",
                    n_clicks=0,
                    children="Tutorial: Off",
                    title=(
                        "Display/hide an intorudctory tutorial."
                    ),
                    style={**CSS["navbar"]["button"], **{"margin-left": "-2px"}}
                ),
                html.Button(
                    id="other_button",
                    n_clicks=0,
                    children="Future Projections: Off",
                    title=(
                        "Display/hide a list of links to other drought data "
                        "portals."
                    ),
                    style={
                        **CSS["navbar"]["button"], **{"margin-left": "-2px"}
                    }
                ),
                html.Button(
                    id="click_sync",
                    children="Location Syncing: On",
                    title=(
                        "Sync/unsync the location of the time series between "
                        "each map."
                    ),
                    style={
                        **CSS["navbar"]["button"], **{"margin-left": "25px"}
                    }
                ),
                html.Button(
                    id="date_sync",
                    children="Year Syncing: On",
                    title=(
                        "Sync/unsync the years of the time series between each"
                        " map."
                    ),
                    style={
                        **CSS["navbar"]["button"], **{"margin-left": "-2px"}
                    }
                ),
            ],
            style={"float": "left", "margin-left": "15px"}
        )
    ],
)

