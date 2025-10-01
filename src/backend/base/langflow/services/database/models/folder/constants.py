import os

DEFAULT_FOLDER_DESCRIPTION = "Manage your own flows. Download and upload projects."
DEFAULT_FOLDER_NAME = "OpenRAG" if os.getenv("RUN_WITH_OPENRAG", "").lower() == "true" else "Starter Project"
