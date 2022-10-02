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
from drip.app.options.indices import INDEX_NAMES

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

    @classmethod
    @property
    def indices(cls):
        """Return list of paths to index netcdfs."""
        paths = list(cls.paths["indices"].glob("*.nc"))
        paths.sort()
        indices = {}
        for path in paths:
            name = path.name.replace(".nc", "")
            indices[name] = path
        return indices
