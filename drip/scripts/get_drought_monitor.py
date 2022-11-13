# -*- coding: utf-8 -*-
"""Build Drought Index Grids.

Created on Sun Aug 29 09:48:03 2021

@author: travis
"""
import os
from drip import DATA_PATH  # Make this data path


URL = ""


class Drought_Monitor:
    """Methods for retrieving and reformatting the Drought Monitor."""

    def __init__(self, home=DATA_PATH):
        """Initialize Drought_Monitor object."""
        self.home = os.path.abspath(os.path.expanduser(home))

    def __repr__(self):
        """Return Drought_Monitor representation string."""
        return f"<Drought_Monitor: home={self.home}"


if __name__ == "__main__":
    self = Drought_Monitor()
