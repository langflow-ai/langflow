"""Hash validation for custom component code.

This module provides functionality to validate custom component code against
a component index by comparing code hashes. When allow_custom_components is False,
only components whose hash matches an entry in the component index are allowed.
"""

import hashlib
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


# Cache for component index hashes
_component_hash_cache: set[str] | None = None
_cache_settings_key: tuple[str, int] | None = None


def _generate_full_hash(source_code: str) -> str:
    """Generate full SHA256 hash of source code.

    Args:
        source_code: The source code string to hash

    Returns:
        Full SHA256 hex digest (64 characters)
    """
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()


def _generate_short_hash(source_code: str) -> str:
    """Generate short hash (first 12 chars) of source code for comparison.

    Args:
        source_code: The source code string to hash

    Returns:
        First 12 characters of SHA256 hex digest
    """
    return _generate_full_hash(source_code)[:12]


def _extract_hashes_from_index(index: dict) -> set[str]:
    """Extract all code hashes from component index.

    Args:
        index: Component index dictionary

    Returns:
        Set of code hashes (12-character prefixes)
    """
    hashes: set[str] = set()

    if not index or "entries" not in index:
        return hashes

    for category_name, components_dict in index.get("entries", []):
        if not isinstance(components_dict, dict):
            continue

        for component_name, component_data in components_dict.items():
            if not isinstance(component_data, dict):
                continue

            metadata = component_data.get("metadata", {})
            if isinstance(metadata, dict):
                code_hash = metadata.get("code_hash")
                if isinstance(code_hash, str) and code_hash:
                    hashes.add(code_hash)

    return hashes


def _load_component_index_hashes(settings_service: "SettingsService") -> set[str]:
    """Load and cache component index hashes.

    Args:
        settings_service: Settings service instance

    Returns:
        Set of allowed code hashes
    """
    from lfx.interface.components import _read_component_index

    # Try to load from custom path first, then built-in
    custom_index_path = settings_service.settings.components_index_path

    index = _read_component_index(custom_index_path)

    if not index:
        # Fallback to built-in index
        index = _read_component_index(None)

    if not index:
        logger.warning(
            "Component index not available for hash validation. Custom code blocking may not work correctly."
        )
        return set()

    hashes = _extract_hashes_from_index(index)

    return hashes


def _get_cached_hashes(settings_service: "SettingsService") -> set[str]:
    """Get cached component hashes, loading if necessary.

    Args:
        settings_service: Settings service instance

    Returns:
        Set of allowed code hashes
    """
    global _component_hash_cache, _cache_settings_key

    # Create a cache key based on settings that affect the index
    current_key = (
        settings_service.settings.components_index_path or "builtin",
        id(settings_service.settings),
    )

    # If settings changed, invalidate cache
    if _cache_settings_key != current_key:
        _component_hash_cache = None
        _cache_settings_key = current_key

    # Load if not cached
    if _component_hash_cache is None:
        _component_hash_cache = _load_component_index_hashes(settings_service)

    return _component_hash_cache


def is_code_hash_allowed(source_code: str, settings_service: "SettingsService | None" = None) -> bool:
    """Check if source code hash is allowed based on component index.

    Args:
        source_code: The source code to validate
        settings_service: Settings service instance (optional, will be fetched if None)

    Returns:
        True if hash is allowed, False otherwise
    """
    # Edge case: empty or whitespace-only code
    if not source_code or not source_code.strip():
        # Empty code should be allowed (will fail validation elsewhere if needed)
        return True

    # If no settings service provided, try to get it
    if settings_service is None:
        try:
            from lfx.services.deps import get_settings_service

            settings_service = get_settings_service()
        except Exception:  # noqa: BLE001
            # If we can't get settings service, default to allowing code
            # (fail open for backward compatibility)
            return True

    # If still no settings service, allow code
    if settings_service is None:
        return True

    # Check if custom components are allowed
    if settings_service.settings.allow_custom_components:
        return True

    try:
        code_hash = _generate_short_hash(source_code)
        allowed_hashes = _get_cached_hashes(settings_service)

        is_allowed = code_hash in allowed_hashes

        if not is_allowed:
            logger.warning(
                f"Custom code blocked: hash {code_hash} not found in component index. "
                f"Index has {len(allowed_hashes)} allowed hashes. "
                "Set LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true to allow custom code."
            )

        return is_allowed
    except Exception as exc:  # noqa: BLE001
        # If hash generation fails, log and allow (fail open for safety)
        logger.warning(f"Error validating code hash: {exc}. Allowing code execution.")
        return True
