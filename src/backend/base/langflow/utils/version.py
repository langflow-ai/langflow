def _compute_non_prerelease_version(prerelease_version: str) -> str:
    prerelease_keywords = ["a", "b", "rc"]
    for keyword in prerelease_keywords:
        if keyword in prerelease_version:
            return prerelease_version.split(keyword)[0][:-1]
    return prerelease_version


def _get_version_info():
    """
    Retrieves the version of the package from a possible list of package names.
    This accounts for after package names are updated for -nightly builds.

    Returns:
        str: The version of the package

    Raises:
        ValueError: If the package is not found from the list of package names.
    """
    from importlib import metadata

    package_options = [
        ("langflow", "Langflow"),
        ("langflow-base", "Langflow Base"),
        ("langflow-nightly", "Langflow Nightly"),
        ("langflow-base-nightly", "Langflow Base Nightly"),
    ]
    __version__ = None
    for pkg_name, display_name in package_options:
        try:
            __version__ = metadata.version(pkg_name)
            prerelease_version = __version__
            version = _compute_non_prerelease_version(prerelease_version)

            return {
                "version": prerelease_version,
                "main_version": version,
                "package": display_name,
            }
        except (ImportError, metadata.PackageNotFoundError):
            pass

    if __version__ is None:
        raise ValueError(f"Package not found from options {package_options}")


VERSION_INFO = _get_version_info()


def get_version_info():
    return VERSION_INFO
