"""Callbacks for main Drip page."""
import copy
import gc
import json
import os
import psutil

from pathlib import Path

import dash
import datetime as dt
import numpy as np
import pandas as pd
import xarray as xr

from collections import OrderedDict
from dash import dash_table, dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate

from drip import calls, Paths
from drip.app.app import app, cache
from drip.app.layouts.mapbox import DEFAULT_MAP_EXTENT, MAPBOX_LAYOUT
from drip.app.old.functions import (
    Admin_Elements,
    Index_Maps,
    Location_Builder,
    FUNCTION_TYPES,
    TYPE_PATHS,
    UNIT_MAP
)
from drip.app.options.options import Options
from drip.app.options.indices import INDEX_NAMES
from drip.app.options.options import Options
from drip.app.options.styles import ON_COLOR, OFF_COLOR, STYLES
from drip.app.pages.main.model import Parse_Shape
from drip.loggers import init_logger, set_handler

logger = init_logger(__name__)
set_handler(logger, Paths.log_directory.joinpath("callbacks.log"))


# Get spatial dimensions from the sample data set above
resolution = Options.transform[0]
admin = Admin_Elements(resolution)
[state_array, county_array, grid, mask,
 source, albers_source, crdict, admin_df] = admin.getElements()  # <----------- remove albers ource here (carefully)


FUNCTION_OPTIONS_PERC = [
    {"label": "Mean", "value": "pmean"},
    {"label": "Maximum", "value": "pmax"},
    {"label": "Minimum", "value": "pmin"},
    {"label": "Correlation", "value": "pcorr"}
]
FUNCTION_OPTIONS_ORIG = [
    {"label": "Mean", "value": "omean"},
    {"label": "Maximum", "value": "omax"},
    {"label": "Minimum", "value": "omin"},
    {"label": "Drought Severity Area", "value":"oarea"},
    {"label": "Correlation", "value": "ocorr"}
]
FUNCTION_NAMES = {
    "pmean": "Average Percentiles",
    "pmax": "Maxmium Percentiles",
    "pmin": "Minimum Percentiles",
    "omean": "Average Values",
    "omax": "Maximum Values",
    "omin": "Minimum Values",
    "oarea": "Average Values",
    "pcorr": "Pearson's Correlation ",
    "ocorr": "Pearson's Correlation "
}


def makeCSV(arg):
    """Make a single summary CSV of the time series plot."""
    # Unpack arguments, retrieve data, and format dates
    index, signal, function, location, crdict = arg
    data = retrieveData(signal, function, index, location)
    dates = data.dataset_interval.time.values
    dates = [pd.to_datetime(str(d)).strftime("%Y-%m") for d in dates]

    # If the function is oarea, we plot five overlapping timeseries
    label = location[3]
    nonindices = ["tdmean", "tmean", "tmin", "tmax", "ppt",  "vpdmax",
                  "vpdmin", "vpdmean"]
    if function != "oarea" or index in nonindices:
        # Get the time series from the data object
        try:
            timeseries = data.getSeries(location, crdict)
        except Exception as e:
            print(e)
            
        # Create data frame as string for download option
        columns = OrderedDict(
            {
                "month": dates,
                "value": list(timeseries),
                "function": FUNCTION_NAMES[function],  # <-- This doesn"t always make sense
                "location": location[-2],
                "index": INDEX_NAMES[index]
            }
        )
        df = pd.DataFrame(columns)

    else:
        label = location[3]
        ts_series, ts_series_ninc, dsci = data.getArea(crdict)

        # Save to file for download option
        columns = OrderedDict(
            {
                "month": dates,
                "d0": ts_series_ninc[0],
                "d1": ts_series_ninc[1],
                "d2": ts_series_ninc[2],
                "d3": ts_series_ninc[3],
                "d4": ts_series_ninc[4],
                "dsci": dsci,
                "function": "Percent Area",
                "location":  label,
                "index": INDEX_NAMES[index]
            }
        )
        df = pd.DataFrame(columns)

    return df

def makeCSVs(signal, function, location):
    """Take a path with query information and save a csv."""
    # Get data
    dfs = []
    args = []
    data_dir = Paths.paths["indices"]
    for i in INDEX_NAMES:
        ftype = FUNCTION_TYPES[function]
        fpath = data_dir.joinpath(i, f"{i}{TYPE_PATHS[ftype]}.nc")
        if fpath.exists():
            args.append((i, signal, function, location, crdict))

    # crdict isn't working in multiprocess
    # with mp.Pool(mp.cpu_count() - 1) as pool:
    #     for df in pool.imap(makeCSV, args):
    #         dfs.append(df)

    for arg in args:
        df = makeCSV(arg)
        if df is not None:
            dfs.append(df)
    df = pd.concat(dfs)

    return df

@app.callback(
    Output("month_start_print_1", "children"),
    Output("month_end_print_1", "children"),
    Output("month_filter_print_1", "children"),
    Input("date_sync", "n_clicks")
)
@calls.log
def adjustMonthPrint1(sync):
    """If users turn date syncing off, print #1 after each month element."""
    # Text filter patterns
    start = "Start Month"
    end = "End Month"
    filters = "Included Months"

    # If not syncing, these need numbers
    if not sync:
        sync = 0
    if sync % 2 == 0:
        number = ""
    else:
        number = " #1"

    start = start + number
    end = end + number
    filters = filters + number

    return start, end, filters

@app.callback(
    Output("function_choice", "options"),
    Output("function_choice", "value"),
    Input("function_type", "value")
)
@calls.log
def optionsFunctions(function_type):
    """
    Use the Percentile/Index tab to decide which functions options to
    display.
    """
    if function_type == "perc":
        return Options.functions["percentile"], "pmean"
    else:
        return Options.functions["main"], "omean"


