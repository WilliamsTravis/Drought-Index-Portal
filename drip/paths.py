# -*- coding: utf-8 -*-
"""Retrieve/Build input datasets.

Created on Sat Mar  5 10:33:33 2022

@author: travis
"""
import datetime as dt
import os

from importlib import resources
from pathlib import Path

import drip

from drip.exceptions import ParameterError
from drip.loggers import init_logger, set_handler
from drip.options import INDEX_NAMES

logger = init_logger(__name__)


class Paths:
    """Methods for handling paths to package data."""

    @classmethod
    @property
    def paths(cls):
        """Return posix path objects for package data items."""
        contents = resources.files(drip.__name__)
        data = [file for file in contents.iterdir() if file.name == "data"][0]
        paths = {}
        for folder in data.iterdir():
            name = os.path.splitext(folder.name)[0].lower()
            paths[name] = folder
        return paths

    @classmethod
    @property
    def home(cls):
        """Return application home directory."""
        return resources.files(drip.__name__).parent


# class ModelPaths(Paths):
#     """Methods for accessing insurance model input data paths."""

#     def __init__(self, home=".", index="ri", actuarial_year=2017):
#         """Initialize ModelPaths object.

#         Parameters
#         ----------
#         home_dir : str
#             Path to application project directory.
#         index : str
#             Key for target weather index.
#         actuarial_year : int
#             Actuarial year to use for model. Only 2017 and 2018 are available.
#         """
#         self.home = Path(home).absolute().expanduser()
#         self.index = index
#         self.actuarial_year = actuarial_year
#         self._check_year()
#         self._set_logger()

#     def __repr__(self):
#         """Return InsuranceModel representation string."""
#         name = self.__class__.__name__
#         attrs = ", ".join([f"{k}={v}" for k, v in self.__dict__.items()])
#         return f"<{name} object: {attrs}>"

#     @property
#     def allocations_min_paths(self):
#         """Return min allocation paths for each interval and strike level."""
#         year = str(self.actuarial_year)
#         rdir = self.paths["actuarial"]
#         rdir = rdir.joinpath(year, "bases", "allocations")
#         paths = list(rdir.joinpath("min").glob("*tif"))
#         path_dict = self._to_dict(paths)
#         return path_dict

#     @property
#     def allocations_max_paths(self):
#         """Return max allocation paths for each interval and strike level."""
#         year = str(self.actuarial_year)
#         rdir = self.paths["actuarial"]
#         rdir = rdir.joinpath(year, "bases", "allocations")
#         paths = list(rdir.joinpath("max").glob("*tif"))
#         path_dict = self._to_dict(paths)
#         return path_dict

#     @property
#     def base_rate_paths(self):
#         """Return county base rates for each interval."""
#         year = str(self.actuarial_year)
#         rdir = self.paths["actuarial"].joinpath(year, "bases")
#         paths = list(rdir.joinpath("rates").glob("*tif"))
#         path_dict = self._to_dict(paths)
#         return path_dict

#     @classmethod
#     @property
#     def grid_path(cls):
#         """Return path to RMA grid IDs raster."""
#         return cls.paths["rma"].joinpath("prfgrid.tif")

#     @classmethod
#     @property
#     def index_names(cls):
#         """Return list of available index options."""
#         names = {}
#         keys = list(cls.index_paths.keys())
#         for key, value in INDEX_NAMES.items():
#             if key in keys:
#                 names[key] = value
#         return names

#     @property
#     def index_path(self):
#         """Return list of available index paths."""
#         path = self.paths["indices"].joinpath(self.index + ".nc")
#         if self.index not in self.index_paths:
#             logger.error("File for %s not found. Expected path "
#                           "to file: %s", self.index, path)
#             raise OSError(f"File for {self.index} not found. Expected path "
#                           f"to file: {path}")
#         return path

#     @classmethod
#     @property
#     def index_paths(self):
#         """Return list of available index paths."""
#         paths = {}
#         for path in list(Paths.paths["indices"].glob("*nc")):
#             key = path.name.split(".")[0]
#             paths[key] = path
#         return paths

#     @property
#     def premium_paths(self):
#         """Return premium rates for each interval and strike level."""
#         year = str(self.actuarial_year)
#         rdir = self.paths["actuarial"].joinpath(year, "premiums")
#         paths = list(rdir.glob("*tif"))
#         path_dict = self._to_dict(paths)
#         return path_dict

#     def _check_year(self):
#         """Check that the requested actuarial year is available."""
#         actuarial_content = list(self.paths["actuarial"].glob("*"))
#         folders = [c for c in actuarial_content if c.is_dir()]
#         years = [int(f.name) for f in folders]
#         year = self.actuarial_year
#         if year not in years:
#             years = [str(y) for y in years]
#             years = ", ".join(years)
#             logger.error("Actuarial year %i not available.", year)
#             raise ParameterError(f"Actuarial year {year} not available. "
#                                  f"Currently available years: {years}.")

#     def _set_logger(self):
#         """Setup logging file for InsuranceModel instance."""
#         today = dt.datetime.now()
#         date = today.strftime("%m/%d/%Y")
#         fname = f"runs_{today.strftime('%Y_%m_%d')}.log"
#         filename = self.home.joinpath("logs", fname)
#         filename.parent.mkdir(exist_ok=True)
#         set_handler(logger, filename)
#         logger.info("Experimental PRF logs for %s\n", date)

#     def _to_dict(self, paths):
#         """Organize paths by interval and/or strike levels."""
#         paths.sort()
#         path_dict = {}

#         if len(paths[0].name.split("_")) == 2:
#             for path in paths:
#                 interval = int(path.name.replace(".tif", "").split("_")[1])
#                 path_dict[interval] = path

#         elif len(paths[0].name.split("_")) == 3:
#             for path in paths:
#                 strike = int(path.name.replace(".tif", "").split("_")[1])
#                 interval = int(path.name.replace(".tif", "").split("_")[2])
#                 if interval not in path_dict:
#                     path_dict[interval] = {}
#                 path_dict[interval][strike] = path

#         else:
#             raise KeyError(f"Incorrectly formatted path name: {paths[0]}")

#         return path_dict
