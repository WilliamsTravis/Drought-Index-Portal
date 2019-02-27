import os
os.chdir('c:/users/travi/github/Ubuntu-Practice-Machine')
from functions import im
from netCDF4 import Dataset
array_path = 'f:/data/droughtindices/netcdfs/eddi1.nc'
def imageD(array_path, slice):
    data = Dataset(array_path)
    date =  data.variables['time'][slice].data
    image = data.variables['value'][slice][:]
    im(image)

# check this out for making a movie of these! https://github.com/bilylee/videofig
for i in range(467):
    imageD(array_path, i)