"""Mapbox Layout."""
TOKEN = (
    "pk.eyJ1IjoidHJhdmlzc2l1cyIsImEiOiJjamZiaHh4b28waXNkMnptaWlwcHZvdzdoIn0."
    "9pxpgXxyyhM6qEF_dcyjIQ"
)
DEFAULT_MAP_EXTENT = {
    "mapbox.center": {
        "lon": -92,
        "lat": 38
    },
    "mapbox.zoom": 3.2,
    "mapbox.bearing": 0,
    "mapbox.pitch": 0
}

MAPBOX_LAYOUT = dict(
    height=600,
    font=dict(
        color="#CCCCCC",
        fontweight="bold"
    ),
    titlefont=dict(
        color="#CCCCCC",
        size="20",
        family="Time New Roman",
        fontweight="bold"
    ),
    margin=dict(
        l=55,
        r=35,
        b=90,
        t=75,
        pad=4
    ),
    hovermode="closest",
    plot_bgcolor="#083C04",
    paper_bgcolor="black",
    legend=dict(
        font=dict(
            size=10,
            fontweight="bold"
        ),
        orientation="h"
    ),
    title="<b>Index Values/b>",
    mapbox=dict(
        accesstoken=TOKEN,
        style="satellite-streets",
        center=dict(lon=-95.7, lat=37.1),
        zoom=2
    )
)