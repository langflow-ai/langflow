"""Hash validation for custom component code.

This module provides functionality to validate custom component code against
hash history files by comparing code hashes. When allow_custom_components is False,
only components whose hash matches an entry in the hash history are allowed.
"""

import hashlib
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from lfx.log.logger import logger
from lfx.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


# Cache for component hashes from history files (thread-safe)
_component_hash_cache: set[str] | None = None
_cache_settings_key: tuple[str, bool, bool, int] | None = None
_cache_lock = threading.Lock()


def _generate_code_hash(source_code: str) -> str:
    """Generate a hash of the component source code.

    This uses the exact same method as _generate_code_hash in custom/utils.py
    to ensure consistency with the build_hash_history.py script.

    Args:
        source_code: The source code string to hash

    Returns:
        First 12 characters of SHA256 hex digest

    Raises:
        TypeError: If source_code is not a string
        ValueError: If source_code is empty
    """
    if not isinstance(source_code, str):
        msg = "Source code must be a string"
        raise TypeError(msg)

    if not source_code:
        msg = "Empty source code provided"
        raise ValueError(msg)

    # Generate SHA256 hash of the source code (first 12 chars for brevity)
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:12]


def _extract_hashes_from_history(history: dict, allow_code_execution: bool = True) -> tuple[set[str], set[str]]:
    """Extract code hashes from hash history file, separating code-execution components.

    Args:
        history: Hash history dictionary mapping component names to version data
        allow_code_execution: Whether to include components that execute code

    Returns:
        Tuple of (allowed_hashes, code_execution_hashes):
        - allowed_hashes: Set of hashes for components that should be allowed
        - code_execution_hashes: Set of hashes for components marked with executes_code=true

    Raises:
        ValueError: If history data is malformed or invalid
    """
    allowed_hashes: set[str] = set()
    code_execution_hashes: set[str] = set()

    if not history:
        return allowed_hashes, code_execution_hashes

    for component_name, component_data in history.items():
        if not isinstance(component_data, dict):
            msg = f"Invalid component data format for '{component_name}' - expected dict, got {type(component_data).__name__}"
            logger.error(msg)
            raise ValueError(msg)

        if "versions" not in component_data:
            msg = f"Missing 'versions' key for component '{component_name}'"
            logger.error(msg)
            raise ValueError(msg)

        versions = component_data["versions"]
        if not isinstance(versions, dict):
            msg = f"Invalid versions format for component '{component_name}' - expected dict, got {type(versions).__name__}"
            logger.error(msg)
            raise ValueError(msg)

        for version, version_data in versions.items():
            # Support both old format (string hash) and new format (dict with hash and flags)
            if isinstance(version_data, str):
                # Old format: version -> hash (string)
                code_hash = version_data
                executes_code = False
            elif isinstance(version_data, dict):
                # New format: version -> {hash: "...", executes_code: true}
                if "hash" not in version_data:
                    msg = f"Missing 'hash' key for component '{component_name}' version '{version}'"
                    logger.error(msg)
                    raise ValueError(msg)
                code_hash = version_data["hash"]
                executes_code = version_data.get("executes_code", False)
            else:
                msg = f"Invalid version data type for component '{component_name}' version '{version}' - expected str or dict, got {type(version_data).__name__}"
                logger.error(msg)
                raise ValueError(msg)

            if not isinstance(code_hash, str):
                msg = f"Invalid hash type for component '{component_name}' version '{version}' - expected str, got {type(code_hash).__name__}"
                logger.error(msg)
                raise ValueError(msg)
            if not code_hash:
                msg = f"Empty hash for component '{component_name}' version '{version}'"
                logger.error(msg)
                raise ValueError(msg)

            # Track code execution components separately
            if executes_code:
                code_execution_hashes.add(code_hash)
                if allow_code_execution:
                    allowed_hashes.add(code_hash)
                else:
                    logger.debug(
                        f"Excluding code-execution component '{component_name}' version '{version}' "
                        f"(hash: {code_hash}) due to allow_code_execution_components=False"
                    )
            else:
                allowed_hashes.add(code_hash)

    return allowed_hashes, code_execution_hashes