@cache.memoize()
@calls.log
def retrieveData(signal, function, choice, location):
    """
    This takes the user defined signal and uses the Index_Map class to filter"
    by the selected dates and return the singular map, the 3d timeseries array,
    and the colorscale.

    sample arguments:
        signal = [[[2000, 2017], [1, 12], [ 4, 5, 6, 7]], "Viridis", "no"]
        choice = "pdsi"
        function = "omean"
        location = ["all", "y", "x", "Contiguous United States", 0]
    """
    # Retrieve signal elements
    time_data = signal[0]
    colorscale = signal[1]

    # Determine the choice_type based on function
    choice_type = FUNCTION_TYPES[function]

    # Retrieve data package
    data = Index_Maps(choice, choice_type, time_data, colorscale)

    # Set mask (also sets coordinate dictionary)
    data.setMask(location, crdict)

    return data


# Output list of all index choices for syncing
@app.callback(
    Output("choice_store", "children"),
    Input("choice_1", "value"),
    Input("choice_2", "value")
)
@calls.log
def storeIndexChoices(choice1, choice2):
    """ Collect and hide both data choices in the hidden "choice_store" div."""
    return (json.dumps([choice1, choice2]))


@app.callback(
    Output("signal", "children"),
    Input("submit", "n_clicks"),
    State("colors", "value"),
    State("reverse", "value"),
    State("year_slider_1", "value"),
    State("month_slider_1a", "value"),
    State("month_slider_1b", "value"),
    State("month_check_1", "value"),
    State("year_slider_2", "value"),
    State("month_slider_2a", "value"),
    State("month_slider_2b", "value"),
    State("month_check_2", "value")
)
@calls.log
def submitSignal(click, colorscale, reverse, year_range_1, month_1a, month_1b,
                 month_check_1, year_range_2, month_2a, month_2b,
                 month_check_2):
    """"Collect and hide the options signal in the hidden "signal" div."""
    # This is to translate the inverse portion of the month range
    month_range_1 = [month_1a, month_1b]
    month_range_2 = [month_2a, month_2b]
    signal_1 = [[year_range_1, month_range_1, month_check_1],
                 colorscale, reverse]
    signal_2 = [[year_range_2, month_range_2, month_check_2],
                 colorscale, reverse]
    signal = [signal_1, signal_2]
    return json.dumps(signal)


@app.callback(
    Output("description", "children"),
    Output("desc_button", "style"),
    Output("desc_button", "children"),
    Input("desc_button", "n_clicks"),
    State("desc_button", "style")
)
@calls.log
def toggleDescription(click, old_style):
    """Toggle description on/off."""
    if not click:
        click = 0
    if click % 2 == 0:
        desc_children = ""
        style = {**old_style, **{"background-color": OFF_COLOR}}
        button_children = "Description: Off"

    else:
        desc_children = open("static/description.txt").read()  # <-------- It makes no sense that the description doc is in the tables folder
        style = {**old_style, **{"background-color": ON_COLOR}}
        button_children = "Description: On"

    return desc_children, style, button_children


@app.callback(
    Output("other_links", "children"),
    Output("title_div", "style"),
    Output("other_button", "style"),
    Output("other_button", "children"),
    Input("other_button", "n_clicks"),
    State("other_button", "style")
)
@calls.log
def toggleFuture(click, old_style):
    """Toggle description on/off."""
    if not click:
        click = 0
    if click % 2 == 0:
        desc_children = ""
        style = {**old_style, **{"background-color": OFF_COLOR}}
        title_style = {"font-weight": "bolder", "text-align": "center",
                       "font-size": "50px", "font-family": "Times New Roman",
                       "margin-top": "100"}
        button_children = "Future Projections: Off"

    else:
        desc_children = open("static/other_links.txt").read()  # <-------- It makes no sense that the description doc is in the tables folder
        style = {**old_style, **{"background-color": ON_COLOR}}
        title_style = {"display": "none"}
        button_children = "Future Projections: On"

    return desc_children, title_style, style, button_children


@app.callback(
    Output("options", "style"),
    Output("toggle_options", "style"),
    Output("submit", "style"),
    Output("toggle_options", "children"),
    Input("toggle_options", "n_clicks"),
    State("toggle_options", "style")
)
@calls.log
def toggleOptions(click, old_style):
    """Toggle options on/off"""
    if click % 2 == 0:
        div_style = {"display": "none"}
        button_style = {**old_style, **{"background-color": OFF_COLOR}}
        submit_style = {"display": "none"}
        children = "Options: Off"
    else:
        div_style = {}
        button_style = {**old_style, **{"background-color": ON_COLOR}}
        submit_style = STYLES["off_button_app"]
        submit_style["margin-bottom"] = "25px"
        submit_style["margin-top"] = "25px"
        children = "Options: On"
    return div_style, button_style, submit_style, children


@app.callback(
    Output("click_sync", "style"),
    Output("click_sync", "children"),
    Input("click_sync", "n_clicks"),
    State("click_sync", "style")
)
@calls.log
def toggleLocationSyncButton(click, old_style):
    """Change the color of on/off location syncing button - for css"""
    if not click:
        click = 0
    if click % 2 != 0:
        children = "Location Syncing: Off"
        style = {**old_style, **{"background-color": OFF_COLOR}}
    else:
        style = {**old_style, **{"background-color": ON_COLOR}}
        children = "Location Syncing: On"
    return style, children

@app.callback(
    Output("tutorial_div", "style"),
    Output("tutorial_button", "style"),
    Output("tutorial_button", "children"),
    Input("tutorial_button", "n_clicks"),
    State("tutorial_div", "style"),
    State("tutorial_button", "style")
)
@calls.log
def toggleTutorial(click, old_div_style, old_button_style):
    """Toggle description on/off."""
    div_style = old_div_style.copy()
    button_style = old_button_style.copy()

    if not click:
        click = 0
    if click % 2 == 0:
        div_style["display"] = "none"
        button_style["background-color"] = OFF_COLOR
        button_children = "Tutorial: Off"
    else:
        if "display" in div_style:
            del div_style["display"]
        button_style["background-color"] = ON_COLOR
        button_children = "Tutorial: On"

    return div_style, button_style, button_children


@app.callback(
    Output("year_div2", "style"),
    Input("date_sync", "n_clicks")
)
@calls.log
def toggleYears2(click):
    """
    When syncing years, there should only be one time slider
    """
    if not click:
        click = 0
    if click % 2 == 0:
        style = {"display": "none", "margin-top": "0", "margin-bottom": "80"}
    else:
        style = {"margin-top": "0", "margin-bottom": "80"}
    return style


