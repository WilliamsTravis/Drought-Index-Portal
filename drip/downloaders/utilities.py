r"""Index Utilities

Methods to help download and format drought indices from source.

date: Sun Mar 27th, 2022
author: Travis Williams
"""
import datetime as dt
import os
import socket
import time
import urllib

from multiprocessing.pool import ThreadPool
from pathlib import Path
from socket import timeout
from statistics import mode
from urllib.error import HTTPError, URLError

import netCDF4
import numpy as np
import pandas as pd

from osgeo import osr

import drip

from drip.app.options.indices import INDEX_NAMES
from drip.downloaders.index_info import HOSTS, SPATIAL_REFERENCES
from drip.loggers import init_logger

logger = init_logger(__name__)
socket.setdefaulttimeout(20)


POSSIBLE_LATS = ["latitude", "lat", "lati", "y"]
POSSIBLE_LONS = ["longitude", "lon", "long", "longi", "x"]


def isint(x):
    """Check if a numeric or string value is an integer."""
    try:
        int(x)
        check = True
    except ValueError:
        check = False
    return check


class Downloader(drip.Paths):
    """Methods for downloading data from urls."""

    def __repr__(self):
        """Print representation string."""
        argstr = ", ".join([f"{k}='{v}'" for k, v in self.__dict__.items()])
        return f"<Downloader object: {argstr}>"

    def download_all(self, entries):
        """Download all files.

        Parameters
        ----------
        entries : list
            List of dictionaries containing 'url' and 'dst' keys for remote
            source and local destination, respectively.
        """
        logger.info("Downloading %d files...", len(entries))
        with ThreadPool(os.cpu_count() - 1) as pool:
            for _ in pool.imap(self.download, entries):
                pass

    def download(self, entry):
        """Download single file.

        Parameters
        ----------
        entry : dict
            A dictionary containing 'url' and 'dst' keys for remote source and
            local destination, respectively.
        """
        start = time.time()
        url = entry["url"]
        dst = entry["dst"]

        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            logger.info("%s exists, skipping...", dst)
            return

        self._download(url, dst)

        end = time.time()
        duration = round((end - start) / 60, 2)
        logger.info("%s downloaded to %s in %f minutes.", os.path.basename(url),
                    dst, duration)

        if not os.path.exists(dst):
            logger.error("%s did not download correctly.", dst)

    def _download(url, dst):
        """Download file.

        Parameters
        ----------
        url : str
            URL to online file.
        dst : str | posix.PosixPath
            Destination path to local file.
        """
        try:
            logger.info(
                "Downloading %s to %s...",
                os.path.basename(url),
                dst
            )
            urllib.request.urlretrieve(url, dst)
        except (HTTPError, URLError) as error:
            logger.error("%s not retrieved because %s\nURL: %s", dst,
                         error, url)
        except timeout:
            logger.error("Socket timed out, attempting again: %s", url)
            try:
                os.remove(dst)
                urllib.request.urlretrieve(url, dst)
            except (HTTPError, URLError) as error:
                logger.error("%s not retrieved because %s\nURL: %s", dst,
                            error, url)
            except timeout:
                logger.error("Socket timed out twice, try again later: %s",
                             url)
                raise


class Adjustments(Downloader):
    """Methods to adjust original drought index."""

    def normalize(self, array):
        """Standardize index values to a 0.0-1.0 range."""
        array = (array - array.min()) / (array.max() - array.min())
        return array


