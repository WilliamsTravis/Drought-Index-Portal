#!/bin/bash
sudo apt-get update
sudo apt-get install gdal-bin libgdal-dev g++ -y
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