def _load_hash_history(settings_service: "SettingsService") -> set[str]:
    """Load and cache component hashes from hash history files.

    Loads from stable_hash_history.json and optionally from nightly_hash_history.json
    based on the allow_nightly_core_components setting. Respects the
    allow_code_execution_components setting to filter out code-execution components.

    Args:
        settings_service: Settings service instance

    Returns:
        Set of allowed code hashes from stable and optionally nightly history
    """
    # Determine the base path for hash history files
    # They should be in src/lfx/src/lfx/_assets/
    assets_path = Path(__file__).parent.parent / "_assets"

    stable_history_path = assets_path / "stable_hash_history.json"
    nightly_history_path = assets_path / "nightly_hash_history.json"

    all_hashes: set[str] = set()
    all_code_execution_hashes: set[str] = set()

    if not stable_history_path.exists():
        msg = f"Stable hash history file not found at {stable_history_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    allow_code_execution = settings_service.settings.allow_code_execution_components

    try:
        stable_history = orjson.loads(stable_history_path.read_bytes())
        stable_hashes, stable_code_exec = _extract_hashes_from_history(stable_history, allow_code_execution)
        all_hashes.update(stable_hashes)
        all_code_execution_hashes.update(stable_code_exec)
        logger.debug(
            f"Loaded {len(stable_hashes)} allowed hashes from stable hash history\n"
            f"with ({len(stable_code_exec)} code-execution components)"
        )
    except Exception as e:
        msg = f"Failed to load stable hash history at {stable_history_path}: {e}"
        logger.error(msg)
        raise ValueError(msg) from e

    if settings_service.settings.allow_nightly_core_components:
        if not nightly_history_path.exists():
            msg = f"Nightly hash history file not found at {nightly_history_path} (allow_nightly_core_components=True)"
            logger.error(msg)
            raise FileNotFoundError(msg)

        try:
            nightly_history = orjson.loads(nightly_history_path.read_bytes())
            nightly_hashes, nightly_code_exec = _extract_hashes_from_history(nightly_history, allow_code_execution)
            all_hashes.update(nightly_hashes)
            all_code_execution_hashes.update(nightly_code_exec)
            logger.debug(
                f"Loaded {len(nightly_hashes)} allowed hashes from nightly hash history\n"
                f"with ({len(nightly_code_exec)} code-execution components)"
            )
        except Exception as e:
            msg = f"Failed to load nightly hash history at {nightly_history_path}: {e}"
            logger.error(msg)
            raise ValueError(msg) from e
    else:
        logger.debug("Nightly custom components are disabled, only using stable hash history")

    if not all_hashes and not all_code_execution_hashes:
        msg = "No hashes loaded from hash history files"
        logger.error(msg)
        raise ValueError(msg)

    if not allow_code_execution and all_code_execution_hashes:
        logger.info(
            f"Code execution components disabled: {len(all_code_execution_hashes)} components blocked. "
            f"{len(all_hashes)} components allowed."
        )

    logger.debug(f"Total {len(all_hashes)} unique hashes loaded for validation")
    return all_hashes


def _get_cached_hashes(settings_service: "SettingsService") -> set[str]:
    """Get cached component hashes from hash history, loading if necessary.

    Thread-safe cache access using a lock to prevent race conditions.

    Args:
        settings_service: Settings service instance

    Returns:
        Set of allowed code hashes
    """
    global _component_hash_cache, _cache_settings_key  # noqa: PLW0603

    # Create a cache key based on settings that affect hash loading
    current_key = (
        "hash_history",
        settings_service.settings.allow_nightly_core_components,
        settings_service.settings.allow_code_execution_components,
        id(settings_service.settings),
    )

    with _cache_lock:
        # If settings changed, invalidate cache
        if _cache_settings_key != current_key:
            _component_hash_cache = None
            _cache_settings_key = current_key

        # Load if not cached
        if _component_hash_cache is None:
            _component_hash_cache = _load_hash_history(settings_service)

        return _component_hash_cache


def is_code_hash_allowed(source_code: str, settings_service: "SettingsService | None" = None) -> bool:
    """Check if source code hash is allowed based on hash history.

    CRITICAL: This function fails fast on any errors. Hash validation is a security-critical
    operation and any failures indicate a serious problem that must be addressed immediately.

    Args:
        source_code: The source code to validate
        settings_service: Settings service instance (optional, will be fetched if None)

    Returns:
        True if hash is allowed, False otherwise

    Raises:
        ValueError: If hash generation or validation fails
        FileNotFoundError: If hash history files are missing
    """
    # Edge case: empty or whitespace-only code
    if not source_code or not source_code.strip():
        # Empty code should be allowed (will fail validation elsewhere if needed)
        return True

    # If no settings service provided, try to get it
    if settings_service is None:
        settings_service = get_settings_service()

    # If still no settings service, fail fast
    if settings_service is None:
        msg = "Settings service is not available for hash validation"
        logger.error(msg)
        raise ValueError(msg)

    # Check if custom components are allowed
    if settings_service.settings.allow_custom_components:
        # Warn if code execution components setting is disabled but being ignored
        if not settings_service.settings.allow_code_execution_components:
            logger.warning(
                "SECURITY WARNING: LANGFLOW_ALLOW_CODE_EXECUTION_COMPONENTS=false is being ignored "
                "because LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true. Code-execution components "
                "are currently ALLOWED. "
            )
        return True

    code_hash = _generate_code_hash(source_code)
    allowed_hashes = _get_cached_hashes(settings_service)

    is_allowed = code_hash in allowed_hashes

    if not is_allowed:
        logger.warning(
            f"Custom code blocked: hash {code_hash} not found in hash history. "
            f"Hash history has {len(allowed_hashes)} allowed hashes. "
            "Set LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true to allow custom code."
        )
    return is_allowed
