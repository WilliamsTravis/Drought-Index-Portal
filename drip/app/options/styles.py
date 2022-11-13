"""HTML style options for DrIP app (in lieu if CSS)."""
ON_COLOR = "#cfb87c"
OFF_COLOR = "#b09d6d"
STYLES = dict(
    tab={
        "height": "30px",
        "padding": "0"
    },
    tablet={
        "line-height": "tab_height",
        "padding": "0"
    },
    selected={
        "color": "black",
        "box-shadow": "1px 1px 0px white",
        "border-left": "1px solid lightgrey",
        "border-right": "1px solid lightgrey",
        "border-top": "3px solid black"
    },
    unselected={
        "border-top-left-radius": "3px",
        "background-color": "#f9f9f9",
        "padding": "0px 24px",
        "border-bottom": "1px solid #d6d6d6"
    },
    on_button={
        "height": "45px",
        "padding": "9px",
        "background-color": ON_COLOR,
        "border-radius": "4px",
        "font-family": "Times New Roman",
        "font-size": "12px",
        "margin-top": "-5px"
    },
    off_button={
        "height": "45px",
        "padding": "9px",
        "background-color": OFF_COLOR,
        "border-radius": "4px",
        "font-family": "Times New Roman",
        "font-size": "12px",
        "margin-top": "-5px"
    },
    on_button_app={
        "height": "31px",
        "font-size": "11",
        "border": "1px solid black",
        "background-color": "#ffff",
        "font-family": "Times New Roman",
        "border-radius": "5px",
        "margin-left": "15px",
        "margin-top": "10px"
    },
    off_button_app={
        "height": "31px",
        "font-size": "11",
        "border": "1px solid black",
        "background-color": "#c9d3e9",
        "font-family": "Times New Roman",
        "border-radius": "5px",
        "margin-left": "15px",
        "margin-top": "10px"
    }
)