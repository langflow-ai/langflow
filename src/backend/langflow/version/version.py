from importlib import metadata

try:
    __version__ = metadata.version("langflow")
except metadata.PackageNotFoundError:
    __version__ = ""
del metadata
