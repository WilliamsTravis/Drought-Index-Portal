# -*- coding: utf-8 -*-
"""Refactoring Get_PRISM

Created on Sun Jul 11 10:04:19 2021

@author: travis
"""
import datetime as dt
import ftplib
import os
import pathlib
import sys
import zipfile

from glob import glob

import numpy as np
import pandas as pd
import xarray as xr

from netCDF4 import Dataset
from osgeo import gdal
from tqdm import tqdm


PWD = str(pathlib.Path('__file__').parent.absolute())
DATA_PATH = os.path.abspath(os.path.join(PWD, ".."))
sys.path.insert(0, DATA_PATH)

from functions import isInt, meanNC, toNetCDF, toNetCDFAlbers  # <------------- Is importable from the drip package in refactor now
from functions import toNetCDFPercentile

# gdal.PushErrorHandler('CPLQuietErrorHandler')
os.environ['GDAL_PAM_ENABLED'] = 'NO'


try:
    RES = float(sys.argv[1])
except:
    RES = 0.25

PROJ = ("+proj=aea +lat_1=20 +lat_2=60 +lat_0=40 +lon_0=-96 +x_0=0 +y_0=0 " +
        "+ellps=GRS80 +datum=NAD83 +units=m no_defs")
TODAYS_DATE = dt.datetime.today()
TODAY = np.datetime64(TODAYS_DATE)
VARIABLES = ["tmin", "tmax", "tdmean", "tmean", "ppt", "vpdmax", "vpdmin"]
HOST = "prism.nacse.org"
USER = "anonymous"


