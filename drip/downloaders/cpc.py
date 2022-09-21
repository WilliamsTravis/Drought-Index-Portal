# -*- coding: utf-8 -*-
"""CPC Downloader.

Methods to download and format Climate Prediction Center datasets.

Created on Sat May 14 13:10:00 2022

@author: travis
"""
import datetime as dt
import os
import shutil
import time

from functools import cached_property, lru_cache
from multiprocessing.pool import ThreadPool
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio as rio
import requests
import rioxarray as xrio
import xarray as xr

from bs4 import BeautifulSoup
from tqdm import tqdm

from drip.downloaders.utilities import (
    isint,
    set_georeferencing,
    Downloader
)
from drip.loggers import init_logger, set_handler

logger = init_logger(__name__)


CPC_URL = ("https://downloads.psl.noaa.gov/Datasets/cpc_us_precip/"
           "precip.V1.0.mon.mean.nc")
CPC_V1_URL = "https://ftp.cpc.ncep.noaa.gov/precip/CPC_UNI_PRCP/GAUGE_CONUS/"


class Current_Builder(Downloader):
    """Methods for downloading and building the current CPC Rainfall index."""

    def __init__(self):
        """Initialize CPCBuilder object."""
        super().__init__()
        self.c_index = "ri"
        self.c_url = CPC_URL
        self.ri_path = self.paths["indices"].joinpath(
            "ri",
            os.path.basename(self.c_url)
        )
        self._set_logger()

    def __repr__(self):
        """Print representation string."""
        name = self.__class__.__name__
        argstr = ", ".join([f"{k}='{v}'" for k, v in self.__dict__.items()])
        return f"<{name} object: {argstr}>"

    def baselines(self, year1=1948, year2=2016):
        """Return average value for each month across time period."""
        if self.interval_path.exists():
            path = self.interval_path
            with xr.open_dataset(path, mask_and_scale=True) as data:
                interval_idx = data.groupby("time.month").groups
                baselines = {}
                for interval, idx in interval_idx.items():
                    mdata = data.isel(time=idx)
                    mdata = mdata.mean(dim="time")
                    baselines[interval] = mdata["precip"]
            return baselines
        else:
            raise OSError("f{self.interval_path} does not exist.")

    def build_cpc(self, overwrite=False):
        """Download CPC Precipitation file and build index."""
        start = time.time()
        dst = self.ri_path
        entry = {"url": self.c_url, "dst": dst}

        if os.path.exists(dst) and overwrite:
            logger.info("Removing existing file: %s...", dst)
            os.remove(dst)

        if not dst.exists():
            self.download(entry)
            self._fix_georeferencing()
            adjust_intervals(self.ri_path, self.interval_path, time_dim="time")
            self.calc_index()

        end = time.time()
        duration = round((end - start) / 60, 2)
        logger.info("%s built in %f minutes.", dst, duration)

    def calc_index(self, year1=1948, year2=2016):
        """Index values by mean since given year."""
        if self.interval_path.exists():
            path = self.interval_path
            baselines = self.baselines(year1, year2)
            indices = []
            with xr.open_dataset(path, mask_and_scale=True) as data:
                # data = xr.open_dataset(path, mask_and_scale=True)
                interval_idx = data.groupby("time.month").groups
                for interval, idx in interval_idx.items():
                    window = data.isel(time=idx)
                    baseline = baselines[interval]    
                    window["precip"] = window["precip"] / baseline
                    window = window.rename({"precip": "index"})
                    indices.append(window)
            index = xr.concat(indices, dim="time").sortby("time")
            if self.final_path.exists():
                os.remove(self.final_path)
            index.to_netcdf(self.final_path)
        else:
            raise OSError("f{self.interval_path} does not exist.")

    @property
    def home(self):
        """Return data home directory."""
        return self.paths["indices"]

    @property
    def interval_path(self):
        """Path to file regrouped into 11 intervals."""
        return self.home.joinpath(self.c_index, "ri.nc")

    @property
    def final_path(self):
        """Return final path for indexed NetCDF file."""
        return self.home.joinpath("ri.nc")

    def _fix_georeferencing(self):
        """Fix georeferencing in raw rainfall data."""
        logger.info("Fixing georeferencing information in %s", self.ri_path)

        # Set the coordinate reference system for rasterio methods
        with xr.open_dataset(self.ri_path, engine="netcdf4") as data:
            # data = xr.open_dataset(self.ri_path)
            data = set_georeferencing("ri", data)

            # Change longitude range and rebuild this coordinate dataset
            lons = data["longitude"].data - 360
            data = data.assign_coords({"longitude": lons})
            data["longitude"].attrs = {
                "units": "degrees_east",
                "long_name": "Longitude",
                "actual_range": [
                    data["longitude"].data.min(),
                    data["longitude"].data.max()
                ]
            }

            # The default nan value (-9.96921e+36) throws overflow warnings
            navalue = -9999
            data["precip"].data[np.isnan(data["precip"].data)] = navalue
            data["precip"].encoding["missing_value"] = -9999
            data["precip"].encoding["_FillValue"] = -9999

            # Overwrite download path
            os.remove(self.ri_path)
            data.to_netcdf(self.ri_path)

        logger.info("Georeferencing information adjusted, overwriting %s",
                    self.ri_path)

    def _set_logger(self):
        """Create logging file handler for this process."""
        filename = self.paths["indices"].joinpath("logs", "ri.log")
        set_handler(logger, filename)


