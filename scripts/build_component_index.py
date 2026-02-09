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

    Returns:
        A dictionary containing version, entries, and sha256 hash

    Raises:
        RuntimeError: If index cannot be built
        ValueError: If existing index is invalid
    """
    print("Building component index...")

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

            sorted_components[comp_name] = component

        entries.append([category_name, sorted_components])

    index = {
        "version": current_version,
        "metadata": {
            "num_modules": len(modules_dict),
            "num_components": components_count,
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


# Standard location for component index
COMPONENT_INDEX_PATH = Path(__file__).parent.parent / "src" / "lfx" / "src" / "lfx" / "_assets" / "component_index.json"


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

    # Pretty-print for readable git diffs and resolvable merge conflicts
    print(f"\nWriting formatted index to {output_path}")
    json_bytes = orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
    output_path.write_text(json_bytes.decode("utf-8"), encoding="utf-8")

    print("\nIndex successfully written!")
    print(f"  Version: {index['version']}")
    print(f"  Modules: {index['metadata']['num_modules']}")
    print(f"  Components: {index['metadata']['num_components']}")
    print(f"  SHA256: {index['sha256']}")


if __name__ == "__main__":
    main()
