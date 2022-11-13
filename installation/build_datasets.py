# -*- coding: utf-8 -*-
"""Download rainfall and drought indices."""
from drip.app.options.options import INDEX_NAMES
from drip.downloaders.utilities import Data_Builder
from drip.loggers import init_logger

logger = init_logger(__name__)


def main():
    """Download and format all needed files for the prf app."""
    for index, desc in INDEX_NAMES.items():
        if not index.startswith("ri"):
            if "Index" in desc:
                logger.info("Building %s ...", index)
                print(f"Building {index}...")
                builder = Data_Builder(index)
                builder.build(overwrite=False)


if __name__ == "__main__":
    main()
