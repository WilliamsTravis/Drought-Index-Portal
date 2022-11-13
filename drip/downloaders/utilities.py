"""Index Utilities

Methods to help download and format drought indices from source.

date: Sun Mar 27th, 2022
author: Travis Williams
"""
import os
import pathlib
import socket
import time
import urllib

from ftplib import FTP
from multiprocessing.pool import ThreadPool
from pathlib import Path
from socket import timeout
from statistics import mode
from urllib.error import HTTPError, URLError

import datetime as dt
import dateutil.parser
import netCDF4
import numpy as np
import pandas as pd
import pathos.multiprocessing as mp
import pyproj
import rasterio as rio

from osgeo import gdal, osr
from scipy.stats import rankdata

import drip

from drip.app.options.indices import INDEX_NAMES
from drip.downloaders.index_info import HOSTS, SPATIAL_REFERENCES
from drip.loggers import init_logger, set_handler

logger = init_logger(__name__)
socket.setdefaulttimeout(120)


POSSIBLE_LATS = ["latitude", "lat", "lati", "y"]
POSSIBLE_LONS = ["longitude", "lon", "long", "longi", "x"]
TEMPLATE = drip.Paths.paths["rasters"].joinpath("grid_0_25.tif")


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

    def download_all(self, download_paths):
        """Download all files.

        Parameters
        ----------
        download_paths : list
            List of dictionaries containing 'url' and 'dst' keys for remote
            source and local destination, respectively.
        """
        # We have a set of different methods here
        logger.info("Downloading %d files...", len(download_paths))
        with ThreadPool(os.cpu_count() - 1) as pool:
            for _ in pool.imap(self.download, download_paths):
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
        url = entry["remote"]
        dst = entry["local"]

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

    def _download(self, url, dst):
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

    def __init__(self, index, resolution=0.25, directory=None,
                 percentile=False, projected=False):
        """Initialize NetCDF object.

        Parameters
        ----------
        index : str
            DrIP key for target index. Available keys can be found in
        directory : str | pathlib.PosixPath
            Path to directory in which to write files. Defaults to
            ~/.drip/datasets
            drip.app.options.indices.INDEX_NAMES.
        percentile : boolean
            Build netcdf as ranked percentiles relative to the full record.
        projected : boolean
            Build netcdf and project to EPSG:5070.
        """
        if not directory:
            home = self.paths["indices"]
            self.directory = home.joinpath(index)
            self.directory.mkdir(exist_ok=True, parents=True)
        else:
            self.directory = Path(".").absolute()

        self.host = HOSTS[index]
        self.index = index
        self.percentile = percentile
        self.projected = projected
        self.today = np.datetime64(dt.datetime.today())
        self._set_logger()

    def __repr__(self):
        """Return representation string."""
        address = hex(id(self))
        name = str(self.__class__).replace(">", f" at {address}>")
        attrs = [f"{key}='{attr}'" for key, attr in self.__dict__.items()]
        attr_str = "\n  ".join(attrs)
        msg = f"{name}\n  {attr_str}"
        return msg

    def combine(self, paths, time_tag="NETCDF_DIM_day"):
        """Combine formatted geotiffs files into a single DrIP dataset.

        Parameters
        ----------
        paths : list
            List of paths to NetCDF files.
        datadim : str
            String representing target data dimension in data object.
        timedim : str
            String representing time dimension in data object.
        """
        # Read in a multifile dataset
        paths = list(paths)
        paths.sort()
        data = [rio.open(path) for path in paths]
        arrays = np.concatenate([d.read() for d in data])

        # Get original and sorted time arrays
        time = []
        for d in data:
            for i in range(1, d.count + 1):
                time.append(int(d.tags(i)[time_tag]))
        time = np.array(time)
        sorted_time = time.copy()
        sorted_time.sort()

        # Use the index positions of the original to track the data positions
        idxs = []
        for st in sorted_time:
            idx = int(np.where(time == st)[0])
            idxs.append(idx)

        # Sort data array (way to do this out of memory?)
        sorted_array = np.rollaxis(arrays, 0)[idxs]

        # Assemble pieces into singular netcdf file
        self._assemble(sorted_array, sorted_time, data)
        self._assemble(sorted_array, sorted_time, data, percentile=True)

    @property
    def home(self):
        """Return data home directory."""
        return self.paths["indices"].joinpath(self.index)

    def final_path(self, percentile=False, projected=False):
        """Return final path for indexed NetCDF file."""
        if percentile:
            modifier = "_percentile"
        else:
            modifier = ""

        if projected:
            modifier += "_projected"

        return self.home.joinpath(f"{self.index}{modifier}.nc")

    def to_date(self, date_string):
        """Convert date string to days since 1900-01-01."""
        base = dateutil.parser.parse("19000101")
        date = dateutil.parser.parse(date_string)
        days = (date - base).days

        return days

    def _add_crs_variable(self, nco, profile):
        """Build and return a spatial referencing variable."""
        # Create coordinate reference system variable
        crs = nco.createVariable("crs", "c")

        # The reference code is stored, not consistent enough to infer
        proj = profile["crs"]
        refs = osr.SpatialReference()
        epsg = proj.to_epsg()
        refs.ImportFromEPSG(epsg)

        # Append spatial referencing attributes
        crs.spatial_ref = f"epsg:{epsg}"
        crs.GeoTransform = profile["transform"]
        crs.grid_mapping_name = "latitude_longitude"
        crs.longitude_of_prime_meridian = 0.0
        crs.semi_major_axis = refs.GetSemiMajor()
        crs.inverse_flattening = refs.GetInvFlattening()

    def _add_global_attributes(self, nco, profile):
        """Add attributes to netcdf object"""
        # Global attributes
        nco.title = INDEX_NAMES[self.index]
        nco.subtitle = "Monthly Index values since 1895-01-01"
        xres = profile["transform"][1]
        nco.description = (
            f"Monthly gridded data at {xres} decimal degrees (15 "
            "arc-minute resolution, calibrated to 1895-2010 for the "
            "continental United States."
        )
        nco.original_author = "John Abatzoglou - University of Idaho"
        nco.adjusted_by = "Travis Williams - University of Colorado"
        nco.date = pd.to_datetime(str(self.today)).strftime("%Y-%m-%d")
        nco.projection = "WGS 1984 EPSG: 4326"
        nco.citation = ("Westwide Drought Tracker, "
                        "http://www.wrcc.dri.edu/monitor/WWDT")
        nco.Conventions = "CF-1.6"  # Should I include this if I am not sure?

        return nco

    def _assemble(self, sorted_array, sorted_time, data, percentile=False):
        """Assemble a new netcdf file with sorted data and time arrays."""
        # Get spatial geometry information
        profile = data[0].profile
        crs = profile["crs"]
        width = profile["width"]
        height = profile["height"]

        # Find percentiles if requested
        if percentile:
            sorted_array = self._get_percentiles(sorted_array)

        # Create Dataset
        projected = crs.is_projected
        dst = self.final_path(percentile=percentile, projected=projected)
        if os.path.exists(dst):
            os.remove(dst)

        # Build file
        with netCDF4.Dataset(dst, mode="w", format="NETCDF4") as nco:

            # Dimensions
            nco.createDimension("latitude", height)
            nco.createDimension("longitude", width)
            nco.createDimension("time", None)

            # Variables
            latitudes = nco.createVariable("latitude",  "f4", ("latitude",))
            longitudes = nco.createVariable("longitude",  "f4", ("longitude",))
            times = nco.createVariable("time", "f8", ("time",))
            variable = nco.createVariable(
                "value",
                "f4",
                ("time", "latitude", "longitude"),
                fill_value=-9999  # Inferfrom data
            )
            variable.standard_name = "data"
            variable.units = "unitless"
            variable.long_name = "Index Value"
            variable.setncattr("grid_mapping", "crs")
            self._add_crs_variable(nco, profile)

            # Variable Attrs
            times.units = "days since 1900-01-01"  # Use index_info.py for this
            times.standard_name = "time"
            times.calendar = "gregorian"
            latitudes.units = "degrees_south"
            latitudes.standard_name = "latitude"
            longitudes.units = "degrees_east"
            longitudes.standard_name = "longitude"

            # Add attributes
            nco = self._add_global_attributes(nco, profile)

            # Write - set this to write one or multiple
            transform = profile["transform"]
            xres = transform[0]
            xmin = transform[2]
            yres = transform[4]
            ymax = transform[5]
            latitudes[:] = [ymax + (i * yres) for i in range(height)]
            longitudes[:] = [xmin + (i * xres) for i in range(width)]
            times[:] = sorted_time
            variable[:, :, :] = sorted_array

        return dst

    def _get_geometry(self, data):
        """Get spatial geometric information from netcdf object or file.

        Parameters
        ---------
        data : str | posix.PosixPath | netCDF4._netCDF4.MFDataset | netCDF4._netCDF4.Dataset
        """
        # Open data set if path
        if isinstance(data, (pathlib.PosixPath, str)):
            data = netCDF4.Dataset(data)

        # There are many coordinate names that could be used
        xdim = self._guess_lon(data)
        ydim = self._guess_lat(data)

        # Build transform, assuming no rotation for now
        xmin = float(min(data[xdim]))
        ymin = float(min(data[ydim]))
        ymax = float(max(data[ydim]))
        xres = mode(np.diff(data[xdim]))
        yres = mode(np.diff(data[ydim][::-1]))  # There are two unique values here
        transform = (xres, 0, xmin, 0, yres, ymax)

        # Create vector of x and y coordinates
        nlat = data[ydim].shape[0]
        nlon = data[xdim].shape[0]
        xs = [xmin + (i * xres) for i in range(nlon)]
        ys = [ymin + (i * yres) for i in range(nlat)]

        # Package together
        info = dict(
            crs=pyproj.CRS(SPATIAL_REFERENCES["wwdt"]),
            nlat=nlat,
            nlon=nlon,
            transform=transform,
            xdim=xdim,
            ydim=ydim,
            top=max(ys),
            left=min(xs),
            bottom=min(ys),
            right=max(xs)
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

    def _get_percentiles(self, array):
        """Return an array of time-ranked percentiles in parallel.

        Parameters
        ----------
        array : np.ndarray | np.ma.core.MaskedArray
            A 3D array of values ordered by time, latitude, and longitude in
            that order

        Returns
        -------
        np.ndarray | np.ma.core.MaskedArray
            Percentiles of the input dataset.
        """
        # Apply percentile function
        ncpu = mp.cpu_count() - 1
        chunks = np.array_split(array, ncpu)
        new_arrays = []
        with mp.Pool(ncpu) as pool:
            for new_array in pool.imap(self._percentile_chunk, chunks):
                new_arrays.append(new_array)

        # Piece array back together
        percentiles = np.concatenate(new_arrays, axis=0)

        return percentiles

    def _percentile_chunk(self, chunk):
        """Calculate and return an array of time ranked percentiles of values.

        Parameters
        ----------
        array : np.ndarray | np.ma.core.MaskedArray
            A 3D array of values ordered by time, latitude, and longitude in
            that order

        Returns
        -------
        np.ndarray | np.ma.core.MaskedArray
            Percentiles of the input dataset.
        """
        return np.apply_along_axis(self._percentile_vector, axis=0, arr=chunk)

    def _percentile_vector(self, vector):
        """Calcuate the percentile value for each item in a 1D vector."""
        return (rankdata(vector) / len(vector)) * 100

    def _set_logger(self):
        """Create logging file handler for this process."""
        filename = self.home.joinpath("logs", self.index + ".log")
        set_handler(logger, filename)

    def _warp(self, src, dst, dst_srs="epsg:4326", xres=None, yres=None):
        """Reproject array to epsg:5070.

        Adding ram will almost certainly increase the speed. That’s not at all the same as saying that it is worth it, or that the speed increase will be significant. Disks are the slowest part of the process.

        By default gdalwarp won't take much advantage of RAM. Using the flag "-wm 500" will operate on 500MB chunks at a time which is better than the default. To increase the io block cache size may also help. This can be done on the command like:

        gdalwarp --config GDAL_CACHEMAX 500 -wm 500 ...
        This uses 500MB of RAM for read/write caching, and 500MB of RAM for working buffers during the warp. Beyond that it is doubtful more memory will make a substantial difference.

        Check CPU usage while gdalwarp is running. If it is substantially less than 100% then you know things are IO bound. Otherwise they are CPU bound.

        Caution : increasing the value of the -wm param may lead to loss of performance in certain circumstances, particularly when gdalwarping *many* small rasters into a big mosaic. See http://trac.osgeo.org/gdal/ticket/3120 for more details
        """
        # Alternate strategy, much like first
        # Reproject to tiff with gdal, all bands
        # Read in tiff array,
        # Reset (or better use before setting) geometry using tiff array
        # Continue along

        # Get geographic information
        na = -9999 # Infer from datatype

        # Resample
        if xres and yres:
            template = rio.open(TEMPLATE)
            warped = gdal.Warp(
                srcDSOrSrcDSTab=str(src),
                destNameOrDestDS=str(dst),
                dstNodata=float(na),
                outputBounds=list(template.bounds),
                dstSRS=dst_srs,
                format="GTiff",
                targetAlignedPixels=True,  # test this
                xRes=xres,
                yRes=yres
            )
            del warped

        # Reproject
        else:
            warped = gdal.Warp(
                destNameOrDestDS=str(dst),
                srcDSOrSrcDSTab=str(src),
                dstSRS=dst_srs,
                dstNodata=float(na),
                format="GTiff"
            )
            del warped


class EDDI(NetCDF):
    """Methods for retrieving EDDI files."""

    def __init__(self, index):
        """Initialize EDDI object."""
        super().__init__(index)
        self.period = int(index.replace("eddi", ""))
        self.target_dir = self.home.joinpath("originals")
        self.target_dir.mkdir(exist_ok=True, parents=True)
        self.eddi_ftp_args = [
            "ftp.cdc.noaa.gov",
            "anonymous",
            "anonymous@cdc.noaa.gov"
        ]

    def download_eddi(self):
        """Download an EDDI dataset."""
        logger.info(f"Downloading datasets for {self.index}...")
        paths = self.eddi_paths
        with FTP(*self.eddi_ftp_args, timeout=60*5) as ftp:
            for path in paths:
                self._get(ftp, path)
                time.sleep(3)

    def format_eddi(self, time_tag="NETCDF_DIM_day"):
        """Reformat EDDI asc files to geotiff for use in DataBuilder."""
        # Collect all paths
        paths = list(self.target_dir.glob("*asc"))
        paths.sort()

        # Group by month and get days since 1900
        monthly = {}
        for i in range(1, 13):
            if i not in monthly:
                monthly[i] = {}
            mpaths = [p for p in paths if p.name[-8: -6] == f"{i:02d}"]
            array = np.array([rio.open(mp).read(1) for mp in mpaths])
            date_strings = [mp.name[-12:-4] for mp in mpaths]
            days = [self.to_date(date) for date in date_strings]
            monthly[i]["paths"] = mpaths
            monthly[i]["days"] = days
            monthly[i]["array"] = array

        # Write to geotiff
        profile = rio.open(paths[0]).profile
        profile["crs"] = "epsg:4326"
        profile["driver"] = "GTiff"
        for month, values in monthly.items():
            profile = profile.copy()
            array = values["array"]
            count = array.shape[0]
            profile["count"] = count
            fname = f"{self.index}_{month:02d}_temp.tif"
            dst = self.home.joinpath("originals", fname)
            with rio.open(dst, "w", **profile) as file:
                for i in range(count):
                    band = i + 1
                    meta = {time_tag: values["days"][i]}
                    file.write(array[i], band)
                    file.update_tags(band, **meta)

        # Reproject and resample
        self._adjust_eddi()

    @property
    def eddi_paths(self):
        """Get the last day of the month."""
        pattern = f"{self.period:02d}mn_"
        paths = []
        with FTP(*self.eddi_ftp_args) as ftp:
            ftp.cwd("/Projects/EDDI/CONUS_archive/data/")
            years = [item for item in ftp.nlst() if isint(item)]
            for year in years:
                cwd = f"/Projects/EDDI/CONUS_archive/data/{year}"
                ftp.cwd(cwd)
                all_paths = [f for f in ftp.nlst() if pattern in f]
                for i in range(1, 13):
                    mpattern = f"{i:02d}"
                    mpaths = [p for p in all_paths if p[-8:-6] == mpattern]
                    if mpaths:
                        paths.append(Path(f"{cwd}/{mpaths[-1]}"))

        return paths

    def _adjust_eddi(self, resolution=0.25):
        """Resample all downloaded monthly files to target resolution."""
        # Collect all needed arguments
        resample_list = []
        reproject_list = []
        resolution = resolution
        monthlies = list(self.home.joinpath("originals").glob("*tif"))
        monthlies.sort()
        for src in monthlies:
            rs_name = src.name.replace(".tif", "_resampled.tif")
            rp_name = src.name.replace(".tif", "_reprojected.tif")
            rs_dst = src.parent.joinpath(rs_name)
            rp_dst = src.parent.joinpath(rp_name)
            rs_args = [src, rs_dst, "epsg:4326", resolution, -resolution]
            rp_args = [rs_dst, rp_dst, "epsg:5070", None, None]
            resample_list.append(rs_args)
            reproject_list.append(rp_args)

        # Resample
        with ThreadPool(os.cpu_count() - 1) as pool:
            for _ in pool.starmap(self._warp, resample_list):
                pass

        # Reproject
        with ThreadPool(os.cpu_count() - 1) as pool:
            for _ in pool.starmap(self._warp, reproject_list):
                pass

    def _get(self, ftp, path):
        """Download path from an FTP server. Add error handling/logging."""
        dst = self.target_dir.joinpath(path.name)
        def writeline(line):
            file.write(line + "\n")
        with open(dst, "w") as file:
            try:
                print(f"downloading {path}...")
                logger.info("downloading %s...", path)
                ftp.retrlines(f"RETR {path}", writeline)
            except Exception as e:
                print(e)
                print(f"Download failed, trying again: {path}...")
                logger.error("Download failed (%s), retrying: %s...", e, path)
                try:
                    ftp.retrlines(f"RETR {path}", writeline)
                except Exception as e:
                    print(e)
                    print(f"{path} totally failed")
                    logger.error("%s totally failed: %s", path, e)
                    raise


class PRISM(NetCDF):
    """Methods fordownloading and formatting PRISM datasets."""

    def __init__(self, index):
        """Initialize PRISM Object."""
        super().__init__(index)
        self.prism_ftp_args = [
            "prism.nacse.org",
            "anonymous"
        ]


class Data_Builder(NetCDF):
    """Methods for downloading and formatting data from various sources."""

    def __init__(self, index, resolution=0.25, template=None):
        """Initialize Data_Builder object.

        Parameters
        ----------
        index : str
            Index key. Must be in prf.options.INDEX_NAMES.
        resolution : float
            Resolution of target drought index NetCDF4 file in decimal degrees.
        template : str
            Path to file to use as template for georeferencing.
        """
        super().__init__(index)
        self.host = HOSTS[index]
        self.resolution = resolution
        self.template = template
        self._set_index(index)

    def build(self, overwrite=False):
        """Download and combine multiple NetCDF files from WWDT into one."""
        dsts = [
            self.final_path(percentile=False, projected=False),
            self.final_path(percentile=False, projected=True),
            self.final_path(percentile=True, projected=False),
            self.final_path(percentile=True, projected=True)
        ]
        if all(map(os.path.exists, dsts)) and not overwrite:
            logger.info("%s exists, skipping.", dsts[0])
        else:
            start = time.time()
            logger.info("Building %s...", dsts[0])

            # Different download methods for different data sources
            if self.index.startswith("eddi"):
                eddi = EDDI(self.index)
                eddi.download_eddi()
                eddi.format_eddi()
            else:
                self.download_all(self.download_paths)
                self._adjust_wwdt()

            # Combine into single files for each index
            self._combine()

            end = time.time()
            duration = round((end - start) / 60, 2)
            logger.info("%s completed in %f minutes.", dsts[0], duration)

    @property
    def download_paths(self):
        """Return appropriate remote and local paths for downloading."""
        if self.host == "https://wrcc.dri.edu/wwdt/data/PRISM":
            return self.paths_wwdt


    @property
    def paths_wwdt(self):
        """Return list of remote urls and local destination paths."""
        paths = []
        host = self.host
        index = self.index
        for i in range(1, 13):
            url = os.path.join(host, f"{index}/{index}_{i}_PRISM.nc")
            fname = f"{self.index}_{i:02d}_temp.nc"
            dst = self.home.joinpath(f"originals/{fname}")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            entry = {"remote": url, "local": dst}
            paths.append(entry)
        return paths

    def _adjust_wwdt(self):
        """Resample all downloaded monthly files to target resolution."""
        # Collect all needed arguments
        resample_list = []
        reproject_list = []
        resolution = self.resolution
        for entry in self.download_paths:
            src = entry["local"]
            rs_name = src.name.replace(".nc", "_resampled.tif")
            rp_name = src.name.replace(".nc", "_reprojected.tif")
            rs_dst = src.parent.joinpath(rs_name)
            rp_dst = src.parent.joinpath(rp_name)
            rs_args = [src, rs_dst, "epsg:4326", resolution, -resolution]
            rp_args = [rs_dst, rp_dst, "epsg:5070", None, None]
            resample_list.append(rs_args)
            reproject_list.append(rp_args)

        # Resample
        with ThreadPool(os.cpu_count() - 1) as pool:
            for _ in pool.starmap(self._warp, resample_list):
                pass

        # Reproject
        with ThreadPool(os.cpu_count() - 1) as pool:
            for _ in pool.starmap(self._warp, reproject_list):
                pass

    def _combine(self):
        """Combine all data into required data set."""
        main_paths = self.home.joinpath("originals").glob("*resampled.tif")
        proj_paths = self.home.joinpath("originals").glob("*reprojected.tif")
        self.combine(main_paths)
        self.combine(proj_paths)

    def _set_index(self, index):
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


# if __name__ == "__main__":
#     index = "pdsi"
    # self = Data_Builder(index)
    # self.build()
