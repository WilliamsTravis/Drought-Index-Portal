"""Navigation bar HTML Layout."""
from dash import html


ACRONYM_TEXT = """
    INDEX/INDICATOR ACRONYMS
    
    
    PDSI:            Palmer Drought Severity Index
    
    PDSI-SC:         Self-Calibrating PDSI
    
    Palmer Z Index:  Palmer Z Index
    
    SPI:             Standardized Precipitation Index
    
    SPEI:            Standardized Precip-ET Index
    
    EDDI:            Evaporative Demand Drought Index
    
    LERI:            Landscape Evaporation Response Index
    
    TMIN:            Average Daily Minimum Temp (°C)
    
    TMAX:            Average Daily Maximum Temp (°C)
    
    TMEAN:           Mean Temperature (°C)
    
    TDMEAN:          Mean Dew Point Temperature (°C)
    
    PPT:             Average Precipitation (mm)
    
    VPDMAX:          Max Vapor Pressure Deficit (hPa)
    
    VPDMIN:          Min Vapor Pressure Deficit (hPa)
"""

BUTTON_STYLE = {
    "height": "55px",
    "padding": "9px",
    "background-color": "#cfb87c",
    "border-radius": "4px",
    "font-family": "Times New Roman",
    "font-size": "12px",
    "margin-top": "-5px",
    "margin-left": "10px",
    "float": "left"
}

NAVBAR = html.Nav(
    className="top-bar fixed",
    children=[
        html.Div(
            children=[
                html.A(
                    html.Img(
                        src=("/static/earthlab.png"),
                        className="one columns",
                        style={
                            "height": "100%",
                            "width": "130px",
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
                            "width": "150px",
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
                            "width": "150px",
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
                            "width": "80px",
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
                            "width": "60px",
                            "float": "right",
                            "border-bottom-left-radius": "3px"
                        }
                    ),
                    href="https://www.colorado.edu/",
                    target="_blank"
                )
            ],
            style={
                "background-color": "white",
                "height": "55px",
                "width": "570px",
                "position": "center",
                "float": "right",
                "margin-right": "10px",
                "margin-top": "-5px",
                "border": "3px solid #cfb87c",
                "border-radius": "5px",
            },
            className="row"
        ),
        html.Button(
            children="ACRONYMS (HOVER)",
            type="button",
            title=ACRONYM_TEXT,
            style={
                "height": "55px",
                "padding": "9px",
                "background-color": "#cfb87c",
                "border-radius": "4px",
                "font-family": "Times New Roman",
                "font-size": "12px",
                "margin-top": "-5px",
                "margin-left": "10px",
                "float": "left",
            }
        ),

        html.Div(
            children=[
                html.Button(
                    id="toggle_options",
                    children="Toggle Options: Off",
                    n_clicks=0,
                    type="button",
                    title="Display/hide options that apply to each map below.",
                    style={**BUTTON_STYLE, **{"margin-left": "25px"}}
                ),
                html.Button(
                    id="desc_button",
                    n_clicks=0,
                    children="Project Description: Off",
                    title=(
                        "Display/hide a description of the application with "
                        "instructions."
                    ),
                    style={**BUTTON_STYLE, **{"margin-left": "25px"}}
                ),
                html.Button(
                    id="other_button",
                    n_clicks=0,
                    children="Future Projections: Off",
                    title=(
                        "Display/hide a list of links to other drought data "
                        "portals."
                    ),
                    style={**BUTTON_STYLE, **{"margin-left": "-2px"}}
                ),
                html.Button(
                    id="click_sync",
                    children="Location Syncing: On",
                    title=(
                        "Sync/unsync the location of the time series between "
                        "each map."
                    ),
                    style={**BUTTON_STYLE, **{"margin-left": "25px"}}
                ),
                html.Button(
                    id="date_sync",
                    children="Year Syncing: On",
                    title=(
                        "Sync/unsync the years of the time series between each"
                        " map."
                    ),
                    style={**BUTTON_STYLE, **{"margin-left": "-2px"}}
                ),
            ],
            style={"float": "left", "margin-left": "15px"}
        )
    ],
    style={
        "background-color": "black",
        "position": "fixed",
        "margin-left": "-10px",
        "margin-right": "-20px",
        "margin-top": "-10px",
        "border-radius": "5px",
        "height": "70px",
        "width": "100.1%",
        "zIndex": "9999",
        "border-bottom": "7px solid #cfb87c",
        "box-shadow": (
            "0 4px 8px 0 rgba(0, 0, 0, 0.2), 0 6px 20px 0 rgba(0, 0, 0, 0.19)"
        ),
    }
)

