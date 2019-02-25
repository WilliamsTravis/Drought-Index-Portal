import netCDF4
import numpy as np
from rasterio.crs import CRS
from affine import Affine


file1 = r'F:\data\droughtindices\netcdfs\final_test\test_1.nc'
file2 = r'F:\data\droughtindices\netcdfs\final_test\test_2.nc'

# rasterio like raster meta information 
meta = {'width': 3000,
        'height': 2000,
        'crs': CRS({u'lon_0': 0, u'ellps': u'WGS84', u'y_0': 0, u'no_defs': True,
                    u'proj': u'laea', u'x_0': 0, u'units': u'm', u'lat_0': 0}),
        'transform': Affine(1000, 0, 0, 0, -1000, 0),
        'count': 100,
}

# Array of random values
array = np.random.rand(meta['height'], meta['width'])

# Util function to generate x and y dimension arrays (only used in second case)
def meta2dim(meta, side):
    """Generate a coordinates array from raster file meta dictionary

    Args:
        meta (dict): dictionary of raster metadata (as returned by rasterio).
            Important keys are height, width and transform.
        side (str): 'width'(lat or y array) or 'height' (lon or x array)

    Return:
        A list corresponding to center row (or columns) coordinates.
    """
    aff = meta['transform']
    if side == 'width':
        res = aff[0]
        start = aff[2]
    elif side == 'height':
        res = aff[4]
        start = aff[5]
    steps = meta[side]
    array = [start + x * res + (res / 2) for x in range(steps)]
    return array

# First, using only geotransform
with netCDF4.Dataset(file1, mode='w') as src:
    # Create spatial dimensions
    x_dim = src.createDimension('x', meta['width'])
    y_dim = src.createDimension('y', meta['height'])

    # Create temporal dimension
    t_dim = src.createDimension('time', None)

    # chlor variable
    chlor = src.createVariable('chlor_a', np.float32, ('time','y','x'),
                               zlib=True)

    chlor.grid_mapping = 'laea' # This corresponds to the name of the variable where crs info is stored
    chlor[0,:,:] = array

    # laea variable to store projection information
    laea = src.createVariable('laea', 'c')
    laea.spatial_ref = meta['crs'].wkt
    laea.GeoTransform = " ".join(str(x) for x in meta['transform'].to_gdal())

# Second, adding x and y coordinates array to netcdf file
with netCDF4.Dataset(file2, mode='w') as src:
    # Create spatial dimensions
    # x
    x_dim = src.createDimension('x', meta['width'])
    x_var = src.createVariable('x', np.float32, ('x',))
    lon = meta2dim(meta, 'width')
    x_var[:] = lon

    # y
    y_dim = src.createDimension('y', meta['height'])
    y_var = src.createVariable('y', np.float32, ('y',))
    lat = meta2dim(meta, 'height')
    y_var[:] = lat

    # Create temporal dimension
    t_dim = src.createDimension('time', None)

    # chlor variable
    chlor = src.createVariable('chlor_a', np.float32, ('time','y','x'),
                               zlib=True)
    chlor.grid_mapping = 'laea'
    chlor[0,:,:] = array

    # laea variable to store projection information
    laea = src.createVariable('laea', 'c')
    laea.spatial_ref = meta['crs'].wkt