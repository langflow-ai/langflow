"""Build a static component index for fast startup.

This script generates a prebuilt index of all built-in components by walking
through the lfx.components package and processing each module. The index is
saved as a JSON file that can be loaded instantly at runtime, avoiding the
need to import all component modules during startup.
"""

import hashlib
import sys
from pathlib import Path

import orjson

try:
    from packaging.version import InvalidVersion, Version
except ImportError as e:
    msg = "The 'packaging' library is required for version comparison"
    raise ImportError(msg) from e


def _get_lfx_version():
    """Get the installed lfx version.

    Components are located in LFX, so use LFX.
    """
    from importlib.metadata import version

    version = version("lfx")
    print(f"Retrieved LFX version: {version}")
    return version


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


def _load_index_from_file(index_path: Path) -> dict:
    """Load a component index from a JSON file.

    Args:
        index_path: Path to the component index JSON file

    Returns:
        Index dict

    Raises:
        ValueError: If file not found
        RuntimeError: If file cannot be loaded or is invalid
    """
    if not index_path.exists():
        msg = "Index file not found. Index file must exist to preserve hash history."
        raise ValueError(msg)

    try:
        # orjson.loads() accepts bytes directly - faster and handles any encoding
        data = orjson.loads(index_path.read_bytes())

        # Validate that we got a dict (not a list or other JSON type)
        if not isinstance(data, dict):
            msg = "Index file does not contain a valid JSON object."
            raise TypeError(msg)

        return data  # noqa: TRY300
    except Exception as e:
        msg = f"Failed to load component index from {index_path}. Must exist to preserve hash history. Error: {e}"
        raise RuntimeError(msg) from e


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

    # Index entries are [category_name, components_dict] tuples
    entry_tuple_size = 2

    for item in index.get("entries", []):
        # Validate entry structure: must be list/tuple with exactly 2 elements
        if not (isinstance(item, list | tuple) and len(item) == entry_tuple_size):
            msg = f"Invalid index entry format: {item}. Expected {entry_tuple_size}-element list/tuple."
            raise ValueError(msg)

        cat_name, components_dict = item

        # Validate components_dict is actually a dict
        if not isinstance(components_dict, dict):
            msg = f"Invalid components dict for category {cat_name}"
            raise TypeError(msg)

        if cat_name == category and component_name in components_dict:
            return components_dict[component_name]

    return None


# Constants for component metadata keys
METADATA_KEY = "metadata"
CODE_HASH_KEY = "code_hash"
HASH_KEY = "hash"  # Key used in hash_history entries
VERSION_FIRST_KEY = "v_from"  # Hash valid from Version (inclusive)
VERSION_LAST_KEY = "v_to"  # Hash valid to version (inclusive)


def _get_component_hash(component: dict | None) -> str | None:
    """Extract code hash from a component.

    Args:
        component: Component dict with metadata

    Returns:
        Code hash string or None if not found
    """
    if not component:
        return None
    return component.get(METADATA_KEY, {}).get(CODE_HASH_KEY)


def _parse_version(version_str: str) -> Version:
    """Parse a version string, handling nightly/dev builds.

    Args:
        version_str: Version string (e.g., "1.7.1" or "1.7.1.dev14")

    Returns:
        Parsed Version object

    Raises:
        InvalidVersion: If version string is malformed
    """
    try:
        return Version(version_str)
    except InvalidVersion as e:
        msg = f"Invalid version string '{version_str}': {e}"
        raise InvalidVersion(msg) from e


def _validate_history_entry(entry: dict, entry_index: int) -> None:
    """Validate a hash history entry has required fields and valid version range.

    Args:
        entry: Hash history entry dict
        entry_index: Index in history list (for error messages)

    Raises:
        ValueError: If entry is malformed or has invalid version range
    """
    # Check required fields exist
    if HASH_KEY not in entry:
        msg = f"History entry {entry_index} missing required field '{HASH_KEY}'"
        raise ValueError(msg)
    if VERSION_FIRST_KEY not in entry:
        msg = f"History entry {entry_index} missing required field '{VERSION_FIRST_KEY}'"
        raise ValueError(msg)
    if VERSION_LAST_KEY not in entry:
        msg = f"History entry {entry_index} missing required field '{VERSION_LAST_KEY}'"
        raise ValueError(msg)

    # Validate version range (first <= last)
    try:
        version_first = _parse_version(entry[VERSION_FIRST_KEY])
        version_last = _parse_version(entry[VERSION_LAST_KEY])

        if version_first > version_last:
            msg = (
                f"History entry {entry_index} has invalid version range: "
                f"{entry[VERSION_FIRST_KEY]} > {entry[VERSION_LAST_KEY]}"
            )
            raise ValueError(msg)
    except InvalidVersion as e:
        msg = f"History entry {entry_index} has invalid version: {e}"
        raise ValueError(msg) from e


