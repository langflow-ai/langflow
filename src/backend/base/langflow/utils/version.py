def get_version_info():
    try:
        from langflow.version import __version__  # type: ignore

        version = __version__
        package = "Langflow"
    except ImportError:
        from importlib import metadata

        version = metadata.version("langflow-base")
        package = "Langflow Base"
    return {"version": version, "package": package}