@app.callback(
    Output("month_div2", "style"),
    Input("date_sync", "n_clicks")
)
@calls.log
def toggleMonths2(click):
    """
    When syncing years, there should only be one time slider
    """
    if not click:
        click = 0
    if click % 2 == 0:
        style = {"display": "none", "margin-top": "0", "margin-bottom": "80"}
    else:
        style = {"margin-top": "30", "margin-bottom": "30"}
    return style


@app.callback(
    Output("date_sync", "style"),
    Output("date_sync", "children"),
    Input("date_sync", "n_clicks"),
    State("date_sync", "style")
)
@calls.log
def toggleDateSyncButton(click, old_style):
    """Change the color of on/off date syncing button - for css."""
    if not click:
        click = 0
    if click % 2 == 0:
        children = "Date Syncing: On"
        style = {**old_style, **{"background-color": ON_COLOR}}
    else:
        children = "Date Syncing: Off"
        style = {**old_style, **{"background-color": OFF_COLOR}}
    return style, children


# For multiple instances
for i in range(1, 3):

    @app.callback(
        Output(f"month_slider_{i}b", "max"),
        Input(f"choice_{i}" ,"value"),
        Input(f"year_slider_{i}", "value")
    )
    def adjust_end_month(index, year):
        """Adjust end month if only the last year in dataset is selected."""
        # Find the files of the last year
        file = Paths.paths["indices"].joinpath(f"{index}/{index}.nc")
        with xr.open_dataset(file) as ds:
            time = ds["time"].data[-1]

        # Convert to datetime
        month = pd.to_datetime(time).month

        return month

    @app.callback(
        Output(f"month_check_{i}", "value"),
        Output(f"month_check_{i}", "options"),
        Input(f"choice_{i}", "value"),
        Input(f"all_months_{i}", "n_clicks"),
        Input(f"no_months_{i}", "n_clicks"),
        Input(f"year_slider_{i}", "value"),
        State(f"month_check_{i}", "value"),
    )
    @calls.log
    def toggleMonthFilter(index, all_months, no_months, years, last_months):
        """This fills or empties the month filter boxes with/of checks"""
        # Adjust options if only one year
        options = Options(index)
        if years[0] == years[-1]:
            # If this is the last year on file, adjust the ending month
            file = Paths.paths["indices"].joinpath(f"{index}/{index}.nc")
            with xr.open_dataset(file) as ds:
                time = ds["time"].data[:]
            time = [pd.to_datetime(date) for date in time]
            time = [date for date in time if date.year == years[0]]
            time = time[-1]
            last_month = time.month + 1
        else:
            last_month = 13
        month_options = list(range(1, last_month))
        options = options.date_marks["months"]

        # Find which input triggered this callback
        context = dash.callback_context
        trigger_value = context.triggered[0]["value"]
        trigger = context.triggered[0]["prop_id"]

        # Set the values
        month_values = last_months.copy()
        if trigger_value:
                if "all" in trigger:
                    month_values = list(range(1, last_month))
                elif "no" in trigger:
                    month_values = [None]

        return month_values, month_options

    @app.callback(
        Output(f"year_slider_{i}", "min"),
        Output(f"year_slider_{i}", "max"),
        Output(f"year_slider_{i}", "marks"),
        Input("choice_1", "value"),
        Input("choice_2", "value"),
        Input("date_sync", "n_clicks"),
        State("key_{}".format(i), "children")
    )
    def adjustYearSlider(choice1, choice2, sync, key):
        """Adjust years slider to available years in chosen index."""
        # Figure which choice is this panel's and which is the other
        key = int(key) - 1
        choices = [choice1, choice2]
        choice = choices[key]
        choice2 = choices[~key]

        # Sync is None on first load
        if not sync:
            sync = 0

        # Get date range for each index, use shared range if syncing
        if sync % 2 == 0:
            options = Options(choice1)
        else:
            options = Options(choice)

        max_year = options.dates["max_year"]
        min_year = options.dates["min_year"]
        marks = options.date_marks["years"]

        return min_year, max_year, marks

    @app.callback(
        Output(f"date_range_{i}", "children"),
        Output(f"date_print_{i}", "children"),
        Input(f"year_slider_{i}", "value"),
        Input(f"month_slider_{i}a", "value"),
        Input(f"month_slider_{i}b", "value"),
        Input(f"month_check_{i}", "value"),
        Input("date_sync", "n_clicks"),
        State("key_{}".format(i), "children")
    )
    @calls.log
    def adjustDatePrint(year_range, month_a,  month_b, month_check,  sync,
                        key):
        """If users select one year, only print it once."""
        # If not syncing, these need numbers
        months = [int(m) for m in range(1, 13)]
        if not sync:
            sync = 0
        if sync % 2 == 0:
            number = ""
        else:
            number = f" #{key}"
    
        # Don"t print start and end months if full year is chosen
        options = Options("pdsi")
        month_a = options.date_marks["months"][month_a - 1]["label"]
        month_b = options.date_marks["months"][month_b - 1]["label"]
        if month_a == "Jan" and month_b == "Dec":
            mrs = ["", ""]
            mjoin = ""
        else:
            mrs = [month_a + " ", month_b + " "]
            mjoin = " - "

        # Don"t print months included if all are included
        if not month_check[0]:
            month_check = month_check[1:]
    
        if len(month_check) == 12 or len(month_check) == 0:
            month_incl_print = ""
        else:
            month_check.sort()
            if months[0]:
                month_incl_print = "".join(
                    [options.date_marks["months"][i - 1]["label"].upper()[0]
                     for i in month_check]
                )
                month_incl_print = f" ({month_incl_print})"
            else:
                month_incl_print = ""
    
        # Year slider #1: If a single year do this
        if year_range[0] == year_range[1]:
            string = str(year_range[0])
            if mrs[0] == mrs[1]:
                string = mrs[0] + str(year_range[0])
            else:
                string = mrs[0] + mjoin + mrs[1] + str(year_range[0])
        else:
            string = (mrs[0] + str(year_range[0]) + " - " + mrs[1] +
                      str(year_range[1]))
    
        # And now add the month printouts
        string = string + month_incl_print
        full = "Date Range" + number + ":  " + string
    
        return full, string

    @app.callback(
        Output(f"location_store_{i}", "children"),
        Input("map_1", "clickData"),
        Input("map_2", "clickData"),
        Input("map_1", "selectedData"),
        Input("map_2", "selectedData"),
        Input("county_1", "value"),
        Input("county_2", "value"),
        Input("shape_store_1", "children"),
        Input("shape_store_2", "children"),
        Input("bbox_1", "value"),
        Input("bbox_2", "value"),
        Input("update_graphs_1", "n_clicks"),
        Input("update_graphs_2", "n_clicks"),
        Input("reset_map_1", "n_clicks"),
        Input("reset_map_2", "n_clicks"),
        State("state_1", "value"),
        State("state_2", "value"),
        State("click_sync", "children"),
        State(f"key_{i}", "children")
    )
    @calls.log
    def locationPicker(click1, click2, select1, select2, county1, county2,
                       shape1, shape2, bbox1, bbox2, update1, update2, reset1,
                       reset2, state1, state2, sync, key):
            """
            The new context method allows us to select which input was most
            recently changed. However, it is still necessary to have an
            independent callback that identifies the most recent selection.
            Because there are many types of buttons and clicks that could
            trigger a graph update we have to work through each input to check
            if it is a location. It's still much nicer than setting up a
            dozen hidden divs, timing callbacks, and writing long lines of
            logic to determine which was most recently updated.

            I need to incorporate the reset button here, it is not currently
            persistent...
            """
            # Find which input triggered this callback
            context = dash.callback_context
            trigger_value = context.triggered[0]["value"]
            trigger = context.triggered[0]["prop_id"]

            # Figure out which element we are working with
            key = int(key) - 1

            # With the outline we have twice the points, half of which are real
            if select1:
                plen = len(select1["points"])
                select1["points"] = select1["points"][int(plen / 2):]
            if select2:
                plen = len(select2["points"])
                select2["points"] = select2["points"][int(plen / 2):]

            # package all the selections for indexing
            locations = [click1, click2, select1, select2, county1, county2,
                         shape1, shape2, bbox1, bbox2, reset1, reset2, state1,
                         state2]
            updates = [update1, update2]

            # The outline points will also be in selected trigger values
            if "selectedData" in trigger:
                if trigger_value:
                    plen = len(trigger_value["points"])
                    tv = trigger_value["points"][int(plen/2):]
                    trigger_value["points"] = tv
                else:
                    location =  ["all", "y", "x", "Contiguous United States"]

            # Two cases, if syncing return a copy, if not split
            if "On" in sync:
                # The update graph button activates US state selections
                if "update_graph" in trigger:
                    if trigger_value is None:
                        trigger_value = "all"
                        sel_idx = 0
                        triggering_element = sel_idx % 2 + 1
                    else:
                        # The idx of the most recent update is -2 or -1
                        update_idx = updates.index(trigger_value) - 2
                        if locations[update_idx] is None:
                            raise PreventUpdate
                        trigger_value = locations[update_idx]
                        sel_idx = locations.index(trigger_value)
                        triggering_element = sel_idx % 2 + 1
                else:
                    sel_idx = locations.index(trigger_value)
                    triggering_element = sel_idx % 2 + 1

                # Use the triggered_value to create the selector object
                selector = Location_Builder(trigger, trigger_value, crdict,
                                            admin_df, state_array,
                                            county_array)

                # Retrieve information for the most recently updated element
                location = selector.chooseRecent()

                # What is this about? Must be some error condition
                if "shape" in location[0] and location[3] is None:
                    location =  ["all", "y", "x", "Contiguous United States"]

                # Add the triggering element key to prevent updates later
                try:
                    location.append(triggering_element)
                except:
                    raise PreventUpdate

            # If not syncing, only use the inputs for this element
            else:
                locations = locations[key::2]

                # That also means that the triggering element is this one
                triggering_element = key + 1

                # The update graph button activates US state selections
                if "update_graph" in trigger:
                    if trigger_value is None:
                        trigger_value = "all"
                    else:
                        # The idx of the most recent update is -2 or -1
                        # update_idx = updates.index(triggered_value) - 2
                        if locations[-1] is None:
                            raise PreventUpdate
                        trigger_value = locations[-1]

                # If this element wasn"t the trigger, prevent updates
                if trigger_value not in locations:
                    raise PreventUpdate

                # Use the triggered_value to create the selector object
                selector = Location_Builder(trigger, trigger_value,
                                            crdict, admin_df, state_array,
                                            county_array)

                # Retrieve information for the most recently updated element
                location = selector.chooseRecent()

                # What is this about?
                if "shape" in location[0] and location[3] is None:
                    location =  ["all", "y", "x", "Contiguous United States"]

                # Add the triggering element key to prevent updates later
                try:
                    location.append(triggering_element)
                except:
                    raise PreventUpdate

            return json.dumps(location)

    @app.callback(
        Output(f"download_chart_{i}", "data"),
        Input(f"download_path_store_{i}", "children"),
        prevent_initial_call=True,
    )
    @calls.log
    def download(download_info):
        """Download csv file."""
        info = json.loads(download_info)
        if info is None:
            raise PreventUpdate
        src = info["tmp_path"]
        dst = info["dst"]
        df = pd.read_csv(src)
        os.remove(src)
        return dcc.send_data_frame(df.to_csv, dst, index=False)

    @app.callback(
        Output("county_div_{}".format(i), "style"),
        Output("state_div_{}".format(i), "style"),
        Output("shape_div_{}".format(i), "style"),
        Input("location_tab_{}".format(i), "value"),
        Input("state_{}".format(i), "value"),
        State("key_{}".format(i), "children")
    )
    @calls.log
    def displayLocOptions(tab_choice, states, key):
        key = int(key)
        if tab_choice == "county":
            county_style = {}
            state_style = {"display": "none"}
            shape_style = {"display": "none"}
        elif tab_choice == "state":
            if states is not None:
                if len(states) <= 5:
                    font_size = 15
                else:
                    font_size = 8
            else:
                font_size = 15
            county_style = {"display": "none"}
            state_style = {"font-size": font_size}
            shape_style = {"display": "none"}
        else:
            county_style = {"display": "none"}
            state_style = {"display": "none"}
            shape_style = {}
        return county_style, state_style, shape_style

    @app.callback(
        Output("shape_store_{}".format(i), "children"),
        Input("shape_{}".format(i), "contents"),
        State("shape_{}".format(i), "filename"),
    )
    @calls.log
    def parseShape(contents, fpaths):
        """Parse a shapefile object."""
        if not contents:
            raise PreventUpdate
        parser = Parse_Shape(fpaths, contents)
        basename = parser.main()
        return basename

    @app.callback(
        Output("coverage_div_{}".format(i), "children"),
        Input("series_{}".format(i), "hoverData"),
        Input("dsci_button_{}".format(i), "n_clicks"),
        Input("submit", "n_clicks"),
        State("function_choice", "value")
    )
    @calls.log
    def hoverCoverage(hover, click1, click2, function):
        """
        The tooltips on the drought severity coverage area graph were
        overlapping, so this outputs the hover data to a chart below instead.
        """
        if function == "oarea":
            try:
                date = dt.datetime.strptime(hover["points"][0]["x"],
                                            "%Y-%m-%d")
                date = dt.datetime.strftime(date, "%b, %Y")
                if click1 % 2 == 0:
                    ds = ["{0:.2f}".format(hover["points"][i]["y"]) for
                          i in range(5)]
                    coverage_df = pd.DataFrame({"D0 - D4 (Dry)": ds[0],
                                                "D1 - D4 (Moderate)": ds[1],
                                                "D2 - D4 (Severe)": ds[2],
                                                "D3 - D4 (Extreme)": ds[3],
                                                "D4 (Exceptional)": ds[4]},
                                               index=[0])

                else:
                    ds = ["{0:.2f}".format(hover["points"][i]["y"]) for
                          i in range(6)]
                    coverage_df = pd.DataFrame(
                        {
                            "D0 - D4 (Dry)": ds[0],
                            "D1 - D4 (Moderate)": ds[1],
                            "D2 - D4 (Severe)": ds[2],
                            "D3 - D4 (Extreme)": ds[3],
                            "D4 (Exceptional)": ds[4],
                            "DSCI":ds[5]
                        },
                        index=[0]
                    )
                children=[
                    html.H6(
                        children=[date],
                        style={
                            "text-align": "left"
                        }
                    ),
                    dash_table.DataTable(
                      data=coverage_df.to_dict("rows"),
                        columns=[
                          {"name": i, "id": i} for i in coverage_df.columns],
                        style_cell={"textAlign": "center"},
                        style_header={"fontWeight": "bold"},
                        style_header_conditional=[
                                {"if": {"column_id": "D0 - D4 (Dry)"},
                                        "backgroundColor": "#ffff00",
                                        "color": "black"},
                                {"if": {"column_id": "D1 - D4 (Moderate)"},
                                        "backgroundColor": "#fcd37f",
                                         "color": "black"},
                                 {"if": {"column_id": "D2 - D4 (Severe)"},
                                        "backgroundColor": "#ffaa00",
                                        "color": "black"},
                                 {"if": {"column_id": "DSCI"},
                                        "backgroundColor": "#27397F",
                                        "color": "white",
                                        "width": "75"},
                                 {"if": {"column_id": "D3 - D4 (Extreme)"},
                                        "backgroundColor": "#e60000",
                                        "color": "white"},
                                 {"if": {"column_id": "D4 (Exceptional)"},
                                         "backgroundColor": "#730000",
                                         "color": "white"}
                         ],
                         style_data_conditional=[
                                 {"if": {"column_id": "D0 - D4 (Dry)"},
                                         "backgroundColor": "#ffffa5",
                                         "color": "black"},
                                 {"if": {"column_id": "D1 - D4 (Moderate)"},
                                         "backgroundColor": "#ffe5af",
                                         "color": "black"},
                                 {"if": {"column_id": "D2 - D4 (Severe)"},
                                         "backgroundColor": "#ffc554",
                                         "color": "black"},
                                 {"if": {"column_id": "DSCI"},
                                         "backgroundColor": "#5c678e",
                                         "color": "white",
                                         "width": "75"},
                                 {"if": {"column_id": "D3 - D4 (Extreme)"},
                                         "backgroundColor": "#dd6666",
                                         "color": "white"},
                                 {"if": {"column_id": "D4 (Exceptional)"},
                                         "backgroundColor": "#a35858",
                                         "color": "white"}
                        ]
                    )
                ]
            except:
                raise PreventUpdate
        else:
            children = None

        return children


    @app.callback(
        Output("dsci_button_{}".format(i), "style"),
        Output("dsci_button_{}".format(i), "children"),
        Input("submit", "n_clicks"),
        Input("dsci_button_{}".format(i), "n_clicks"),
        State("function_choice", "value")
    )
    @calls.log
    def displayDSCI(click1, click2, function):
        """
        Toggle the blue Drought Severity Coverage Index on and off for the
        drought area option.
        """
        style = STYLES["off_button_app"].copy()
        if function == "oarea":
            if click2 % 2 == 0:
                children = "Show DSCI: Off"
            else:
                style["background-color"] = "#ffff"
                children = "Show DSCI: On"
        else:
            children = "Show DSCI: Off"
            style = {"display": "none"}

        return style, children

    @app.callback(
        Output(f"map_{i}", "figure"),
        Input("choice_1", "value"),
        Input("choice_2", "value"),
        Input("map_type", "value"),
        Input("signal", "children"),
        Input(f"point_size_{i}", "value"),
        Input(f"color_min_{i}", "value"),
        Input(f"color_max_{i}", "value"),
        Input(f"location_store_{i}", "children"),
        State("function_choice", "value"),
        State(f"key_{i}", "children"),
        State("click_sync", "children"),
        State("date_sync", "children"),
        State("date_print_1", "children"),
        State("date_print_2", "children"),
        State(f"map_{i}", "relayoutData")
    )
    @calls.log
    def makeMap(choice1, choice2, map_type, signal, point_size, color_min,
                color_max, location, function, key, sync, date_sync,
                date_print_1, date_print_2, map_extent):
        """Build plotly scatter mapbox figure."""
        # Catch Trigger
        trigger = dash.callback_context.triggered[0]["prop_id"]

        # Reformat/unpack signals from user
        location = json.loads(location)
        signal = json.loads(signal)
        key = int(key)

        # Prevent update from location unless its a state, shape or bbox filter
        if trigger == f"location_store_{key}.children":
            if "corr" not in function:
                if location[0] in ["grids"]:
                    print("Preventing Map Update (Map point/selection trigger)")
                    raise PreventUpdate

            # Check which element the selection came from
            triggered_element = location[-1]
            if "On" not in sync:
                if triggered_element != key:
                    print("Preventing Update (not syncing this map)")
                    raise PreventUpdate

        # To save zoom levels and extent between map options
        if not map_extent:
            map_extent = DEFAULT_MAP_EXTENT
        elif "mapbox.center" not in map_extent.keys():
            map_extent = DEFAULT_MAP_EXTENT

        # If we are syncing times, use the key to find the right signal
        if "On" in date_sync:
            signal = signal[0]
            date_print = date_print_1
        else:
            signal = signal[key - 1]
            if key == 1:
                date_print = date_print_1
            else:
                date_print = date_print_2
        [year_range, [month1, month2], month_filter] = signal[0]
        colorscale, reverse = signal[1:]

        # DASH doesn't seem to like passing True/False as values
        verity = {"no": False, "yes":True}
        reverse = verity[reverse]

        # Figure which choice is this panel"s and which is the other
        key = int(key) - 1
        choices = [choice1, choice2]
        choice = choices[key]
        choice2 = choices[~key]

        # Get/cache data
        data = retrieveData(signal, function, choice, location)
        choice_reverse = data.reverse
        if choice_reverse:
            reverse = not reverse

        # Pull array into memory
        array = data.getFunction(function).compute()

        # Individual array min/max
        amin = np.nanmin(array)
        amax = np.nanmax(array)
        if color_min and not color_max:
            amin = color_min        
        if color_max and not color_min:
            amax = color_max
        if color_max and color_min:
            amax = color_max
            amin = color_min

        # Now, we want to use the same value range for colors for both maps
        nonindices = ["tdmean", "tmean", "tmin", "tmax", "ppt",  "vpdmax",
                      "vpdmin", "vpdmean"]
        if function == "pmean":
            # Get the data for the other panel for its value range
            data2 = retrieveData(signal, function, choice2, location)
            array2 = data2.getFunction(function).compute()
            amax2 = np.nanmax(array2)
            amin2 = np.nanmin(array2)
            amax = np.nanmax([amax, amax2])
            amin = np.nanmin([amin, amin2])
            del array2
        elif "min" in function or "max" in function:
            amax = amax
            amin = amin
        elif choice in nonindices:
            amax = amax
            amin = amin
        else:
            limit = np.nanmax([abs(amin), abs(amax)])
            amax = limit
            amin = limit * -1

        # Filter for state filters
        flag, y, x, label, idx = location
        if flag in ["state", "county", "shape"]:
            array = array * data.mask

        # If it is a correlation recreate the map array
        if "corr" in function and flag != "all":
            y = np.array(json.loads(y))
            x = np.array(json.loads(x))
            gridid = grid[y, x]
            if not color_min:
                amin = -1
            if not color_max:    
                amax = 1
            if isinstance(gridid, np.ndarray):
                grids = [np.nanmin(gridid), np.nanmax(gridid)]
                title = (Options.index_names[choice] + "<br>" +
                         Options.function_names[function] + "With Grids " +
                         str(int(grids[0]))  + " to " + str(int(grids[1])) +
                         "  ("  + date_print + ")")
                title_size = 15
            else:
                title = (Options.index_names[choice] + "<br>" +
                         Options.function_names[function] + "With Grid " +
                         str(int(gridid))  + "  ("  + date_print + ")")

            # This is the only map interaction that alters the map
            array = data.getCorr(location, crdict)  # <------------------------ Expected memory spike
            title_size = 20
        else:
            title = (Options.index_names[choice] + "<br>" + Options.function_names[function] +
                     ": " + date_print)
            title_size = 20

        # Create a data frame of coordinates, index values, labels, etc
        dfs = xr.DataArray(array, name="value")
        pdf = dfs.to_dataframe()
        step = crdict.res
        to_bin = lambda x: np.floor(x / step) * step
        pdf["latbin"] = pdf.index.get_level_values("latitude").map(to_bin)
        pdf["lonbin"] = pdf.index.get_level_values("longitude").map(to_bin)
        pdf["gridx"] = pdf["lonbin"].map(crdict.londict)
        pdf["gridy"] = pdf["latbin"].map(crdict.latdict)

        # For hover information
        grid2 = np.copy(grid)
        grid2[np.isnan(grid2)] = 0
        pdf["grid"] = grid2[pdf["gridy"], pdf["gridx"]]
        pdf = pd.merge(pdf, admin_df, how="inner")
        pdf["data"] = pdf["value"].astype(float)
        pdf["printdata"] = (
            pdf["place"] + "<br>  lat/lon: "
            + pdf["latbin"].apply(str) + ", "
            + pdf["lonbin"].astype(str) + "<br>     <b>"
            + pdf["data"].round(3).apply(str) + "</b>"
        )
        df_flat = pdf.drop_duplicates(subset=["latbin", "lonbin"])
        df = df_flat[np.isfinite(df_flat["data"])]

        # Create the scattermapbox object
        colorscale = data.color_scale
        d1 = dict(
            type="scattermapbox",
            lon=df["lonbin"],
            lat=df["latbin"],
            text=df["printdata"],
            hoverinfo="text",
            hovermode="closest",
            showlegend=False,
            marker=dict(
                color=df["data"],
                colorscale=colorscale,
                reversescale=reverse,
                cmax=amax,
                cmin=amin,
                size=point_size,
                colorbar=dict(
                    y=-.15,
                    textposition="bottom",
                    orientation="h",
                    font=dict(
                        size=15,
                        fontweight="bold"
                    )
                )
            )
        )

        # Add an outline to help see when zoomed in
        # d2 = dict(
        #     type="scattermapbox",
        #     lon=df["lonbin"],
        #     lat=df["latbin"],
        #     mode="markers",
        #     hovermode="closest",
        #     showlegend=False,
        #     marker=dict(
        #         color="#000000",
        #         size=point_size * 1.05
        #     )
        # )

        # package these in a list
        data_list = [d1]

        # Add shape if a single site is selected
        if location[0] == "grid":
            site = location[3]
            gridid = float(site[site.index("(Grid") + 6: site.index(")")])
            row = df[df["grid"] == gridid]
            # d3 = dict(
            #     type="scattermapbox",
            #     lon=row["lonbin"],
            #     lat=row["latbin"],
            #     mode="markers",
            #     hovermode="closest",
            #     showlegend=False,
            #     marker=dict(
            #         color="black",
            #         size=point_size * 3.5
            #     )
            # )
            d4 = dict(
                type="scattermapbox",
                lon=row["lonbin"],
                lat=row["latbin"],
                mode="markers",
                hovermode="closest",
                showlegend=False,
                marker=dict(
                    color="black",
                    size=point_size * 2
                )
            )
            data_list += [d4]

        # Set up layout
        layout_copy = copy.deepcopy(MAPBOX_LAYOUT)
        layout_copy["mapbox"]["style"] = map_type
        layout_copy["mapbox"]["center"] = map_extent["mapbox.center"]
        layout_copy["mapbox"]["zoom"] = map_extent["mapbox.zoom"]
        layout_copy["mapbox"]["bearing"] = map_extent["mapbox.bearing"]
        layout_copy["mapbox"]["pitch"] = map_extent["mapbox.pitch"]
        layout_copy["hoverlabel"] = dict(font=dict(size=20))
        layout_copy["titlefont"] = dict(
            color="#CCCCCC",
            size=title_size,
            family="Time New Roman",
            fontweight="bold"
        )
        layout_copy["title"] = title
        figure = dict(data=data_list, layout=layout_copy)

        # Clear memory space
        gc.collect()

        # Check on Memory
        print("\nCPU: {}% \nMemory: {}%\n".format(
            psutil.cpu_percent(),
            psutil.virtual_memory().percent)
        )

        return figure


    @app.callback(
        Output(f"series_{i}", "figure"),
        Output(f"area_store_{i}", "children"),
        Output(f"download_path_store_{i}", "children"),
        Input("submit", "n_clicks"),
        Input("signal", "children"),
        Input(f"choice_{i}", "value"),
        Input("choice_store", "children"),
        Input(f"location_store_{i}", "children"),
        Input(f"dsci_button_{i}", "n_clicks"),
        Input(f"color_min_{i}", "value"),
        Input(f"color_max_{i}", "value"),
        Input(f"download_all_link_{i}", "n_clicks"),
        Input(f"download_link_{i}", "n_clicks"),
        State(f"key_{i}", "children"),
        State("click_sync", "children"),
        State("date_sync", "children"),
        State("function_choice", "value"),
        State(f"area_store_{i}", "children")
    )
    @calls.log
    def makeSeries(submit, signal, choice, choice_store, location, show_dsci,
                   color_min, color_max, download, download_all, key, sync,
                   date_sync, function, area_store):
        """
        This makes the time series graph below the map.
        Sample arguments:
            signal = [[[2000, 2017], [1, 12], [5, 6, 7, 8]], "Viridis", "no"]
            choice = "pdsi"
            function = "oarea"
            location =  ["all", "y", "x", "Contiguous United States", 0]
        """
        # Prevent update from location unless it is a state filter
        trigger = dash.callback_context.triggered[0]["prop_id"]

        # Identify element number
        key = int(key)
        location = json.loads(location)

        # If we aren"t syncing or changing the function or color
        if trigger == f"location_store_{key}.children":
            triggered_element = location[-1]
            if "On" not in sync:
                if triggered_element != key:
                    raise PreventUpdate

        # Create signal for the global_store
        choice_store = json.loads(choice_store)
        signal = json.loads(signal)

        # If we are syncing times, use the key to find the right signal
        if "On" in date_sync:
            signal = signal[0]
        else:
            signal = signal[key - 1]

        # Collect signals
        [year_range, [month1, month2], month_filter] = signal[0]
        [colorscale, reverse] = signal[1:]

        # DASH doesn"t seem to like passing True/False as values
        verity = {"no": False, "yes": True}
        reverse = verity[reverse]

        # Get/cache data
        data = retrieveData(signal, function, choice, location)
        choice_reverse = data.reverse
        if choice_reverse:
            reverse = not reverse
        dates = data.dataset_interval.time.values
        dates = [pd.to_datetime(str(d)).strftime("%Y-%m") for d in dates]
        dmin = data.data_min
        dmax = data.data_max

        # Now, before we calculate the time series, there is some area business
        area_store_key = str(signal) + "_" + choice + "_" + str(location)
        area_store = json.loads(area_store)

        # Create the label for the plots, so sorry this is so complex
        label = location[3]
        if location[0] == "shape":
            path = Path(label)
            ext = path.suffix
            label = path.name.replace(ext, "")

        # If the function is oarea, we plot five overlapping timeseries
        nonindices = ["tdmean", "tmean", "tmin", "tmax", "ppt",  "vpdmax",
                      "vpdmin", "vpdmean"]
        if function != "oarea" or choice in nonindices:
            # Get the time series from the data object
            timeseries = data.getSeries(location, crdict)

            # Create data frame as string for download option
            columns = OrderedDict({
                "month": dates,
                "value": list(timeseries),
                "function": FUNCTION_NAMES[function],  # <-- This doesn"t always make sense
                "location": location[-2],
                "index": INDEX_NAMES[choice]
            })
            df = pd.DataFrame(columns)
            bar_type = "bar"
            area_store = ["", ""]
            if choice in nonindices and function == "oarea":
                label = "(Drought Severity Categories Not Available)"
        else:
            bar_type = "overlay"
            label = location[3]
            if location[0] == "shape":
                path = Path(label)
                ext = path.suffix
                label = path.name.replace(ext, "")

            # I cannot get this thing to cache! We are storing it in a Div
            if area_store_key == area_store[0]:
                ts_series, ts_series_ninc, dsci = area_store[1]
            else:
                ts_series, ts_series_ninc, dsci = data.getArea(crdict)

            # This needs to be returned either way
            series = [ts_series, ts_series_ninc, dsci]
            area_store = [area_store_key, series, dates]

            # Save to file for download option
            columns = OrderedDict({
                "month": dates,
                "d0": ts_series_ninc[0],
                "d1": ts_series_ninc[1],
                "d2": ts_series_ninc[2],
                "d3": ts_series_ninc[3],
                "d4": ts_series_ninc[4],
                "dsci": dsci,
                "function": "Percent Area",
                "location":  label,
                "index": INDEX_NAMES[choice]
            })
            df = pd.DataFrame(columns)

        # Write to file for download
        download_info = None
        if "download_" in trigger:
            tmp_path = "/tmp/drip_timeseries.csv"
            if "all_link" in trigger:
                dst = f"drip_timeseries_all_{key}.csv"
                df = makeCSVs(signal, function, location)
            else:
                dst = f"drip_timeseries_{key}.csv"
                df = makeCSV((choice, signal, function, location, crdict))
            download_info = {
                "dst": dst,
                "tmp_path": tmp_path
            }
            df.to_csv(tmp_path, index=False)

        # Set up y-axis depending on selection
        if function != "oarea" or choice in nonindices:
            if "p" in function:
                yaxis = dict(title="Percentiles", range=[0, 100])
            elif "o" in function:
                yaxis = dict(range=[dmin, dmax], title=UNIT_MAP[choice])

                # Center the color scale
                xmask = data.mask
                sd = data.dataset_interval.where(xmask == 1).std()
                sd = float(sd.compute().value) # Sheesh
                if "eddi" in choice:
                    sd = sd * -1
                dmin = 3 * sd
                dmax = 3 * sd * -1

        # A few pieces to incorporate in to Index_Maps later
        if "corr" in function:
            reverse = not reverse
            if "p" in function:
                dmin = 0
                dmax = 100

        # Individual array min/max
        if color_min and not color_max:
            dmin = color_min        
        if color_max and not color_min:
            dmax = color_max
        if color_max and color_min:
            dmax = color_max
            dmin = color_min

        # The drought area graphs have there own configuration
        elif function == "oarea" and choice not in nonindices:
            yaxis = dict(
                title="Percent Area (%)",
                range=[0, 100],
                hovermode="y"
            )

        # Build the plotly readable dictionaries (Two types)
        if function != "oarea" or choice in nonindices:
            data = [
                dict(
                    type="bar",
                    x=dates,
                    y=timeseries,
                    marker=dict(
                        color=timeseries,
                        colorscale=data.color_scale,
                        reversescale=reverse,
                        autocolorscale=False,
                        cmin=dmin,
                        cmax=dmax,
                        line=dict(
                            width=0.2,
                            color="#000000"
                        )
                    )
                )
            ]

        else:
            # The drought area data
            colors = ["rgb(255, 255, 0)","rgb(252, 211, 127)",
                      "rgb(255, 170, 0)", "rgb(230, 0, 0)", "rgb(115, 0, 0)"]
            if year_range[0] != year_range[1]:
                line_width = 1 + ((1/(year_range[1] - year_range[0])) * 25)
            else:
                line_width = 12
            data = []
            for i in range(5):
                trace = dict(type="scatter",
                              fill="tozeroy",
                              mode="none",
                              showlegend=False,
                              x=dates,
                              y=ts_series[i],
                              hoverinfo="x",
                              fillcolor=colors[i])
                data.append(trace)

            # Toggle the DSCI
            if show_dsci % 2 != 0:
                dsci_data = dict(
                    x=dates,
                    y=dsci,
                    yaxis="y2",
                    hoverinfo="x",
                    showlegend=False,
                    line=dict(
                        color="rgba(39, 57, 127, 0.85)",
                        width=line_width
                    )
                )
                data.insert(5, dsci_data)

        # Copy and customize Layout
        if label is None:
            label = "Existing Shapefile"
        layout_copy = copy.deepcopy(MAPBOX_LAYOUT)
        layout_copy["title"] = INDEX_NAMES[choice] + "<Br>" + label
        layout_copy["plot_bgcolor"] = "white"
        layout_copy["paper_bgcolor"] = "white"
        layout_copy["margin"]["b"] = 50
        layout_copy["height"] = 400
        layout_copy["yaxis"] = yaxis
        layout_copy["font"] = dict(family="Time New Roman")
        layout_copy["hoverlabel"] = dict(font=dict(size=24))
        if function == "oarea":
            if type(location[0]) is int:
                layout_copy["title"] = (INDEX_NAMES[choice] +
                                        "<Br>" + "Contiguous US " +
                                        "(point estimates not available)")
            layout_copy["xaxis"] = dict(
                type="date",
                font=dict(family="Times New Roman")
            )
            layout_copy["yaxis2"] = dict(
                title="<br>DSCI",
                range=[0, 500],
                anchor="x",
                overlaying="y",
                side="right",
                position=0.15
            )
            layout_copy["margin"] = dict(l=55, r=55, b=50, t=90, pad=10)
        layout_copy["hovermode"] = "x"
        layout_copy["barmode"] = bar_type
        layout_copy["legend"] = dict(
            orientation="h",
            y=-.5,
            markers=dict(size=10),
            font=dict(size=10)
        )
        layout_copy["titlefont"]["color"] = "#636363"
        layout_copy["font"]["color"] = "#636363"

        figure = dict(data=data, layout=layout_copy)

        return figure, json.dumps(area_store), json.dumps(download_info)
