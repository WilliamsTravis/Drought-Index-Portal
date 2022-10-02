"""HTML style options for DrIP app (in lieu if CSS)."""
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
        "background-color": "#cfb87c",
        "border-radius": "4px",
        "font-family": "Times New Roman",
        "font-size": "12px",
        "margin-top": "-5px"
    },
    off_button={
        "height": "45px",
        "padding": "9px",
        "background-color": "#b09d6d",
        "border-radius": "4px",
        "font-family": "Times New Roman",
        "font-size": "12px",
        "margin-top": "-5px"
    }
)