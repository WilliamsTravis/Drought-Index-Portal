"""Data methods for main page."""
import base64
import os
import tempfile

from pathlib import Path
from zipfile import ZipFile

import fiona
import geopandas as gpd
import rasterio as rio

from osgeo import osr
from rasterio.features import rasterize

from drip import Paths
from drip.app.old.functions import Admin_Elements
from drip.app.options.options import Options
from drip.loggers import init_logger, set_handler

logger = init_logger(__name__)
set_handler(logger, Paths.log_directory.joinpath("model.log"))


RESOLUTION = Options.transform[0]
ADMIN = Admin_Elements(RESOLUTION)
ZIP_EXTENSIONS = ["zip", "7z"]


class Parse_Shape(Paths):
    """Methods for parsing and reformatting a user-provided shapefile."""

    def __init__(self, fpaths, contents):
        """Initialize Parse_Shape object.

        Parameters
        ----------
        fpaths : list
            List of strings of filenames.
        contents : list
            List of strings containing shapefile data.
        """
        self.fpaths = [Path(fpath) for fpath in fpaths]
        self.contents = contents

    def __repr__(self):
        """Return representation string for Parse_Shape object."""
        msg = f"<{self.__class__.__name__} object: basename='{self.basename}'>"
        return msg

    @property
    def basename(self):
        """Return basename of file or file group."""
        return os.path.splitext(self.fpaths[0])[0]

    @property
    def elements(self):
        """Return encoded shapefile elements."""
        content_elements = [c.split(",") for c in self.contents]
        return [e[1] for e in content_elements]

    @property
    def element_types(self):
        """Return element type."""
        content_elements = [c.split(",") for c in self.contents]
        return [e[0] for e in content_elements]

    def parse(self):
        """Parse a multi-file shapefile format."""
        for i in range(len(self.elements)):
            decoded = base64.b64decode(self.elements[i])
            fname = self.fpaths[i]
            name, ext = os.path.splitext(fname)
            temp_path = self.temp_dir.joinpath(f"temp{ext}")
            with open(temp_path, "wb") as f:
                f.write(decoded)
        return temp_path  # Placeholder

    def parse_zip(self):
        """Parse a zipped shapefile."""
        fpath = self.fpaths[0]
        content_type, shp_element = self.contents[0].split(",")
        decoded = base64.b64decode(shp_element)
        with tempfile.TemporaryFile() as tmp:
            tmp.write(decoded)
            tmp.seek(0)
            archive = ZipFile(tmp, "r")
            for file in archive.filelist:
                fname = file.filename
                content = archive.read(fname)
                name, ext = os.path.splitext(fname)
                fname = "temp" + ext
                fpath = self.temp_dir.joinpath(fname)
                with open(fpath, "wb") as f:
                    f.write(content)
        return fpath

    def rasterize(self, gdf):
        """Rasterize geodataframe."""
        # Make target path
        dst = str(self.temp_dir.joinpath(f"{self.basename}.tif"))

        # Create array
        shapes = [(geom, 1) for geom in gdf["geometry"].values]
        mask = rasterize(
            shapes=shapes,
            out_shape=(120, 300),
            transform=Options.transform[:6],
            all_touched=True
        )

        # Write to raster
        with rio.open(dst, "w", **self.profile) as file:
            file.write(mask, 1)

        return dst

    def reproject(self, gdf, fpath):
        """Reproject geodataframe to WGS 84."""
        crs = gdf.crs
        try:
            epsg = crs.to_epsg()
        except:
            fshp = fiona.open(fpath)
            crs_wkt = fshp.crs_wkt
            crs_ref = osr.SpatialReference()
            crs_ref.ImportFromWkt(crs_wkt)
            crs_ref.AutoIdentifyEPSG()
            epsg = crs_ref.GetAttrValue("AUTHORITY", 1)
            epsg = int(epsg)
            fshp.close()

        if epsg != 4326:
            gdf = gdf.to_crs("epsg:4326")

        return gdf

    @property
    def temp_dir(self):
        """Return temporary file directory."""
        return Paths.paths["shapefiles"].joinpath("temp")

    @property
    def profile(self):
        """Return a rasterio profile from a template raster."""
        res_str = str(RESOLUTION).replace(".", "_")
        template_fpath = self.paths["rasters"].joinpath(f"grid_{res_str}.tif")
        with rio.open(template_fpath) as r:
            profile = r.profile
        return profile

    def main(self):
        """Parse and rasterize shapefile contents."""
        # Skip if empty
        if self.fpaths:
            # Parse contents, write to file
            if any(e in self.fpaths[0].name for e in ZIP_EXTENSIONS):
                fpath = self.parse_zip()
            else:
                fpath = self.parse()

            # Check CRS, reproject if needed
            gdf = gpd.read_file(fpath)
            gdf = self.reproject(gdf, fpath)

            # Now let"s just rasterize it for a mask
            fpath = self.temp_dir.joinpath("temp.gpkg")
            gdf.to_file(fpath, "GPKG")

            # Rasterize
            dst = self.rasterize(gdf)
 
            return dst
