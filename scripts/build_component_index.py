"""Build a static component index for fast startup.

This script generates a prebuilt index of all built-in components by walking
through the lfx.components package and processing each module. The index is
saved as a JSON file that can be loaded instantly at runtime, avoiding the
need to import all component modules during startup.
"""

import hashlib
import logging
import sys
from pathlib import Path

import orjson

# Import packaging early and fail fast if not available
try:
    from packaging.version import Version, InvalidVersion
except ImportError as e:
    raise ImportError(
        "The 'packaging' library is required for version comparison. "
        "Install it with: pip install packaging"
    ) from e

# Configure logging for build script
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def _get_langflow_version():
    """Get the installed langflow version."""
    from importlib.metadata import version

    return version("langflow")


def _normalize_for_determinism(obj):
    """Recursively normalize data structures for deterministic serialization.

    Sorts dictionaries by key to ensure consistent ordering. Lists are kept in
    their original order since many lists are semantically ordered (e.g., field_order,
    display_order, etc.).
    
    Note: If upstream code produces nondeterministic list ordering (e.g., from
    reflection or set iteration), this function will NOT fix it. Ensure lists
    are deterministically ordered before calling this function, or consider
    sorting specific list fields that are semantically unordered (e.g., tags).
    """
    if isinstance(obj, dict):
        # Recursively normalize all dict values and return sorted by keys
        return {k: _normalize_for_determinism(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        # Recursively normalize list items but preserve order
        # Lists like field_order, display_order, etc. are semantically ordered
        return [_normalize_for_determinism(item) for item in obj]
    # Primitive types, return as-is
    return obj


def _strip_dynamic_fields(obj):
    """Recursively remove dynamic fields that change with external dependencies.

    This prevents unnecessary hash changes and git history bloat when dependencies update.
    Timestamps are stripped to ensure deterministic builds - version is used as the timeline.
    """
    # List of field names that are dynamically populated from external sources
    # or contain runtime-specific data
    dynamic_field_names = {"timestamp", "deprecated_at"}

    if isinstance(obj, dict):
        return {k: _strip_dynamic_fields(v) for k, v in obj.items() if k not in dynamic_field_names}
    if isinstance(obj, list):
        return [_strip_dynamic_fields(item) for item in obj]
    return obj


def _load_index_from_file(index_path: Path) -> dict | None:
    """Load a component index from a JSON file.
    
    Args:
        index_path: Path to the component index JSON file
        
    Returns:
        Index dict or None if file not found or invalid.
        Note: Validates that loaded JSON is a dict object.
    """
    if not index_path.exists():
        return None
    
    try:
        # orjson.loads() accepts bytes directly - faster and handles any encoding
        data = orjson.loads(index_path.read_bytes())
        
        # Validate that we got a dict (not a list or other JSON type)
        if not isinstance(data, dict):
            logger.warning("Index file %s does not contain a JSON object", index_path)
            return None
            
        return data
    except Exception as e:
        logger.warning("Could not load index from %s: %s", index_path, e)
        return None


def _find_component_in_index(index: dict, category: str, component_name: str) -> dict | None:
    """Find a component in the index by category and name.
    
    Safely handles malformed index entries to prevent crashes if the index
    format evolves or becomes corrupted.
    
    Args:
        index: The component index
        category: Category name
        component_name: Component name
        
    Returns:
        Component data dict or None if not found
    """
    if not index or "entries" not in index:
        return None
    
    for item in index.get("entries", []):
        # Validate entry structure: must be list/tuple with exactly 2 elements
        if not (isinstance(item, (list, tuple)) and len(item) == 2):
            continue
        
        cat_name, components_dict = item
        
        # Validate components_dict is actually a dict
        if not isinstance(components_dict, dict):
            continue
        
        if cat_name == category and component_name in components_dict:
            return components_dict[component_name]
    
    return None


def _compare_versions(version1: str, version2: str) -> int:
    """Compare two version strings using PEP 440 semantics.
    
    Requires the 'packaging' library for correct version comparison.
    Lexicographic string comparison is NOT semver-aware and will produce
    incorrect results (e.g., "1.10.0" < "1.9.0" lexicographically).
    
    Supports formats like:
    - 1.7.1
    - 1.7.1.dev14 (nightly builds)
    - 1.7.1.dev20260107 (date-based nightlies)
    
    Args:
        version1: First version string
        version2: Second version string
        
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
         
    Raises:
        ImportError: If packaging library is not available
    """
    try:
        from packaging.version import Version
    except ImportError as e:
        raise ImportError(
            "The 'packaging' library is required for version comparison. "
            "Install it with: pip install packaging"
        ) from e
    
    v1 = Version(version1)
    v2 = Version(version2)
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0


def _validate_version_range(version_first: str, version_last: str, current_version: str) -> bool:
    """Validate that a version range is valid.
    
    Ensures:
    - version_first <= version_last
    - current_version >= version_last (no going backwards)
    
    Args:
        version_first: Start of version range
        version_last: End of version range
        current_version: Current version being added
        
    Returns:
        True if valid, False otherwise
    """
    # Check that first <= last
    if _compare_versions(version_first, version_last) > 0:
        return False
    
    # Check that current >= last (no going backwards)
    if _compare_versions(current_version, version_last) < 0:
        return False
    
    return True


def _create_history_entry(hash_value: str, version: str) -> dict:
    """Create a new hash history entry with version range.
    
    Args:
        hash_value: Component code hash
        version: Version for both first and last
        
    Returns:
        Hash history entry dict
    """
    return {
        "hash": hash_value,
        "version_first": version,
        "version_last": version
    }


def _normalize_history_to_range_format(history: list[dict]) -> list[dict]:
    """Normalize all history entries to range format.
    
    Converts old format entries ({"hash": ..., "version": ...}) to new range
    format ({"hash": ..., "version_first": ..., "version_last": ...}).
    
    Filters out invalid entries to prevent crashes:
    - Missing hash
    - Missing version fields
    - Invalid version strings (not PEP 440 compliant)
    - Inverted version ranges (first > last)
    
    Args:
        history: List of history entries (may be mixed format)
        
    Returns:
        List of valid history entries in range format
    """
    normalized = []
    for entry in history:
        # Skip entries without a hash
        if not entry.get("hash"):
            logger.warning("Skipping history entry with missing hash")
            continue
            
        if "version_first" in entry:
            # Already in range format - validate it has required fields
            version_first = entry.get("version_first")
            version_last = entry.get("version_last")
            
            if not version_first or not version_last:
                logger.warning("Skipping malformed range entry with missing versions")
                continue
            
            # Validate versions are PEP 440 compliant and range is not inverted
            try:
                v_first = Version(version_first)
                v_last = Version(version_last)
                
                # Check for inverted range
                if v_first > v_last:
                    logger.warning(
                        "Skipping entry with inverted version range: %s > %s",
                        version_first, version_last
                    )
                    continue
            except InvalidVersion:
                logger.warning(
                    "Skipping entry with invalid version strings: %s, %s",
                    version_first, version_last
                )
                continue
                
            normalized.append(entry.copy())
        else:
            # Old format - migrate to range format
            version = entry.get("version")
            if not version:
                logger.warning("Skipping history entry with missing version")
                continue
            
            # Validate version is PEP 440 compliant
            try:
                Version(version)
            except InvalidVersion:
                logger.warning("Skipping entry with invalid version string: %s", version)
                continue
                
            normalized.append({
                "hash": entry["hash"],
                "version_first": version,
                "version_last": version
            })
    return normalized


def _merge_hash_history(
    current_component: dict,
    previous_component: dict | None,
    current_version: str
) -> list[dict]:
    """Merge hash history from previous index with current component using version ranges.
    
    This approach stores version ranges (version_first to version_last) for each hash,
    which dramatically reduces storage when components don't change between versions.
    
    During development of a version:
    - If hash unchanged: Extend version_last of current range
    - If hash changed: Close previous range, start new range
    
    Includes safeguards:
    - Validates version ranges (first <= last)
    - Prevents version regression (current >= last)
    - Handles nightly build format (1.7.1.dev14)
    - Normalizes old format entries to range format
    
    Args:
        current_component: Current component data with code_hash
        previous_component: Previous component data (may have hash_history)
        current_version: Current Langflow version
        
    Returns:
        List of hash history entries with version ranges
    """
    current_hash = current_component.get("metadata", {}).get("code_hash")
    if not current_hash:
        return []
    
    # If no previous component or history, create first entry
    if not previous_component:
        return [_create_history_entry(current_hash, current_version)]
    
    prev_history = previous_component.get("metadata", {}).get("hash_history", [])
    if not prev_history:
        return [_create_history_entry(current_hash, current_version)]
    
    # Normalize entire history to range format at the start
    # This prevents inconsistencies when mixing old and new formats
    # Also filters out invalid entries (missing hash, invalid versions, etc.)
    prev_history = _normalize_history_to_range_format(prev_history)
    
    # If normalization filtered out all entries, start fresh
    if not prev_history:
        logger.warning("All previous history entries were invalid, starting fresh")
        return [_create_history_entry(current_hash, current_version)]
    
    # Get the last entry (most recent) - now guaranteed to be valid and in range format
    last_entry = prev_history[-1]
    last_hash = last_entry.get("hash")
    last_version_first = last_entry.get("version_first")
    last_version_last = last_entry.get("version_last")
    
    # Additional safety check (should never happen after normalization, but be defensive)
    if not last_hash or not last_version_first or not last_version_last:
        logger.error("Normalized entry still has missing data, starting fresh: %s", last_entry)
        return [_create_history_entry(current_hash, current_version)]
    
    # Validate we're not going backwards in versions
    if _compare_versions(current_version, last_version_last) < 0:
        # Version regression detected - log warning but continue
        logger.warning(
            "Version regression detected. Current: %s, Previous: %s. Creating new entry.",
            current_version, last_version_last
        )
        history = prev_history.copy()
        history.append(_create_history_entry(current_hash, current_version))
        return history
    
    # Hash unchanged - extend the version range
    if last_hash == current_hash:
        # Copy all previous entries except the last one
        history = prev_history[:-1].copy() if len(prev_history) > 1 else []
        
        # Validate the extended range
        if _validate_version_range(last_version_first, last_version_last, current_version):
            # Extend the last entry's version range
            history.append({
                "hash": current_hash,
                "version_first": last_version_first,
                "version_last": current_version
            })
        else:
            # Invalid range - create new entry
            logger.warning(
                "Invalid version range detected. First: %s, Last: %s, Current: %s. Creating new entry.",
                last_version_first, last_version_last, current_version
            )
            history.append(last_entry)  # Keep old entry as-is
            history.append(_create_history_entry(current_hash, current_version))
        return history
    
    # Hash changed - close previous range and start new one
    # All entries already normalized, so just copy and append
    history = prev_history.copy()
    history.append(_create_history_entry(current_hash, current_version))
    return history


# Standard location for component index
COMPONENT_INDEX_PATH = Path(__file__).parent.parent / "src" / "lfx" / "src" / "lfx" / "_assets" / "component_index.json"


def _load_previous_index_for_history(preserve_history: bool, previous_index_path: Path | None) -> dict | None:
    """Load previous index if history preservation is enabled.
    
    Args:
        preserve_history: Whether to load previous index
        previous_index_path: Optional custom path to previous index
        
    Returns:
        Previous index dict or None
    """
    if not preserve_history:
        return None
    
    # Use provided path or default to standard location
    index_path = previous_index_path if previous_index_path is not None else COMPONENT_INDEX_PATH
    previous_index = _load_index_from_file(index_path)
    
    if previous_index:
        print(f"Loaded previous index (version {previous_index.get('version', 'unknown')})")
    
    return previous_index


def _import_components() -> tuple[dict, int]:
    """Import all Langflow components using the async import function.
    
    Returns:
        Tuple of (modules_dict, components_count)
        
    Raises:
        RuntimeError: If component import fails
    """
    import asyncio

    from lfx.interface.components import import_langflow_components

    try:
        # Run the async function
        components_result = asyncio.run(import_langflow_components())
        modules_dict = components_result.get("components", {})
        components_count = sum(len(v) for v in modules_dict.values())
        print(f"Discovered {components_count} components across {len(modules_dict)} categories")
        return modules_dict, components_count
    except Exception as e:
        raise RuntimeError(f"Failed to import components: {e}") from e


def build_component_index(preserve_history: bool = True, previous_index_path: Path | None = None):
    """Build the component index by scanning all modules in lfx.components.

    Args:
        preserve_history: If True, merge hash history from previous index
        previous_index_path: Path to previous index (defaults to standard location)

    Returns:
        A dictionary containing version, entries, and sha256 hash
    """
    print("Building component index...")

    # Load previous index if preserving history
    previous_index = _load_previous_index_for_history(preserve_history, previous_index_path)

    # Import all components
    try:
        modules_dict, components_count = _import_components()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return None

    # Get current version
    current_version = _get_langflow_version()

    # Convert modules_dict to entries format and sort for determinism
    # Sort by category name (top_level) to ensure consistent ordering
    entries = []
    for category_name in sorted(modules_dict.keys()):
        # Sort components within each category by component name
        components_dict = modules_dict[category_name]
        sorted_components = {}
        
        for comp_name in sorted(components_dict.keys()):
            # Make defensive copies to avoid mutating the original component object
            # This prevents side effects if modules_dict is used elsewhere
            component = dict(components_dict[comp_name])
            component["metadata"] = dict(component.get("metadata", {}))
            
            if preserve_history and previous_index:
                previous_component = _find_component_in_index(previous_index, category_name, comp_name)
                hash_history = _merge_hash_history(component, previous_component, current_version)
                component["metadata"]["hash_history"] = hash_history
            
            sorted_components[comp_name] = component
        
        entries.append([category_name, sorted_components])

    # Build the index structure
    index = {
        "version": current_version,
        "metadata": {
            "num_modules": len(modules_dict),
            "num_components": components_count,
            "hash_history_format": "inline_ranges_v1",  # Document the format for future evolution
        },
        "entries": entries,
    }

    # Strip dynamic fields from component templates BEFORE normalization
    # This prevents changes in external dependencies (like litellm model lists) from changing the hash
    print("\nStripping dynamic fields from component metadata...")
    index = _strip_dynamic_fields(index)

    # Normalize the entire structure for deterministic output
    # This recursively sorts all dict keys, ensuring consistent ordering
    index = _normalize_for_determinism(index)

    # Calculate SHA256 hash for integrity verification
    # IMPORTANT: Hash is computed BEFORE adding the sha256 field itself
    # Determinism relies on BOTH:
    # 1. _normalize_for_determinism() - recursively sorts dict keys
    # 2. orjson.OPT_SORT_KEYS - ensures consistent serialization
    #
    # To verify integrity later, you must:
    # 1. Load the index
    # 2. Remove the 'sha256' field
    # 3. Serialize with OPT_SORT_KEYS
    # 4. Compare SHA256 hashes
    payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
    index["sha256"] = hashlib.sha256(payload).hexdigest()  # type: ignore[index]

    return index


def main():
    """Main entry point for building the component index."""
    # Build the index
    index = build_component_index()

    if not index:
        print("Failed to build component index", file=sys.stderr)
        sys.exit(1)

    # Use the standard component index path (defined at module level)
    output_path = COMPONENT_INDEX_PATH

    # Create directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Always minify to reduce file size and git history bloat (from 83k to ~5k lines)
    # The index is auto-generated and can be inspected with `jq` if needed
    print(f"\nWriting minified index to {output_path}")
    json_bytes = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
    output_path.write_text(json_bytes.decode("utf-8"), encoding="utf-8")

    print("\nIndex successfully written!")
    print(f"  Version: {index['version']}")
    print(f"  Modules: {index['metadata']['num_modules']}")
    print(f"  Components: {index['metadata']['num_components']}")
    print(f"  SHA256: {index['sha256']}")


if __name__ == "__main__":
    main()
