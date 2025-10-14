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


def _get_langflow_version():
    """Get the installed langflow version."""
    from importlib.metadata import version

    return version("langflow")


def _normalize_for_determinism(obj):
    """Recursively normalize data structures for deterministic serialization.

    Sorts dictionaries by key and lists (where semantically appropriate) to ensure
    the same input always produces the same JSON output.
    """
    if isinstance(obj, dict):
        # Recursively normalize all dict values and return sorted by keys
        return {k: _normalize_for_determinism(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        # Recursively normalize list items
        # Keep list order as-is since some lists are ordered (like field_order)
        return [_normalize_for_determinism(item) for item in obj]
    # Primitive types, return as-is
    return obj


def build_component_index():
    """Build the component index by scanning all modules in lfx.components.

    Returns:
        A dictionary containing version, entries, and sha256 hash
    """
    print("Building component index...")

    # Use the existing import_langflow_components function
    try:
        import asyncio

        from lfx.interface.components import import_langflow_components

        # Run the async function
        components_result = asyncio.run(import_langflow_components())
        modules_dict = components_result.get("components", {})
        components_count = sum(len(v) for v in modules_dict.values())
        print(f"Discovered {components_count} components across {len(modules_dict)} categories")

        # Convert modules_dict to entries format and sort for determinism
        # Sort by category name (top_level) to ensure consistent ordering
        entries = []
        for category_name in sorted(modules_dict.keys()):
            # Sort components within each category by component name
            components_dict = modules_dict[category_name]
            sorted_components = {comp_name: components_dict[comp_name] for comp_name in sorted(components_dict.keys())}
            entries.append([category_name, sorted_components])

    except (ImportError, AttributeError) as e:
        print(f"Failed to import components: {e}", file=sys.stderr)
        return None

    # Build the index structure
    index = {
        "version": _get_langflow_version(),
        "metadata": {
            "num_modules": len(modules_dict),
            "num_components": components_count,
        },
        "entries": entries,
    }

    # Normalize the entire structure for deterministic output
    index = _normalize_for_determinism(index)

    # Calculate hash for integrity verification
    # Note: We calculate hash without the sha256 field itself
    # orjson.dumps returns bytes and handles Enums automatically
    # OPT_SORT_KEYS ensures consistent key ordering in the final JSON
    payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
    index["sha256"] = hashlib.sha256(payload).hexdigest()

    return index


def main():
    """Main entry point for building the component index."""
    # Build the index
    index = build_component_index()

    if not index:
        print("Failed to build component index", file=sys.stderr)
        sys.exit(1)

    # Determine output path relative to script location (repo structure)
    # This script is run during development/CI, not from installed package
    output_path = Path(__file__).parent.parent / "src" / "lfx" / "src" / "lfx" / "_assets" / "component_index.json"

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
