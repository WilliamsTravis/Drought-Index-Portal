"""Index for main Drip page."""
import drip.app.pages.main.callbacks

from drip import calls
from drip.app.app import app, server

DEBUG = True


if __name__ == "__main__":
    if DEBUG:
        app.run(debug=False)
    else:
        app.run(debug=False, host="0.0.0.0", port=8050)