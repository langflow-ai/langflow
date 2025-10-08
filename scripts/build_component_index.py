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
    """Get the installed lfx version."""
    try:
        from importlib.metadata import version

        return version("lfx")
    except (ImportError, ModuleNotFoundError):
        return "0.0.0+unknown"


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

        print(f"Successfully loaded {len(modules_dict)} component categories")

        # Convert modules_dict back to entries format for the index
        entries = [[top_level, components] for top_level, components in modules_dict.items()]

    except (ImportError, AttributeError) as e:
        print(f"Failed to import components: {e}", file=sys.stderr)
        return None

    # Build the index structure
    index = {
        "version": _get_lfx_version(),
        "entries": entries,
    }

    # Calculate hash for integrity verification
    # Note: We calculate hash without the sha256 field itself
    # orjson.dumps returns bytes and handles Enums automatically
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

    # Write the index with pretty formatting for readability in PRs
    print(f"\nWriting index to {output_path}")
    # orjson.dumps with OPT_INDENT_2 for pretty printing
    json_bytes = orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
    output_path.write_text(json_bytes.decode("utf-8"), encoding="utf-8")

    print("\nIndex successfully written!")
    print(f"  Version: {index['version']}")
    print(f"  Modules: {len(index['entries'])}")
    print(f"  SHA256: {index['sha256']}")


if __name__ == "__main__":
    main()
