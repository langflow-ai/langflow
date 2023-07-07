# This file is used by lc-serve to load the mounted app and serve it.

import os

# Use the JCLOUD_WORKSPACE for db URL if it's provided by JCloud.
if "JCLOUD_WORKSPACE" in os.environ:
    os.environ[
        "LANGFLOW_DATABASE_URL"
    ] = f"sqlite:///{os.environ['JCLOUD_WORKSPACE']}/langflow.db"

from langflow.main import setup_app
from langflow.utils.logger import configure

configure(log_level="DEBUG")
app = setup_app()
