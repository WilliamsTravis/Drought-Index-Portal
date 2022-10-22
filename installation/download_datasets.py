# -*- coding: utf-8 -*-
"""Download rainfall and drought indices."""
from drip.downloaders.wwdt import WWDT_Builder
from drip.downloaders.cpc import CPC_Builder
from drip.loggers import init_logger, set_handler
from drip.app.options.options import INDEX_NAMES

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
