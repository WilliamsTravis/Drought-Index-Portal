r"""Index Utilities

Methods to help download and format drought indices from source.

date: Sun Mar 27th, 2022
author: Travis Williams
"""
import os
import shutil
import socket
import time
import urllib

from pathlib import Path
from multiprocessing.pool import ThreadPool
from socket import timeout
from urllib.error import HTTPError, URLError

import gzip
import numpy as np
import pyproj
import xarray as xr

import drip

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


def set_georeferencing(index, data, xy=False):
    """Set needed georeferencing information on an xarray object.

    Parameters
    ----------
    index : str
        Name of index.
    data : xr.core.dataset.Dataset
        xarray dataset object.
    xy : boolean
        Use 'x' and 'y' instead of 'longitude' and 'latitude'.
    """
    # Make sure the crs is referenced
    crs = pyproj.CRS("epsg:4326").to_wkt()
    data = data.rio.write_crs(crs)

    # Infer the latitude and longitude fields
    xnames = [dim for dim in data.dims if dim in POSSIBLE_LONS]
    ynames = [dim for dim in data.dims if dim in POSSIBLE_LATS]

    # Make sure each dimension is found
    if len(xnames) == 0:
        logger.error("X coordinate dimension not found for %s", index)
        raise KeyError(f"X dimension not found for {index}")
    if len(ynames) == 0:
        logger.error("Y coordinate dimension not found for %s", index)
        raise KeyError(f"Y dimension not found for {index}")

    # Make sure only one dimension is found
    if len(xnames) > 1:
        logger.error("Multiple X coordinate dimensions found for %s",
                     index)
        raise KeyError(f"Multiple X dimensions found for {index}")
    if len(ynames) > 1:
        logger.error("Multiple Y coordinate dimension found for %s",
                     index)
        raise KeyError(f"Multiple Y dimensions found for {index}")

    # Get x and y dimension names
    xname = xnames[0]
    yname = ynames[0]

    # Use 'x' and 'y' as names
    if xy:
        data = data.swap_dims({xname: "x", yname: "y"})
        data = data.rename_vars({xname: "x", yname: "y"})
        xname = "x"
        yname = "y"
    else:
        data = data.swap_dims({xname: "longitude", yname: "latitude"})
        data = data.rename_vars({xname: "longitude", yname: "latitude"})
        xname = "longitude"
        yname = "latitude"

    # Set x and y dimension names
    data = data.rio.set_spatial_dims(x_dim=xname, y_dim=yname)

    # Some how 'axis' is getting added to the attributes.rio.transform()
    if "axis" in data[xname].attrs:
        del data[xname].attrs["axis"]
        del data[yname].attrs["axis"]

    return data


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

        end = time.time()
        duration = round((end - start) / 60, 2)
        logger.info(
            "%s downloaded to %s in %f minutes.",
            os.path.basename(url),
            dst,
            duration
        )

        if not os.path.exists(dst):
            logger.error("%s did not download correctly.", dst)