class NetCDF(Adjustments):
    """Methods for building, combining, and warping netcdf files."""

    def __init__(self, index, directory=None):
        """Initialize NetCDF object.
        
        Parameters
        ----------
        index : str
            DrIP key for target index. Available keys can be found in
            drip.app.options.indices.INDEX_NAMES.
        directory : str | pathlib.PosixPath
            Path to directory in which to write files. Defaults to 
            ~/.drip/datasets
        """
        if not directory:
            self.directory = self.paths["indices"].joinpath(index)
        else:
            self.directory = Path(".").absolute()
        self.host = HOSTS[index]
        self.index = index
        self.today = np.datetime64(dt.datetime.today())

    def __repr__(self):
        """Return representation string."""
        address = hex(id(self))
        name = str(self.__class__).replace(">", f" at {address}>")
        attrs = [f"{key}='{attr}'" for key, attr in self.__dict__.items()]
        attr_str = "\n  ".join(attrs)
        msg = f"{name}\n  {attr_str}"
        return msg

    def build(self, paths, dst, datadim="data", aggdim="day"):
        """Format downloaded netcd4 files into a single DrIP dataset.

        Parameters
        ----------
        paths : list
            List of paths to NetCDF files.
        dst : str
            Path to target output file.
        datadim : str
            String representing target data dimension in data object.
        timedim : str
            String representing time dimension in data object.
        """
        # Read in a multifile dataset
        data = netCDF4.MFDataset(paths, aggdim=aggdim)

        # Get original and sorted time arrays
        time_array = data[timedim][:]
        sorted_time = time_array.copy()
        sorted_time.sort()

        # Use the index positions of the original to track the data positions
        idxs = []
        for st in sorted_time:
          idx = np.where(time_array == st)[0][0]
          idxs.append(idx)

        # Sort data array (way to do this out of memory?)
        time_axis =  data[datadim].dimensions.index(timedim)
        sorted_array = np.rollaxis(data[datadim], time_axis)[idxs]

        # Assemble pieces into singular netcdf file
        self._assemble(dst, sorted_array, sorted_time, data)

    def _add_crs_variable(self, nco, geo_info):
        """Build and return a spatial referencing variable."""
        # Create coordinate reference system variable
        crs = nco.createVariable("crs", "c")

        # The reference code is stored, not consistent enough to infer
        proj = SPATIAL_REFERENCES["wwdt"]
        refs = osr.SpatialReference()
        if proj.lower().startswith("epsg"):
            code = int(proj.split(":")[-1])
            refs.ImportFromEPSG(code)
        elif isinstance(proj, str) and "+" in proj:
            refs.ImportFromProj4(proj)

        # Append spatial referencing attributes
        crs.spatial_ref = proj
        crs.GeoTransform = geo_info["transform"]
        crs.grid_mapping_name = "latitude_longitude"
        crs.longitude_of_prime_meridian = 0.0
        crs.semi_major_axis = refs.GetSemiMajor()
        crs.inverse_flattening = refs.GetInvFlattening()

    def _add_global_attributes(self, nco, geo_info):
        """Add attributes to netcdf object"""
        # Global attributes
        nco.title = INDEX_NAMES[self.index]
        nco.subtitle = "Monthly Index values since 1895-01-01"
        xres = geo_info["transform"][1]
        nco.description = (
            f"Monthly gridded data at {xres} decimal degrees (15 "
            "arc-minute resolution, calibrated to 1895-2010 for the "
            "continental United States."
        ),
        nco.original_author = "John Abatzoglou - University of Idaho"
        nco.adjusted_by = "Travis Williams - University of Colorado"
        nco.date = pd.to_datetime(str(self.today)).strftime("%Y-%m-%d")
        nco.projection = "WGS 1984 EPSG: 4326"
        nco.citation = ("Westwide Drought Tracker, "
                        "http://www.wrcc.dri.edu/monitor/WWDT")
        nco.Conventions = "CF-1.6"  # Should I include this if I am not sure?

        return nco

    def _assemble(self, dst, sorted_array, sorted_time, data):
        """Assemble a new netcdf file with sorted data and time arrays."""
        # Create Dataset
        nco = netCDF4.Dataset(dst, mode="w", format="NETCDF4")

        # Get spatial geometry information
        geo_info = self._get_geometry(data)

        # Dimensions
        nco.createDimension("latitude", geo_info["nlat"])
        nco.createDimension("longitude", geo_info["nlon"])
        nco.createDimension("time", None)

        # Variables
        latitudes = nco.createVariable("latitude",  "f4", ("latitude",))
        longitudes = nco.createVariable("longitude",  "f4", ("longitude",))
        times = nco.createVariable("time", "f8", ("time",))
        variable = nco.createVariable(
            "value",
            "f4",
            ("time", "latitude", "longitude"),
            fill_value=-9999
        )
        variable.standard_name = "index"
        variable.units = "unitless"
        variable.long_name = "Index Value"
        variable.setncattr("grid_mapping", "crs")
        self._add_crs_variable(nco, geo_info)

        # Variable Attrs
        times.units = "days since 1900-01-01"  # Use index_info.py for this
        times.standard_name = "time"
        times.calendar = "gregorian"
        latitudes.units = "degrees_south"
        latitudes.standard_name = "latitude"
        longitudes.units = "degrees_east"
        longitudes.standard_name = "longitude"

        # Add attributes
        nco = self._add_global_attributes(nco, geo_info)

        # Pull multifile data out
        array = data["data"][:]
        time = data["day"][:]

        # This allows the option to store the data as percentiles
        # if percentiles:
        #     arrays[arrays == -9999] = np.nan  # Infer nan from file
        #     arrays = percentileArrays(arrays)

        # Write - set this to write one or multiple
        latitudes[:] = geo_info["ys"]
        longitudes[:] = geo_info["xs"]
        times[:] = time.astype(int)
        variable[:, :, :] = array
    
        # Done
        nco.close()

    def _get_geometry(self, data):
        """Get spatial geometric information"""
        # There are many coordinate names that could be used
        xdim = self._guess_lon(data)
        ydim = self._guess_lat(data)

        # Build transform, assuming no rotation for now
        xmin = float(min(data[xdim]))
        ymin = float(min(data[ydim]))
        ymax = float(max(data[ydim]))
        xres = mode(np.diff(data[xdim]))
        yres = mode(np.diff(data[ydim]))  # There are two unique values here
        transform = (xmin, xres, 0, ymax, 0, yres)

        # Create vector of x and y coordinates
        nlat = data[ydim].shape[0]
        nlon = data[xdim].shape[0]
        xs = [xmin + (i * xres) for i in range(nlon)]
        ys = [ymin + (i * yres) for i in range(nlat)]

        # Package together
        info = dict(
            nlat=nlat,
            nlon=nlon,
            transform=transform,
            xdim=xdim,
            xs=xs,
            ydim=ydim,
            ys=ys
        )

        return info

    def _guess_lat(self, data):
        """Guess latitude dimension in netCDF4 dataset."""
        dims = [d for d in data.dimensions.keys() if d in POSSIBLE_LATS]
        if len(dims) == 0:
            # Log it here
            raise KeyError("Could not find latitude dimension. Add latitude "
                           "key to POSSIBLE_LATS.")
        return dims[0]     
        
    def _guess_lon(self, data):
        """Guess longitude dimension in netCDF4 dataset."""
        dims = [d for d in data.dimensions.keys() if d in POSSIBLE_LONS]
        if len(dims) == 0:
            # Log it here
            raise KeyError("Could not find longitude dimension. Add longitude "
                           "key to POSSIBLE_LONS.")
        return dims[0]     


if __name__ == "__main__":
    timedim = aggdim = "day"
    datadim = "data"
    self = NetCDF("pdsi")
    paths = list(self.home.glob("drip/data/indices/pdsi/pdsi*nc"))
    dst = paths[0].parent.joinpath("temp.nc")
    self.build(paths, dst)
