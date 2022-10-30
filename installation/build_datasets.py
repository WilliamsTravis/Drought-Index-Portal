# -*- coding: utf-8 -*-
"""Download rainfall and drought indices."""
from drip.app.options.options import INDEX_NAMES
from drip.downloaders.utilities import Data_Builder
from drip.loggers import init_logger, set_handler

logger = init_logger(__name__)


def get_wwdt():
    """Download all WWDT datasets specified in drip.options."""
    for index in INDEX_NAMES:
        if not index.startswith("ri") or index.startswith("eddi"):
            logger.info("Building %s ...", index)
            print(f"Building {index}...")
            builder = Data_Builder(index)
            builder.build(overwrite=False)




def main():
    """Download and format all needed files for the prf app."""
    # Download each index we have labels for
    get_wwdt()

    # Download EDDI

    # Download Gridmet

    # Download LERI

    # Download USDM (custom dataset)


if __name__ == "__main__":
    main()
