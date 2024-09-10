import httpx

from typing import Optional
from langflow.logging.logger import logger


def _compute_non_prerelease_version(prerelease_version: str) -> str:
    prerelease_keywords = ["a", "b", "rc", "dev", "post"]
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


def is_pre_release(v: str) -> bool:
    """
    Returns a boolean indicating whether the version is a pre-release version,
    as per the definition of a pre-release segment from PEP 440.
    """
    return any(label in v for label in ["a", "b", "rc"])


def is_nightly(v: str) -> bool:
    """
    Returns a boolean indicating whether the version is a dev (nightly) version,
    as per the definition of a dev segment from PEP 440.
    """
    return "dev" in v


def fetch_latest_version(package_name: str, include_prerelease: bool) -> Optional[str]:
    from packaging import version as pkg_version

    package_name = package_name.replace(" ", "-").lower()
    valid_versions = []
    try:
        response = httpx.get(f"https://pypi.org/pypi/{package_name}/json")
        versions = response.json()["releases"].keys()
        valid_versions = [v for v in versions if include_prerelease or not is_pre_release(v)]

    except Exception as e:
        logger.exception(e)

    finally:
        if not valid_versions:
            return None  # Handle case where no valid versions are found
        return max(valid_versions, key=lambda v: pkg_version.parse(v))


def get_version_info():
    return VERSION_INFO
