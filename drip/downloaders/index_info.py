"""Droungt index information

Not all netcdf files will have intuitive coordinate reference system info
in the their attributes (i.e. WWDT sometimes puts it in the "esri_pe_string"
attribute.

This module provides non-intuitive referencing information for each
DrIP dataset source.

This also stores the server address for each index.
"""
SPATIAL_REFERENCES = {
    "wwdt": "epsg:4326",
    "eddi": "epsg:4326",
    "prism": "epsg:4326"
}

ADDRESSES = {
    "ftp://ftp2.psl.noaa.gov/Projects/EDDI/CONUS_archive": [
        f"eddi{i}" for i in range(1, 13)
    ],
    "prism.nacse.org": [
        "tmin",
        "tmax",
        "tdmean",
        "ppt",
        "vpdmax",
        "vpdmin"
    ],
    "https://wrcc.dri.edu/wwdt/data/PRISM": [
        'pdsi',
        'scpdsi',
        'pzi',
        'spi1',
        'spi2',
        'spi3',
        'spi4',
        'spi5',
        'spi6',
        'spi7',
        'spi8',
        'spi9',
        'spi10',
        'spi11',
        'spi12',
        'spei1',
        'spei2',
        'spei3',
        'spei4',
        'spei5',
        'spei6',
        'spei7',
        'spei8',
        'spei9',
        'spei10',
        'spei11',
        'spei12'
    ]
}


HOSTS = {}
for host in ADDRESSES:
    for key in ADDRESSES[host]:
        HOSTS[key] = host