class CPC_Builder(Current_Builder):
    """Methods for downloading and building the CPC Rainfall index."""

    def __init__(self):
        """Initialize RIBuilder object."""
        super().__init__()
        self.o_index = "riv1"
        self.o_url = CPC_V1_URL
        self.ri1_path = self.paths["indices"].joinpath(
            self.o_index,
            os.path.basename(self.o_url)
        )
        self.ri1_path.mkdir(exist_ok=True)
        self._set_logger()

    def __repr__(self):
        """Print representation string."""
        name = self.__class__.__name__
        argstr = ", ".join([f"{k}='{v}'" for k, v in self.__dict__.items()])
        return f"<{name} object: {argstr}>"

    def build(self, overwrite=False, original=False):
        """Build the desired rainfall index."""
        if original:
            self.build_original(overwrite=overwrite)
        else:
            self.build_cpc(overwrite=overwrite)

    def build_original(self, overwrite=False):
        """Download original CPC Precipitation files and build index."""
        # Build the target path and check if it exists
        dst = self.home.joinpath("riv1.nc")
        if dst.exists() and overwrite:
            logger.info("Removing existing file: %s...", dst)
            os.remove(dst)

        # Build from daily GrAD files
        if not dst.exists():
            # Download original files
            self.get_dailies()

            # Use fortran to convert GrAD to text files
            self.fortran_dailies()

            # Build and write rainfall index from text files
            logger.info("Building original CPC rainfall index...")
            index = self.ri_index()
            self.to_netcdf(index, dst)

            # # Build and write station counts
            # logger.info("Building original CPC rainfall station counts...")
            # stations = self.stations
            # dst = self.home.joinpath("riv1/station_counts.nc")
            # self.to_netcdf(stations, dst)

    @property
    def daily_dir(self):
        """Return collection directory for daily files"""
        directory = self.ri1_path.joinpath("daily_files")
        directory.mkdir(exist_ok=True)
        return directory

    def fortran_dailies(self):
        """Use a fortran script to convert GrAD files to text files.

        Notes:
            Let's make the fortran script take only one file and parallelize
            with python here.
        """
        logger.info("Converting .lnx files to text files...")
        script_fpath = list(self.paths["fortran"].glob("*f"))[0]
        trgt_fpath = self.daily_dir.joinpath(script_fpath.name)
        if trgt_fpath.exists():
            os.remove(trgt_fpath)
        daily_dir = str(self.daily_dir)
        src = str(script_fpath)
        dst = str(trgt_fpath)
        shutil.copy(src, dst)
        cmd = f"cd {daily_dir} && gfortran {dst} && ./a.out"

        # What kind of errors are possible here?
        os.system(cmd)

        # Rename the real time files.
        for file in self.daily_dir.glob("*.RT.txt"):
            dst = str(file).replace(".RT.txt", ".txt")
            shutil.move(file, dst)

    def get_dailies(self):
        """Collect individual files into single time-series."""
        # Download older datasets
        entries = self.v1_urls
        logger.info("Downloading daily V1.0 CPC rainfall datasets "
                    "(1948-2006).")
        self.download_all(entries)

        # Download newer datasets
        entries = self.rt_urls
        logger.info("Downloading daily RT CPC rainfall datasets (2007-).")
        self.download_all(entries) 

        # Check that all files were downloaded
        self._check_dailies()

    def get_dates(self, array_dict):
        """Return datetime objects."""
        date_strs = list(array_dict.keys())
        dates = []
        for date_str in date_strs:
            date = dt.datetime.strptime(date_str, "%Y%m")
            dates.append(date)
        return dates

    def get_lats(self, corner=False):
        """Return list of longitude coordinates.

        Parameters
        ----------
        corner : boolean
            If True, assume coordinates refer to the top left corner of the
            cell.

        Returns
        -------
        list : List of longitude coordinates associated with the V1.0 rainfall
               index.
        """
        profile = self.get_profile(corner)
        transform = profile["transform"]
        yres = transform[4]
        y0 = transform[5]
        ny = profile["height"]
        return [y0 + yres * n for n in range(ny)]

    def get_lons(self, corner=False):
        """Return list of longitude coordinates.

        Parameters
        ----------
        corner : boolean
            If True, assume coordinates refer to the top left corner of the
            cell.

        Returns
        -------
        list : List of longitude coordinates associated with the V1.0 rainfall
               index. 
        """
        profile = self.get_profile(corner)
        transform = profile["transform"]
        xres = transform[0]
        x0 = transform[2]
        nx = profile["width"]
        return [x0 + xres * n for n in range(nx)]

    def get_profile(self, corner=False):
        """Build georeferencing profile.

        Parameters
        ----------
        corner : boolean
            If True, assume coordinates refer to the top left corner of the
            cell.

        Returns
        -------
        dict : Rasterio style georeferencing profile dictionary.
        """
        doc_url = "DOCU/PRCP_CU_GAUGE_V1.0CONUS_0.25deg.lnx.ctl"
        doc = os.path.join(self.o_url, doc_url)

        # Use their control script
        with requests.get(doc) as r:
            content = r.content.decode().split("\n")

        # Get no data
        nodata = [c for c in content if "undef" in c][0].replace("undef ", "")
        nodata = float(nodata)

        # Get x references
        xdefs = [c for c in content if "xdef" in c][0].split()
        xres = float(xdefs[-1])
        x0 = float(xdefs[-2]) - 360.0
        nx = int(xdefs[1])

        # Get y references
        ydefs = [c for c in content if "ydef" in c][0].split()
        yres = float(ydefs[-1])
        ny = int(ydefs[1])
        y0 = float(ydefs[-2])

        # GrADS uses center of pixel, rasters use top-left corner
        if corner:
            x0 -= (xres / 2)
            y0 -= (yres / 2)

        # Build profile
        profile = {
            "transform": [xres, 0, x0, 0, yres, y0],
            "width": nx,
            "height": ny,
            "count": 1,
            "crs": "epsg:4326",
            "tiled": False,
            "interleave": "band",
            "driver": "GTiff",
            "dtype": "float32",
            "nodata": nodata
        }

        return profile

    def get_urls(self, url):
        """Retrieve CPC V1 rainfall dataset urls."""
        with requests.request("GET", url) as r:
            soup = BeautifulSoup(r.content, features="html.parser")
            hrefs = []
            for a in soup.find_all("a", href=True):
                yhref = os.path.join(url, a["href"])
                if isint(Path(yhref).name):
                    yr = requests.request("GET", yhref)
                    ysoup = BeautifulSoup(yr.content, features="html.parser")
                    for ya in ysoup.find_all("a", href=True):        
                        href = os.path.join(yhref, ya["href"])
                        if ".gz" in href or ".RT" in href:
                            hrefs.append(href)

        hrefs.sort()
        entries = []
        for href in hrefs:
            name = os.path.basename(href)
            dst = os.path.join(self.daily_dir, name)            
            entries.append({"url": href, "dst": dst})

        return entries

    @property
    def gridids(self):
        """Recreate PRF grid ids."""
        grid_fpath = self.paths["rma"].joinpath("prfgrid.tif")
        if not os.path.exists(grid_fpath):
            grid = np.zeros(120 * 300).reshape((120, 300))
            gid = 1
            for y in range(120):
                for x in range(300):
                    grid[y, x] = gid
                    gid += 1

            profile = self.get_profile(corner=True)
            with rio.open(grid_fpath, "w", **profile) as f:
                f.write(grid, 1)
        else:
            with rio.open(grid_fpath) as file:
                grid = file.read(1)
            
        return grid

    def group_intervals(self, arrays):
        """Group arrays to overlapping bi-monthly intervals.

        Parameters
        ----------
        arrays : list
            Dictionary containing date strings ("YYYYMMDD") as keys and 2D
            numpy arrays as values.
        years : list
            List of yearly integers.

        Returns
        -------
        dict : Dictionary with interval date strings ("YYYYII") as keys and
               lists of daily arrays as values.
        """
        years = np.unique([int(key[:4]) for key in arrays.keys()])
        intervals = {}
        for y in range(years.min(), years.max() + 1):
            i1 = 0
            i2 = 1
            for month in range(1, 12):
                i1 += 1
                i2 += 1
                interval1 = str(i1).zfill(2)
                interval2 = str(i2).zfill(2)
                pattern1 = str(y) + interval1
                pattern2 = str(y) + interval2
                array_lst = []
                for date, array in arrays.items():
                    if pattern1 == date[:6] or pattern2 == date[:6]:
                        array_lst.append(array)
                intervals[pattern1] = array_lst
        return intervals

    @lru_cache
    def make_arrays(self):
        """Take the text files from `self.fortran_dailies` and build index.

        Returns
        -------
        list : A list of dictionaries, each containing a 'date', 'rain', and
               'station_count' values corresponding to a string, 2D array, and
               2D array respectively.

        """
        txt_fpaths = list(self.daily_dir.glob("*PRCP*.txt"))
        txt_fpaths.sort()

        # Each array will actually be a dictionary with two arrays and a date
        array_dicts = []
        with ThreadPool(os.cpu_count() - 1) as pool:
            for array_dict in tqdm(pool.imap(self._make_array, txt_fpaths),
                                   total=len(txt_fpaths)):
                array_dicts.append(array_dict)

        return array_dicts

    def ri_index(self):
        """Return the overlapping bimonthly index array from daily files."""
        # get arrays
        array_dicts = self.make_arrays()

        # Organize these
        rain = {d["date"]: d["rain"]for d in array_dicts}

        # Split into intervals
        rain_intervals = self.group_intervals(rain)

        # Take sums of rainfall values
        risums = {k: np.nansum(v, axis=0) for k, v in rain_intervals.items()}
        risums = {k: v for k, v in risums.items() if not isinstance(v, float)}

        # Create rainfall baseline
        baselines = {}
        for i in range(1, 12):
            interval = str(i).zfill(2)
            arrays = [a for k, a in risums.items() if k[4:6] == interval]
            arrays = np.stack(arrays)
            average = np.nanmean(arrays, axis=0)
            average[average == 0] = np.nan
            baselines[interval] = average

        # Index rainfall sums against baseline
        indices = {}
        for date, array in risums.items():
            interval = date[-2:]
            base = baselines[interval]
            out = np.divide(array, base)
            indices[date] = out

        return indices

    def ri_stations(self):
        """Return the overlapping bimonthly average station county array."""
        # get arrays
        array_dicts = self.make_arrays()

        # Organize these
        stations = {d["date"]: d["station_count"]for d in array_dicts}

        # Split into intervals
        station_intervals = self.group_intervals(stations)

        # Take average station count
        station_means = {}
        for k, v in station_intervals.items():
            station_means[k] = np.nanmean(v, axis=0)

        return station_means

    @cached_property
    def rt_urls(self):
        """Return urls for original dataset from 1948 to 2006."""
        logger.info("Collecting daily RT CPC rainfall dataset urls "
                    "(2007-).")
        url = os.path.join(self.o_url, "RT")
        entries = self.get_urls(url)
        return entries

    def to_netcdf(self, array_dict, dst):
        """Write arrays to netcdf file."""
        # Unpack dictionary
        dates = self.get_dates(array_dict)  # Do we want datetimes?
        array = np.stack(list(array_dict.values()))

        # Match CPC origin standard
        array = array[:, ::-1, :]

        # Initialize spatial reference
        sarray = xr.DataArray(
            data=0,
            coords={
                "spatial_ref": 0
            }
        )

        # Build data array
        darray = xr.DataArray(
            data=array,
            dims=["time", "latitude", "longitude"],
            coords={
                "latitude": self.get_lats(corner=False),
                "longitude": self.get_lons(corner=False),
                "time": dates,
                "spatial_ref": sarray
            },
            attrs={
                "units": "ratio"
            }
        )

        # Add coordinate attributes
        darray["latitude"].attrs = {
            "units": "degrees_north",
            "long_name": "Latitude",
            "actual_range": [
                float(darray["latitude"].min()),
                float(darray["latitude"].max())                             
            ]
        }
        darray["longitude"].attrs = {
            "units": "degrees_east",
            "long_name": "Longitude",
            "actual_range": [
                float(darray["longitude"].min()),
                float(darray["longitude"].max())                             
            ]
        }

        # Build data set
        dset = xr.Dataset({"index": darray})
        dset.attrs={
            "title": "CPC Rainfall Index, V1.0",
            "Conventions": "COARDS",
            "description": ("Rain gauge based rainfall grouped into "
                            "eleven overlapping bi-monthly intervals per "
                            "year and indexed against average rainfall "
                            "for each interval across the entire record "
                            "(1948)"),
            "source": self.o_url,
            "comments": ("Coordinates represent center of cell.")
        }

        # Assign georeferencing
        dset = set_georeferencing("riv1", dset)

        # Save
        dset.to_netcdf(dst)

    @cached_property
    def v1_urls(self):
        """Return urls for original dataset from 1948 to 2006."""
        logger.info("Collecting daily V1.0 CPC rainfall dataset urls "
                    "(1948-2006).")
        url = os.path.join(self.o_url, "V1.0")
        entries = self.get_urls(url)
        return entries

    def _check_dailies(self):
        """Check that all daily files downloaded and unzipped."""
        logger.info("Checking daily CPC Rainfall download files...")
        check = True
        gzs = list(self.daily_dir.glob("*.gz"))
        if gzs:
            check = False
            for gz in gzs:
                logger.error("%s failed to unzip.", gz)
        else:
            files = list(self.daily_dir.glob("*"))
            files.sort()
            file_dates = []
            for file in files:
                for part in str(file).split("."):
                    if isint(part):
                        file_dates.append(part)

            last = file_dates[-1]
            needed_dates = pd.date_range("19480101", last)
            needed_dates = [str(d).replace("-", "")[:8] for d in needed_dates]

            if len(needed_dates) != file_dates:
                check = False 
                missings = set(needed_dates) - set(file_dates)
                for missing in missings:
                    logger.error("CPC V1 file for %s is missing.")
        return check

    def _make_array(self, txt_fpath):
        """Take text file and return array and date.

        Parameters
        ----------
        txt_fpath : str
            Path to daily text file derived in `self.fortran_dailies`.

        Returns
        -------
        dict: A dictionary providing a 'date' string, 'rain' array, and
              'station_count'. Each array's shape is (120, 300).
        """
        date = str(txt_fpath).split(".")[-2]

        df = pd.read_csv(txt_fpath, delim_whitespace=True)
        rain_values = df["mm"].values.astype("float32")
        station_values = df["nstations"].values.astype("float32")

        rain = rain_values.reshape(300, 120).T[::-1]
        rain[rain == -999] = np.nan

        station_count = station_values.reshape(300, 120).T[::-1]
        station_count[station_count == -999] = np.nan

        out = {
            "date": date,
            "rain": rain,
            "station_count": station_count
        }

        return out


if __name__ == "__main__":
    self = CPC_Builder()