class PRISM:
    """Methods for downloading, reformatting, and updating PRISM datasets."""

    def __init__(self, host=HOST, user=USER, data_path=DATA_PATH):
        """Initialize PRISM object."""
        self.data_path = data_path
        self.host = host
        self.user = user

    def __repr__(self):
        """Print representation string."""
        argstr = ", ".join([f"{k}='{v}'" for k, v in self.__dict__.items()])
        return f"<PRISM object: {argstr}>"

    def build(self, variable, ftp):
        """Build initial dataset."""
        # We need to build these three files
        paths = self.get_paths(variable)

        # Retrieve rasters
        self.get_rasters(variable, ftp)

        # Reproject for area calculations
        for file in glob(os.path.join(self.tif_folder, "*tif")):
            self.reproject(file)

        # Convert originals to NetCDF file
        files = glob(os.path.join(self.tif_folder, variable + "*tif"))
        toNetCDF(tfiles=files, ncfiles=None, savepath=paths["original"],
                 index=variable, proj=4326, year1=1895, month1=1,
                 year2=TODAYS_DATE.year - 2, month2=12, wmode="w",
                 percentiles=False)

        # Convert projected files to NetCDF file
        files = glob(os.path.join(self.tif_folder, "proj_*tif"))
        toNetCDFAlbers(tfiles=files, ncfiles=None, savepath=paths["albers"],
                       index=variable, proj=PROJ, year1=1895, month1=1,
                       year2=TODAYS_DATE.year - 2, month2=12, wmode="w",
                       percentiles=False)

        # Create a percentile dataset
        toNetCDFPercentile(paths["original"], paths["percentile"])

        # Clear temp folder
        self._clear_tif()

    def get_file(self, filename, ftp):
        """Download file from FTP server.

        Parameters
        ----------
        filename : str
            Name of file on FTP server.
        ftp : ftplib.FTP
            An open FTP connection.

        Returns
        -------
        str
            Local file path.
        """
        dst = os.path.join(self.temp_folder, "prism.zip")
        with open(dst, "wb") as file:
            try:
                ftp.retrbinary("RETR " + filename, file.write)
            except Exception as e:
                print(e)
                pass

        return dst

    def get_rasters(self, variable, ftp):
        """Retrieve original grids and convert to raster."""
        # List the remote monthly datasets
        ftp.cwd(f"/monthly/{variable}")
        ftp_years = ftp.nlst()
        ftp_years = [f for f in ftp_years if isInt(f)]
        ftp_years.sort()

        # Get each yearly file
        for year in tqdm(ftp_years, position=0):
            ftp.cwd(f"/monthly/{variable}/{year}")
            files = ftp.nlst()

            # There are three different formats to look out for
            if any(["_all_" in f for f in files]):
                file = [f for f in files if "_all_" in f][0]
                self._retrieve(variable, file, year, ftp)
                self._clear_temp()
            elif any([f"_{year}_" in f for f in files]):
                file = [f for f in files if f"_{year}_" in f][0]
                self._retrieve(variable, file, year, ftp)
                self._clear_temp()
            else:
                files = [f for f in files if '_' + year + '_' not in f]
                for file in files:
                    self._retrieve(variable, file, year, ftp)
                    self._clear_temp()

    def get_paths(self, variable):
        """Return dictionary of target local file paths."""
        original = os.path.join(self.target_folder, variable + ".nc")
        albers= os.path.join(self.projected_folder, variable + ".nc")
        percentile= os.path.join(self.percentile_folder, variable + ".nc")
        paths = {"original": original, "albers": albers,
                 "percentile": percentile}
        return paths

    def needed_dates(self, variable, ftp):
        """Return a list of all dates we don't have for a variable."""
        # We need to build these three files
        paths = self.get_paths(variable)

        # Dates we already have
        ftp.cwd('/monthly/' + variable)
        with xr.open_dataset(paths["original"]) as data:
            our_dates = pd.DatetimeIndex(data.time.data)

        # Available years    
        ftp_years = ftp.nlst()
        ftp_years = [f for f in ftp_years if isInt(f)]
        ftp_years.sort()

        # Find the most recently available ftp files
        ftp.cwd('/monthly/' + variable + '/' + max(ftp_years))
        ftp_files = ftp.nlst()

        # Find the most recent date
        ftp_dates = [f[-14:-8] for f in ftp_files]
        most_recent = dt.datetime.strptime(max(ftp_dates), "%Y%m")
        most_recent = pd.Timestamp(most_recent)

        # Build a list of needed dates
        first = our_dates[-1]
        needed_dates = pd.date_range(first, most_recent, freq="MS")
        needed_years = np.unique([d.year for d in needed_dates])

        # Build a dictionary of needed years and months
        needed_years.sort()
        needed = {}
        for year in needed_years:
            months = [date.month for date in needed_dates if date.year == year]
            months = ["{:02d}".format(month) for month in months]
            year = str(year)
            needed[year] = months

        return needed

    @property
    def percentile_folder(self):
        """Return target file directory path."""
        folder = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/"
                              "percentile_folder")
        os.makedirs(folder, exist_ok=True)
        return folder

    @property
    def projected_folder(self):
        """Return target file directory path."""
        folder = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/albers")
        os.makedirs(folder, exist_ok=True)
        return folder

    @property
    def target_folder(self):
        """Return target file directory path."""
        folder = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/")
        os.makedirs(folder, exist_ok=True)
        return folder

    @property
    def temp_folder(self):
        """Return temporary file directory path."""
        folder = os.path.join(DATA_PATH, "data/droughtindices/netcdfs/prism")
        os.makedirs(folder, exist_ok=True)
        return folder

    @property
    def tif_folder(self):
        """Return geotif file directory path."""
        folder = os.path.join(self.temp_folder, "tifs")
        os.makedirs(folder, exist_ok=True)
        return folder

    def reproject(self, file):
        """Reproject file to our North American Equal Areas projection."""
        fname = os.path.basename(file)
        dst = os.path.join(self.tif_folder, "proj_" + fname)
        out = gdal.Warp(dst, file, dstSRS=PROJ)
        del out

    def update(self, variable, ftp):
        """Update dataset."""
        # We need to build these three files
        paths = self.get_paths(variable)

        # Find the missing files
        needed_dates = self.needed_dates(variable, ftp)

        # Download needed files
        for year, months in needed_dates.items():
            # Get all files availabel for this year
            ftp.cwd("/monthly/" + variable + "/" + year)
            rfiles = ftp.nlst()
            rfiles = [f for f in rfiles if "_" + year + "_" not in f]
            rfiles.sort()
            for rfile in rfiles:
                for month in months:
                    if rfile[-10: -8] == month:
                        # Update the WGS file
                        self._clear_temp("*bil")
                        self._retrieve(variable, rfile, year, ftp)
                        lfile = os.path.join(self.tif_folder,
                                             f"{variable}_{year}{month}.tif")
                        with Dataset(paths["original"], "r+") as old:
                            times = old.variables["time"]
                            values = old.variables["value"]
                            n = times.shape[0]
                            base_data = gdal.Open(lfile)
                            array = base_data.ReadAsArray()
                            del base_data
        
                            # Catch the day      
                            date = dt.datetime(int(year), int(month), day=15)
                            days = date - dt.datetime(1900, 1, 1)
                            days = np.float64(days.days)
        
                            # Write changes to file and close
                            times[n] = days
                            values[n] = array
        
                        # Update the Albers file
                        self.reproject(lfile)
                        pfile = os.path.join(
                            self.tif_folder,
                            f"proj_{variable}_{year}{month}.tif"
                        )
                        with Dataset(paths["albers"], "r+") as old:
                            times = old.variables["time"]
                            values = old.variables["value"]
                            n = times.shape[0]
                            base_data = gdal.Open(pfile)
                            array = base_data.ReadAsArray()
                            del base_data
        
                            # Catch the day                    
                            date = dt.datetime(int(year), int(month), day=15)
                            days = date - dt.datetime(1900, 1, 1)
                            days = np.float64(days.days)
        
                            # Write changes to file and close
                            times[n] = days
                            values[n] = array

        # Reset the percentiles file
        toNetCDFPercentile(paths["original"], paths["percentile"])

    def vpd_means(self):
        """Build a mean datasetS for the vapor pressure deficit files."""
        for source in ["target", "percentile", "projected"]:
            folder = self.__getattribute__(f"{source}_folder")
            minsrc = os.path.join(folder, "vpdmin.nc")
            maxsrc = os.path.join(folder, "vpdmax.nc")
            dst = os.path.join(folder, "vpdmean.nc")
            meanNC(minsrc, maxsrc, dst)

    def _clear_temp(self, pattern="*"):
        """Clear the temp file folder."""
        temps = glob(os.path.join(self.temp_folder, pattern))
        for file in temps:
            if file != self.tif_folder:
                os.remove(file)

    def _clear_tif(self):
        """Clear the temp file folder."""
        temps = glob(os.path.join(self.tif_folder, "*"))
        for file in temps:
            os.remove(file)

    def _connect(self, timeout=120):
        """Connect to FTP server."""
        ftp = ftplib.FTP(host=self.host, user=self.user, timeout=timeout)
        ftp.set_pasv(False)
        try:
            assert "server ready" in ftp.welcome
        except AssertionError:
            print(f"{self.host} appears to be down.")
            print(ftp.welcome)
            raise
        return ftp

    def _retrieve(self, variable, file, year, ftp):
        """Retrieve and reformat the older format PRISM file."""
        # Download zip file from server
        temp_path = self.get_file(file, ftp)
        self._unzip(temp_path)

        # Get the right files
        bils = glob(os.path.join(self.temp_folder, "*bil"))
        bils = [b for b in bils if "_" + year + "_" not in b]  # monthly
        bils.sort()

        # Warp each to the target dataset
        for bil in bils:
            month = bil[-10: -8]
            fpath = f"{variable}_{year + month}.tif"
            dst = os.path.join(self.tif_folder, fpath)
            out = gdal.Warp(dst, bil, dstSRS="EPSG:4326", xRes=RES, yRes=RES,
                            outputBounds=[-130, 20, -55, 50])
            del out

    def _unzip(self, file):
        """Unzip contents of zipped file."""
        with zipfile.ZipFile(file, "r") as zref:
            zref.extractall(self.temp_folder)

    def main(self):
        """Build or update dataset."""
        for variable in VARIABLES:
            self._clear_temp()
            target_path = os.path.join(self.target_folder, variable + ".nc")
            with self._connect(timeout=None) as ftp:
                if os.path.exists(target_path):
                    print(f"Checking/Updating {variable}...")
                    self.update(variable, ftp)
                else:
                    print(f"Building new dataset for {variable}...")
                    self.build(variable, ftp)

        print("Building/rebuilding mean vpd...")
        self.vpd_means()


if __name__ == "__main__":
    self = PRISM()
    
    prism = PRISM()
    prism.main()
