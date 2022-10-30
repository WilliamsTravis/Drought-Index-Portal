"""Drip main page options."""
import pandas as pd
import xarray as xr

from drip.app.options.colors import COLORS
from drip.app.options.indices import INDEX_NAMES, INDEX_OPTIONS
from drip.loggers import init_logger, set_handler
from drip.paths import Paths

logger = init_logger(__name__)


MONTH_LABELS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec"
}

# Make the signal a dictionary
DEFAULT_SIGNAL = [
    [[[1980, 2021], [1, 12], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]], 
     "Default", "no"],
    [[[2000, 2021], [1, 12], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]], 
     "Default", "no"]
]
DEFAULT_CHOICE = "spi1"
DEFAULT_FUNCTION = "omean"
DEFAULT_LOCATION = ["grids", "[10, 11, 11, 11, 12, 12, 12, 12]",
                    "[243, 242, 243, 244, 241, 242, 243, 244]",
                    "Aroostook County, ME to Aroostook County, ME", 2]


class Options(Paths):
    """Methods for retrieving updated default options and values."""

    def __init__(self):
        """Initialize Drip_Defaults object."""

    def __repr__(self):
        """Return representation string for Drip_Defaults object."""

    @classmethod
    @property
    def base_maps(cls):
        """Return list of MapBox Basemap options."""
        base_maps = [
            {"label": "Light", "value": "light"},
            {"label": "Dark", "value": "dark"},
            {"label": "Basic", "value": "basic"},
            {"label": "Outdoors", "value": "outdoors"},
            {"label": "Satellite", "value": "satellite"},
            {"label": "Satellite Streets", "value": "satellite-streets"},
            {"label": "White", "value": "white-bg"},
            {"label": "Open Street Map", "value": "open-street-map"},
            {"label": "Carto Positron", "value": "carto-positron"},
            {"label": "Carto Dark Matter", "value": "carto-darkmatter"},
            {"label": "Stamen Terrain", "value": "stamen-terrain"},
            {"label": "Stamen Toner", "value": "stamen-toner"},
            {"label": "Stamen Watercolor", "value": "stamen-watercolor"},
        ]
        return base_maps

    @classmethod
    @property
    def colors(cls):
        """Return list of color scale options."""
        return [{"label": k, "value": k} for k, _ in COLORS.items()]

    @classmethod
    @property
    def counties(cls):
        """Return county option list."""
        df = pd.read_csv(cls.paths["tables"].joinpath("unique_counties.csv"))
        options = []
        for idx, row in df.iterrows():
            options.append({"label": row["place"], "value": row["fips"]})
        return options

    @classmethod
    @property
    def dates(cls):
        """Return minimum and maxmium dates in sample dataset."""
        with xr.open_dataset(cls.sample_path) as data:
            min_date = data.time.data[0]
            max_date = data.time.data[-1]
        dates = {}
        dates["max_year"] = pd.Timestamp(max_date).year
        dates["min_year"] = pd.Timestamp(min_date).year + 1  # for 12 month indices
        dates["max_month"] = pd.Timestamp(max_date).month
        dates["years"] = list(range(dates["min_year"], dates["max_year"] + 1))
        return dates

    @classmethod
    @property
    def date_marks(cls):
        """Return slider tick marks for year sliders."""
        min_year = cls.dates["min_year"]
        max_year = cls.dates["max_year"]
        years = {}
        for i, y in enumerate(cls.dates["years"]):
            ymark = str(y)
            if y % 5 != 0 and y != min_year and y != max_year:  
                ymark = ""
            years[y] = {
                "label": ymark,
                "style": {"transform": "rotate(45deg)"}
            }

        months = []
        months_slanted = {}
        for m in list(range(1, 13)):
            months.append({"label": MONTH_LABELS[m], "value": m})
            months_slanted[m] = {
                "label": MONTH_LABELS[m],
                "style": {"transform": "rotate(45deg)"}
            }

        marks = {
            "years": years,
            "months": months,
            "months_slanted": months_slanted
        }

        return marks

    @classmethod
    @property
    def functions(cls):
        """Return function option lists."""
        main = [
            {"label": "Mean", "value": "omean"},
            {"label": "Maximum", "value": "omax"},
            {"label": "Minimum", "value": "omin"},
            {"label": "Drought Severity Area", "value":"oarea"},
            {"label": "Correlation", "value": "ocorr"}
        ]
        percentile = [
            {"label": "Mean", "value": "pmean"},
            {"label": "Maximum", "value": "pmax"},
            {"label": "Minimum", "value": "pmin"},
            {"label": "Correlation", "value": "pcorr"}
        ]
        functions = {"main": main, "percentile": percentile}
        return functions

    @classmethod
    @property
    def function_names(cls):
        """Return function key-name dictionary."""
        names = {
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
        return names

    @classmethod
    @property
    def index_keys(cls):
        """Return list of keys for existing indices."""
        return list(cls.indices.keys())

    @classmethod
    @property
    def index_options(cls):
        """Return index options list."""
        options = []
        for entry in INDEX_OPTIONS:
            if entry["value"] in cls.index_keys:
                options.append(entry)
        return options

    @classmethod
    @property
    def index_names(cls):
        """Return index key-name dictionary."""
        names = {}
        for key, name in INDEX_NAMES.items():
            if key in cls.index_keys:
                names[key] = name
        return names

    @classmethod
    @property
    def sample_path(cls):
        """Return a sample path for an existing drought index netcdf file."""
        path = cls.indices[cls.index_keys[-1]]
        try:
            path.exists()
            return path
        except AssertionError:
             logger.error("Error retrieving sample dataset for default values"
                          "%s does not exist.", path)

    @classmethod
    @property
    def states(cls):
        """Return state option list."""
        nconus = ["AK", "AS", "DC", "GU", "HI", "MP", "PR", "UM", "VI"]
        fpath = cls.paths["tables"].joinpath("state_fips.txt")
        df = pd.read_table(fpath, sep="|")
        df = df.sort_values("STUSAB")
        df = df[~df.STUSAB.isin(nconus)]

        options = []
        for idx, row in df.iterrows():
            options.append({"label": row["STUSAB"], "value": row["STATE"]})
        options.insert(0, {"label": "ALL STATES IN CONUS", "value": "all"})

        return options

    @classmethod
    @property
    def transform(cls):
        """Return geotransform of sample dataset."""
        with xr.open_dataset(cls.sample_path) as data:
            transform = data.crs.GeoTransform
        return transform
