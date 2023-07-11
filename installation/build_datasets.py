# -*- coding: utf-8 -*-
"""Download rainfall and drought indices."""
import sys

from drip import Paths
from drip.app.options.options import INDEX_NAMES
from drip.downloaders.utilities import Data_Builder
from drip.loggers import init_logger, set_handler

logger = init_logger(__name__)
set_handler(logger, Paths.home.joinpath("installation/installation.log"))


def main():
    """Download and format all needed files for the prf app."""
    for index, desc in INDEX_NAMES.items():
        if not index.startswith("ri"):
            logger.info("Building %s ...", index)
            print(f"Building {index}...")
            builder = Data_Builder(index)
            try:
                builder.build(overwrite=True)
            except Exception as error:
                print(f" {index} build failed: {error}")
                logger.error("%s build failed: %s.", index, error,
                             stack_info=sys.exc_info(), stacklevel=1)
                raise


if __name__ == "__main__":
    main()
