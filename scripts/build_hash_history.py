#!/usr/bin/env python3
import argparse
import asyncio
import copy
from pathlib import Path

import orjson
from packaging.version import Version

STABLE_HISTORY_FILE = "src/lfx/src/lfx/_assets/stable_hash_history.json"
NIGHTLY_HISTORY_FILE = "src/lfx/src/lfx/_assets/nightly_hash_history.json"


def get_lfx_version():
    """Get the installed lfx version."""
    from importlib.metadata import PackageNotFoundError, version

    # Try lfx-nightly first (for nightly builds), then fall back to lfx
    try:
        return version("lfx-nightly")
    except PackageNotFoundError:
        return version("lfx")


def load_hash_history(file_path: Path) -> dict:
    """Loads a hash history file."""
    if not file_path.exists():
        return {}
    return orjson.loads(file_path.read_bytes())


def save_hash_history(file_path: Path, history: dict):
    """Saves a hash history file."""
    file_path.write_text(orjson.dumps(history, option=orjson.OPT_INDENT_2).decode("utf-8"), encoding="utf-8")


def _import_components() -> tuple[dict, int]:
    """Import all lfx components using the async import function.

    Returns:
        Tuple of (modules_dict, components_count)

    Raises:
        RuntimeError: If component import fails
    """
    from lfx.interface.components import import_langflow_components

    try:
        components_result = asyncio.run(import_langflow_components())
        modules_dict = components_result.get("components", {})
        components_count = sum(len(v) for v in modules_dict.values())
        print(f"Discovered {components_count} components across {len(modules_dict)} categories")
    except Exception as e:
        msg = f"Failed to import components: {e}"
        raise RuntimeError(msg) from e
    else:
        return modules_dict, components_count


def update_history(history: dict, component_name: str, code_hash: str, current_version: str) -> dict:
    """Updates the hash history for a single component with the new simple schema.

    IMPORTANT: Note that the component_name acts as the unique identifier for the component, and must not be changed.
    """
    current_version_parsed = Version(current_version)
    # Use the string representation of the version as the key
    # For dev versions (nightly), this includes the full version with dev suffix (e.g., "0.8.0.dev13")
    # For stable versions, this is just major.minor.micro (e.g., "0.8.0")
    version_key = str(current_version_parsed)

    if component_name not in history:
        print(f"Component {component_name} not found in history. Adding...")
        warning_msg = (
            f"WARNING - Ensure that Component {component_name} is a NEW Component. "
            "If not, this is an error and will lose hash history for this component."
        )
        print(warning_msg)
        history[component_name] = {}
        history[component_name]["versions"] = {version_key: code_hash}
    else:
        # Ensure that we aren't ovewriting a previous version
        for v in history[component_name]["versions"]:
            parsed_version = Version(v)
            if parsed_version > current_version_parsed:
                # If this happens, we are overwriting a previous version.
                msg = (
                    f"ERROR - Component {component_name} already has a version {v} that is greater than the current "
                    f"version {current_version}."
                )
                raise ValueError(msg)
        history[component_name]["versions"][version_key] = code_hash

    return history


def validate_append_only(old_history: dict, new_history: dict) -> None:
    """Validate that the new history only adds data, never removes it.

    Args:
        old_history: The previous hash history
        new_history: The updated hash history

    Raises:
        ValueError: If components or versions were removed
    """
    # Check that no components were removed
    old_components = set(old_history.keys())
    new_components = set(new_history.keys())
    removed_components = old_components - new_components

    if removed_components:
        msg = (
            f"ERROR: Components were removed: {removed_components}\n"
            "Hash history must be append-only. Components cannot be deleted."
        )
        raise ValueError(msg)

    # Check that no version keys were removed from existing components
    for component in old_components:
        if component in new_history:
            old_versions = set(old_history[component].get("versions", {}).keys())
            new_versions = set(new_history[component].get("versions", {}).keys())
            removed_versions = old_versions - new_versions

            if removed_versions:
                msg = (
                    f"ERROR: Versions removed from component '{component}': {removed_versions}\n"
                    "Hash history must be append-only. Version keys cannot be deleted."
                )
                raise ValueError(msg)

    print("✓ Append-only validation passed - no components or versions were removed")


def main(argv=None):
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Build and update component hash history.")
    parser.add_argument("--nightly", action="store_true", help="Update the nightly hash history.")
    args = parser.parse_args(argv)

    current_version = get_lfx_version()
    print(f"Current LFX version: {current_version}")

    if args.nightly:
        if "dev" not in str(current_version):
            err = (
                f"Cannot update nightly hash history for a non-dev version.\n"
                f"Expected version format: X.Y.Z.devN (e.g., 0.3.0.dev13)\n"
                f"Got: {current_version}\n"
                f"This indicates the LFX package was not properly updated to a nightly version."
            )
            raise ValueError(err)
        history_file = NIGHTLY_HISTORY_FILE
        print(f"✓ Version check passed: {current_version} is a dev version")
        print("Updating nightly hash history...")
    else:
        if "dev" in str(current_version):
            err = (
                f"Cannot update stable hash history for a dev version.\n"
                f"Expected version format: X.Y.Z (e.g., 0.3.0)\n"
                f"Got: {current_version}\n"
                f"This indicates the LFX package is a development version, not a stable release."
            )
            raise ValueError(err)
        history_file = STABLE_HISTORY_FILE
        print(f"✓ Version check passed: {current_version} is a stable version")
        print("Updating stable hash history...")

    modules_dict, components_count = _import_components()
    print(f"Found {components_count} components.")
    if not components_count:
        print("No components found. Exiting.")
        return

    old_history = load_hash_history(Path(history_file))
    new_history = copy.deepcopy(old_history)

    for category_name, components_dict in modules_dict.items():
        for comp_name, comp_details in components_dict.items():
            if "metadata" not in comp_details:
                print(f"Warning: Component {comp_name} in category {category_name} is missing metadata. Skipping.")
                continue

            code_hash = comp_details["metadata"].get("code_hash")

            if not code_hash:
                print(f"Warning: Component {comp_name} in category {category_name} is missing code_hash. Skipping.")
                continue

            new_history = update_history(new_history, comp_name, code_hash, current_version)

    # Validate append-only constraint before saving
    validate_append_only(old_history, new_history)

    save_hash_history(Path(history_file), new_history)
    print(f"Successfully updated {history_file}")


if __name__ == "__main__":
    main()
