
# -*- coding: utf-8 -*-
"""WWDT Downloader.

Methods to download and format West Wide Drought Tracker datasets.

Notes:
    Watch for this resampling error:
        "failed to prevent overwriting existing key grid_mapping in attrs."
    Is only periodic, check for this before overwritting original.


Created on Sat May 14 13:09:51 2022

@author: travis
"""
import json
import os
import shutil
import time
import warnings

from multiprocessing.pool import ThreadPool
from pathlib import Path

import dask
import numpy as np
import xarray as xr

from rasterio.enums import Resampling

import drip

from drip.downloaders.utilities import (
    set_georeferencing,
    Downloader
)
from drip.loggers import init_logger, set_handler
from drip.options import INDEX_NAMES

logger = init_logger(__name__)


PRISM_URL = "https://wrcc.dri.edu/wwdt/data/PRISM"


class Adjustments(Downloader):
    """Methods to adjust original drought index."""

    def __init__(self):
        """Initialize DroughtAdjust object."""
        super().__init__()
    
    def normalize(self, array):
        """Standardize index values to a 0.0-1.0 range."""
        array = (array - array.min()) / (array.max() - array.min())
        return array


class WWDT_Builder(Adjustments):
    """Methods for downloading and formatting selected data from the WWDT."""

    def __init__(self, index, resolution=0.25, template=None,
                 std_limit=3):
        """Initialize DIBuilder object.

        Parameters
        ----------
        index : str
            Index key. Must be in prf.options.INDEX_NAMES.
        resolution : float
            Resolution of target drought index NetCDF4 file in decimal degrees.
        template : str
            Path to file to use as template for georeferencing.
        """
        super().__init__()
        self.url = PRISM_URL
        self.resolution = resolution
        self.template = template
        self.set_index(index)
        self._set_logger(index)

    def __repr__(self):
        """Print representation string."""
        argstr = ", ".join([f"{k}='{v}'" for k, v in self.__dict__.items()])
        return f"<DIBuilder object: {argstr}>"

    def build(self, overwrite=False):
        """Download and combine multiple NetCDF files from WWDT into one."""
        dst = self.final_path
        if dst.exists() and not overwrite:
            logger.info("%s exists, skipping.", dst)
        else:
            start = time.time()
            logger.info("Building %s...", dst)

            self.download_all(self.index_paths)
            self.resample_all()
            self.combine()

            logger.info("Removing %s", self.combined_path.parent)
            shutil.rmtree(self.combined_path.parent)

            end = time.time()
            duration = round((end - start) / 60, 2)
            logger.info("%s completed in %f minutes.", dst, duration)

    def combine(self):
        """Combine monthly WWDT files into one."""
        logger.info("Combining monthly %s files into singular timeseries...",
                    self.index)

        # Get all monthly file paths
        paths = [entry["dst"] for entry in self.index_paths]

        # Combine by day dimension
        try:
            chunk_option = "array.slicing.split_large_chunks"
            with dask.config.set(**{chunk_option: False}):
                data = xr.open_mfdataset(
                    paths,
                    combine="nested",
                    concat_dim="day"
                )

                # Resort by day
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    data = data.sortby("day")

                # Check that it was concatenated correctly
                single = xr.open_dataset(paths[0])
                lonshape = single["longitude"].shape[0]
                latshape = single["latitude"].shape[0]
                tshape = (lonshape, latshape)
                lonshape = data["longitude"].shape[0]
                latshape = data["latitude"].shape[0]
                nshape = (lonshape, latshape)
                assert tshape == nshape

                # Change dataset name to 'index'
                data = data.rename({"data": "index"})

                # Write to file
                data.to_netcdf(self.combined_path)

            logger.info("Build for %s complete.", self.combined_path)

        except AssertionError:
            print(f"Combination of {self.index} failed with incorrect shape: "
                  f"target spatial shape: {tshape}, generated spatial shape "
                  f"{nshape}")
            logger.error("Combination of %s failed with incorrect "
                         "shape: target spatial shape: %s, "
                         "generated spatial shape %s", self.index,
                         str(tshape), str(nshape))
            raise

        except Exception as error:
            print(error.__dict__)
            print(f"Combination of {self.index} failed with error "
                  f"message: {type(error)}, {error}")
            logger.error("Combination of %s failed. %s: %s", self.index,
                         type(error), error)
            raise

    @property
    def combined_path(self):
        """Return path for all year, 12-monthly combined dataset."""
        return self.home.joinpath(self.index, self.index + ".nc")

    @property
    def final_path(self):
        """Return final path for indexed NetCDF file."""
        return self.home.joinpath(self.index + ".nc")

    @property
    def home(self):
        """Return data home directory."""
        return self.paths["indices"]

    @property
    def index_paths(self):
        """Return list of remote urls and local destination paths."""
        paths = []
        for i in range(1, 13):
            url = os.path.join(
                self.url,
                f"{self.index}/{self.index}_{i}_PRISM.nc"
            )
            fname = f"{self.index}_{i:02d}_temp.nc"
            dst = self.home.joinpath(f"{self.index}/{fname}")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            entry = {"url": url, "dst": dst}
            paths.append(entry)

        return paths

    def resample(self, path):
        """Resample indices to target resolution."""
        dst = str(path).replace(".nc", "_2.nc")
        path = str(path)
        with xr.open_dataset(path) as data:
            data = set_georeferencing(self.index, data)

            if not self.template:
                if data.rio.resolution()[0] != self.resolution:
                    logger.info("Resampling %s to %f decimal degrees...", path,
                                self.resolution)
                    try:
                        ndata = data.rio.reproject(
                            data.rio.crs,
                            transform=self.resolution,
                            resampling=Resampling.bilinear
                        )
                        ndata.to_netcdf(dst)
                        ndata.close()
                        logger.info("Resampling %s to %f complete.", path,
                                    self.resolution)
                    except Exception as error:
                        print(error.__dict__)
                        print(f"Resampling {path} failed with error message: "
                            f"{type(error)}, {error}")
                        logger.error("Resampling %s failed. %s: %s", path,
                                    type(error), error)
                else:
                    logger.info("%s already has %f resolution, skipping...",
                                path, self.resolution)

            else:
                logger.info("Reprojecting %s to match georeferencing of "
                            "%s ...", path, self.template)

                # Reproject Matching requires x and y dim names
                templ = xr.open_dataset(self.template)
                templ = set_georeferencing(self.index, templ, xy=True)
                data = set_georeferencing(self.index, data, xy=True)

                try:
                    ndata = data.rio.reproject_match(
                        match_data_array=templ["index"],
                        resampling=Resampling.bilinear
                    )
                    ndata = set_georeferencing(self.index, ndata)
                    ndata.to_netcdf(dst)
                    templ.close()
                    ndata.close()
                except Exception as error:
                    print(error.__dict__)
                    print(f"Resampling {path} failed with error message: "
                          f"{type(error)}, {error}")
                    logger.error("Resampling %s failed. %s: %s", path,
                                type(error), error)

                path = Path(path)
                tmp = path.parent.joinpath("tmp", path.name)
                tmp.parent.mkdir(exist_ok=True)
                shutil.move(path, tmp)
                shutil.move(dst, path)
                logger.info("Reprojection of %s to match %s complete.", path,
                            self.template)

    def resample_all(self):
        """Resample all downloading monthly files to target resolution."""
        paths = [entry["dst"] for entry in self.index_paths]
        with ThreadPool(os.cpu_count() - 1) as pool:
            for _ in pool.imap(self.resample, paths):
                pass

    def set_index(self, index):
        """Set the index key and index name.

        Parameters
        ----------
        index : str
            Index key. Must be in prf.options.INDEX_NAMES.
        """
        if index not in INDEX_NAMES:
            available_keys = ", ".join(list(INDEX_NAMES.keys()))
            msg = (f"{index} key is not avaiable. Available keys: "
                   f"{available_keys}")
            logger.error(msg)
            raise KeyError(msg)
        self.index = index
        self.index_name = INDEX_NAMES[index]

    def _set_logger(self, index):
        """Create logging file handler for this process."""
        filename = self.home.joinpath("logs", index + ".log")
        set_handler(logger, filename)
