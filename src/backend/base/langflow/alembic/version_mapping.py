"""Version to Alembic Revision Mapping.

This file maps Langflow application versions to their required Alembic migration revisions.
It enables safe rollbacks by allowing the application to downgrade the database to a
compatible state when rolling back to an older version.

IMPORTANT: This file must be updated as part of the release process:
1. Before cutting a new release, determine the latest migration revision for that version
2. Add an entry to VERSION_REVISION_MAP with the version and revision ID
3. Commit this file along with the release

Usage:
    The DatabaseService uses this mapping during startup to:
    - Detect when the database is ahead of the application version (rollback scenario)
    - Automatically downgrade the database to the correct revision for the deployed version
    - Prevent startup failures due to missing future migrations
"""

from __future__ import annotations

from typing import Final

# Map of application version to the last migration revision that version expects
# Format: "version": "revision_id"
#
# To find the latest revision for a version:
#   alembic current
# or check the most recent file in src/backend/base/langflow/alembic/versions/
VERSION_REVISION_MAP: Final[dict[str, str]] = {
    # v1.5.x series - Add the actual revision ID when v1.5 was released
    # "1.5.0": "5ace73a7f223",  # Example - replace with actual v1.5.0 head
    # v1.6.x series
    "1.6.0": "eb5e72293a8e",  # Add error and edit flags to message
    "1.6.1": "d37bc4322900",  # Drop single constraint on files.name
    "1.6.2": "d37bc4322900",  # Same as 1.6.1
    "1.6.3": "d37bc4322900",  # Same as 1.6.1
    "1.6.4": "fd531f8868b1",  # Fix Credential table (current)
    # Add new versions here as they are released
}


def get_revision_for_version(version: str) -> str | None:
    """Get the target migration revision for a given application version.

    Args:
        version: Application version (e.g., "1.6.0")

    Returns:
        Alembic revision ID, or None if version not found in mapping

    Examples:
        >>> get_revision_for_version("1.6.0")
        "eb5e72293a8e"
        >>> get_revision_for_version("unknown")
        None
    """
    return VERSION_REVISION_MAP.get(version)


def get_major_minor_version(version: str) -> str:
    """Extract major.minor version from a semantic version string.

    Args:
        version: Full version string (e.g., "1.6.4", "1.6.4-rc1", "1.6.4.post1")

    Returns:
        Major.minor version (e.g., "1.6")

    Examples:
        >>> get_major_minor_version("1.6.4")
        "1.6"
        >>> get_major_minor_version("1.6.0-rc1")
        "1.6"
    """
    # Split by '.' and '-' to handle versions like "1.6.4-rc1"
    parts = version.replace("-", ".").split(".")[:2]
    return ".".join(parts)


def get_revision_for_version_flexible(version: str) -> str | None:
    """Get revision with fallback to major.minor if exact version not found.

    This allows mapping to work even if the exact patch version isn't in the map.
    For example, if only "1.6.0" is mapped, "1.6.4" will still resolve to the 1.6.0 revision.

    Args:
        version: Application version (e.g., "1.6.4")

    Returns:
        Alembic revision ID, or None if no mapping found

    Examples:
        >>> get_revision_for_version_flexible("1.6.4")
        "d37bc4322900"  # Exact match
        >>> get_revision_for_version_flexible("1.6.99")
        "d37bc4322900"  # Falls back to 1.6.x mapping
    """
    # Try exact version first
    revision = get_revision_for_version(version)
    if revision:
        return revision

    # Fall back to major.minor
    major_minor = get_major_minor_version(version)
    return get_revision_for_version(major_minor)


def get_all_known_versions() -> list[str]:
    """Get all versions that have migration mappings.

    Returns:
        List of version strings sorted in ascending order
    """
    return sorted(VERSION_REVISION_MAP.keys())
