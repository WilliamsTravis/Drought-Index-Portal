import xarray as xr
import time

start = time.time()
array_path = "/root/Sync/data/droughtindices/netcdfs/eddi1.nc"
indexlist = xr.open_dataset(array_path)
end = time.time()
print("{} seconds".format(round(start-end, 2)))
