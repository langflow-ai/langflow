from importlib import metadata

from langflow_base.interface.custom.custom_component import CustomComponent
from langflow_base.processing.process import load_flow_from_json

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""
del metadata  # optional, avoids polluting the results of dir(__package__)

__all__ = ["load_flow_from_json", "CustomComponent"]
