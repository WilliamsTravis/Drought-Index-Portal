"""Stand-in python dictionary for future CSS."""

BOX_SHADOW = "0 4px 8px 0 rgba(0, 0, 0, 0.2), 0 6px 20px 0 rgba(0, 0, 0, 0.19)"

CSS = {
    "navbar":{
        "container": {
                "background-color": "black",
                "position": "fixed",
                "margin-left": "-10px",
                "margin-right": "-20px",
                "margin-top": "-10px",
                "border-radius": "5px",
                "height": "55px",
                "width": "100.1%",
                "zIndex": "9999",
                "border-bottom": "7px solid #cfb87c",
                "box-shadow": BOX_SHADOW
        },
        "button": {
            "height": "45px",
            "padding": "7px",
            "background-color": "#cfb87c",
            "border-radius": "4px",
            "font-family": "Times New Roman",
            "font-size": "12px",
            "margin-top": "-5px",
            "margin-left": "5px",
            "float": "left"
        },
        "link-container": {
            "background-color": "white",
            "height": "40px",
            "width": "490px",
            "position": "center",
            "float": "right",
            "margin-right": "10px",
            "margin-top": "-5px",
            "border": "3px solid #cfb87c",
            "border-radius": "5px",
        }
    },
    "graph": {
        "container": {
            "position": "relative",
            "margin-top": "-1px",
            "border-radius": "5px",
            "box-shadow": BOX_SHADOW
        },
    },
    "body": {
        "container": {
            "width": "98%",
            "margin-bottom": "50px",
            "margin-top": "60px",
            "margin-left": "25px",
            "margin-right": "100px"
        },
        "tutorial": {
            "margin-bottom": "75px",
            "margin-top": "15px",
            "border-radius": "5px",
            "box-shadow": BOX_SHADOW
        },
        "text-large": {
            "font-weight": "bolder",
            "text-align": "center",
            "font-family": "Times New Roman",
            "margin-top": "90",
        }
    }
}
