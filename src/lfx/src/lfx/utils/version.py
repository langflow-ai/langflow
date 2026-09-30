"""Version utilities for lfx package."""


def get_version_info():
    """Get version information for compatibility.

    This is a stub implementation for lfx package.
    """
    return {"version": "0.1.0", "package": "lfx"}


def is_pre_release(version: str) -> bool:
    """Check if a version is a pre-release.

    Args:
        version: Version string to check

    Returns:
        bool: True if version is a pre-release
    """
    # Check for common pre-release indicators
    pre_release_indicators = ["alpha", "beta", "rc", "dev", "a", "b"]
    version_lower = version.lower()
    return any(indicator in version_lower for indicator in pre_release_indicators)
