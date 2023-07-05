# This file is used by lc-serve to load the mounted app and serve it.

from langflow.main import setup_app
from langflow.utils.logger import configure

configure(log_level="DEBUG")
app = setup_app()
