# -*- coding: utf-8 -*-
"""Download rainfall and drought indices.

Combination of spi6 failed with incorrect shape: target spatial shape: (1405, 621), generated spatial shape (1705, 741)
Traceback (most recent call last):
  File "/home/travis/github/Drought-Index-Portal/installation/download_datasets.py", line 52, in <module>
    main()
  File "/home/travis/github/Drought-Index-Portal/installation/download_datasets.py", line 40, in main
    get_wwdt()
  File "/home/travis/github/Drought-Index-Portal/installation/download_datasets.py", line 23, in get_wwdt
    di.build(overwrite=False)
  File "/home/travis/github/Drought-Index-Portal/drip/downloaders/wwdt.py", line 98, in build
    self.combine()
  File "/home/travis/github/Drought-Index-Portal/drip/downloaders/wwdt.py", line 139, in combine
    assert tshape == nshape
AssertionError

Author: travis
Date: Sun 05 Jun 2022 09:35:02 AM MDT
"""
from drip.downloaders.wwdt import WWDT_Builder
from drip.downloaders.cpc import CPC_Builder
from drip.loggers import init_logger, set_handler
from drip.options import INDEX_NAMES

logger = init_logger(__name__)


def get_wwdt():
    """Download all WWDT datasets specified in drip.options."""
    ri = CPC_Builder()
    for index in INDEX_NAMES:
        if not index.startswith("ri"):
            logger.info("Building %s ...", index)
            print(f"Building {index}...")
            di = WWDT_Builder(index, template=ri.final_path)
            di.build(overwrite=False)


def get_cpc():
    """Download all CPC datasets specified in drip.options."""
    logger.info("Building CPC rainfall index...")
    print("Building CPC rainfall index...")
    ri = CPC_Builder()
    ri.build(overwrite=True)


def main():
    """Download and format all needed files for the prf app."""
    # Get the current rainfall index
    get_cpc()

    # Download each index we have labels for
    get_wwdt()

    # Download EDDI

    # Download Gridmet

    # Download LERI

    # Download USDM (custom dataset)


if __name__ == "__main__":
    main()
