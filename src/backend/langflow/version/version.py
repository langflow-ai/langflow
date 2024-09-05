def get_version() -> str:
    """
    Retrieves the version of the package from a possible list of package names.
    This accounts for after package names are updated for -nightly builds.

    Returns:
        str: The version of the package

    Raises:
        ValueError: If the package is not found from the list of package names.
    """
    from importlib import metadata

    pkg_names = [
        "langflow",
        "langflow-base",
        "langflow-nightly",
        "langflow-base-nightly",
    ]
    _version = None
    for pkg_name in pkg_names:
        try:
            _version = metadata.version(pkg_name)
        except (ImportError, metadata.PackageNotFoundError):
            pass

    if _version is None:
        raise ValueError(f"Package not found from options {pkg_names}")

    return _version


def is_pre_release(v: str) -> bool:
    """
    Returns a boolean indicating whether the version is a pre-release version,
    as per the definition of a pre-release segment from PEP 440.
    """
    return any(label in v for label in ["a", "b", "rc"])
