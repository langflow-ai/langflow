def _compute_non_prerelease_version(prerelease_version: str) -> str:
    prerelease_keywords = ["a", "b", "rc", "dev", "post"]
    for keyword in prerelease_keywords:
        if keyword in prerelease_version:
            return prerelease_version.split(keyword)[0][:-1]
    return prerelease_version


def _get_version_info():
    try:
        from langflow.version import __version__  # type: ignore

        prerelease_version = __version__
        version = _compute_non_prerelease_version(prerelease_version)
        package = "Langflow"
    except ImportError:
        from importlib import metadata

        prerelease_version = metadata.version("langflow-base")
        version = _compute_non_prerelease_version(prerelease_version)
        package = "Langflow Base"
    return {"version": prerelease_version, "main_version": version, "package": package}


VERSION_INFO = _get_version_info()


def get_version_info():
    return VERSION_INFO
