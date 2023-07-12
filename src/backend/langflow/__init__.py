from importlib import metadata
from langflow.cache import cache_manager  # noqa: E402
from langflow.processing.process import load_flow_from_json  # noqa: E402

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""
del metadata  # optional, avoids polluting the results of dir(__package__)


__all__ = ["load_flow_from_json", "cache_manager"]