def _create_history_entry(hash_value: str, version: str) -> dict:
    """Create a new hash history entry with version range.

    Args:
        hash_value: Component code hash
        version: Version for both first and last

    Returns:
        Hash history entry dict

    Raises:
        InvalidVersion: If version string is malformed
    """
    # Validate version can be parsed
    _parse_version(version)
    return {HASH_KEY: hash_value, VERSION_FIRST_KEY: version, VERSION_LAST_KEY: version}


def _merge_hash_history(current_component: dict, existing_component: dict | None, current_version: str) -> list[dict]:
    """Merge hash history from existing index with current component using version ranges.

    This approach stores version ranges (version_first to version_last) for each hash,
    which dramatically reduces storage when components don't change between versions.

    During development of a version:
    - If hash unchanged: Extend version_last of current range
    - If hash changed: Close existing range, start new range

    Includes safeguards:
    - Validates version ranges (first <= last)
    - Prevents version regression (current >= last)
    - Handles nightly build format (1.7.1.dev14)
    - Validates all history entries have required fields

    Args:
        current_component: Current component data with code_hash
        existing_component: Existing component from disk
        current_version: Current lfx version

    Returns:
        List of hash history entries with version ranges

    Raises:
        ValueError: If history entries are malformed or version regression detected
        InvalidVersion: If version strings cannot be parsed
    """
    current_hash = _get_component_hash(current_component)
    if not current_hash:
        return []

    # Parse and validate current version (will raise InvalidVersion if malformed)
    current_ver = _parse_version(current_version)

    # Get existing hash history if it exists
    existing_history = []
    if existing_component:
        existing_history = existing_component.get(METADATA_KEY, {}).get("hash_history", [])

    # If no existing history, start fresh
    if not existing_history:
        return [_create_history_entry(current_hash, current_version)]

    # Validate all existing history entries (will raise on invalid entries)
    for i, entry in enumerate(existing_history):
        _validate_history_entry(entry, i)

    # Get the most recent history entry
    last_entry = existing_history[-1]
    last_hash = last_entry.get(HASH_KEY)
    last_version_str = last_entry[VERSION_LAST_KEY]

    # Prevent version regression - current must be >= last
    last_ver = _parse_version(last_version_str)
    if current_ver < last_ver:
        msg = (
            f"Version regression detected: current version {current_version} < "
            f"last version {last_version_str}. Cannot build index with older version."
        )
        raise ValueError(msg)

    # If hash hasn't changed, extend the version_last of the most recent entry
    if current_hash == last_hash:
        return [
            *existing_history[:-1],
            {
                HASH_KEY: last_hash,
                VERSION_FIRST_KEY: last_entry[VERSION_FIRST_KEY],
                VERSION_LAST_KEY: current_version,
            },
        ]

    # Hash changed - append new entry to history
    return [*existing_history, _create_history_entry(current_hash, current_version)]


# Standard location for component index
COMPONENT_INDEX_PATH = Path(__file__).parent.parent / "src" / "lfx" / "src" / "lfx" / "_assets" / "component_index.json"


def _load_existing_index() -> dict:
    """Load existing index from disk for history merging.

    Returns:
        Existing index dict

    Raises:
        RuntimeError: If index file cannot be loaded
    """
    existing_index = _load_index_from_file(COMPONENT_INDEX_PATH)
    print(f"Loaded existing index (version {existing_index.get('version', 'unknown')})")
    return existing_index


def _import_components() -> tuple[dict, int]:
    """Import all lfx components using the async import function.

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
    except Exception as e:
        msg = f"Failed to import components: {e}"
        raise RuntimeError(msg) from e
    else:
        return modules_dict, components_count


def build_component_index() -> dict:
    """Build the component index by scanning all modules in lfx.components.

    Merges hash history from the existing index to track component evolution.

    Returns:
        A dictionary containing version, entries, and sha256 hash

    Raises:
        RuntimeError: If index cannot be built
        ValueError: If existing index is invalid
    """
    print("Building component index...")

    existing_index = _load_existing_index()
    modules_dict, components_count = _import_components()
    current_version = _get_lfx_version()

    # Convert modules_dict to entries format and sort for determinism
    # Sort by category name (top_level) to ensure consistent ordering
    entries = []
    for category_name in sorted(modules_dict.keys()):
        # Sort components within each category by component name
        components_dict = modules_dict[category_name]
        sorted_components = {}

        for comp_name in sorted(components_dict.keys()):
            # Make defensive copies to avoid mutating the original component object
            component = dict(components_dict[comp_name])
            component["metadata"] = dict(component.get("metadata", {}))

            existing_component = (
                _find_component_in_index(existing_index, category_name, comp_name) if existing_index else None
            )
            hash_history = _merge_hash_history(component, existing_component, current_version)
            component["metadata"]["hash_history"] = hash_history

            sorted_components[comp_name] = component

        entries.append([category_name, sorted_components])

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
    try:
        # Build the index - will raise on any error
        index = build_component_index()
    except Exception as e:  # noqa: BLE001
        print(f"Failed to build component index: {e}", file=sys.stderr)
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
