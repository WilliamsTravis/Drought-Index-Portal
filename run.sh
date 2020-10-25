#!/bin/bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate drip
cd ~/github/Drought-Index-Portal
gunicorn -w 4 app:server --daemon

