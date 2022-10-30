"""Index for main Drip page."""
import drip.app.pages.main.callbacks

from drip import calls
from drip.app.app import app, server


if __name__ == "__main__":
    app.run_server(dev_tools_hot_reload=True, debug=False, port=8050)
