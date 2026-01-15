import argparse
import asyncio
from pathlib import Path

import orjson
from packaging.version import Version

STABLE_HISTORY_FILE = "src/lfx/src/lfx/_assets/stable_hash_history.json"
NIGHTLY_HISTORY_FILE = "src/lfx/src/lfx/_assets/nightly_hash_history.json"


def get_lfx_version():
    """Get the installed lfx version."""
    from importlib.metadata import version

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
    version_key = f"{current_version_parsed.major}.{current_version_parsed.minor}.{current_version_parsed.micro}"

    if component_name not in history:
        print(f"Component {component_name} not found in history. Adding...")
        print(f"WARNING - Ensure that Component {component_name} is a NEW Component. If not, this is an error and will lose hash history for this component.")
        history[component_name] = {}
        history[component_name]["versions"] = {version_key: code_hash}
    else:
        # Ensure that we aren't ovewriting a previous version
        for v in history[component_name]["versions"]:
            parsed_version = Version(v)
            if parsed_version > current_version_parsed:
                # If this happens, we are overwriting a previous version.
                msg = f"ERROR - Component {component_name} already has a version {v} that is greater than the current version {current_version}."
                raise ValueError(msg)
        history[component_name]["versions"][version_key] = code_hash

    return history


def main(argv=None):
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Build and update component hash history.")
    parser.add_argument("--nightly", action="store_true", help="Update the nightly hash history.")
    args = parser.parse_args(argv)

    current_version = get_lfx_version()
    print(f"Current LFX version: {current_version}")

    if args.nightly:
        if "dev" not in str(current_version):
            raise ValueError("Cannot update nightly hash history for a non-dev version.")
        history_file = NIGHTLY_HISTORY_FILE
        print("Updating nightly hash history...")
    else:
        if "dev" in str(current_version):
            raise ValueError("Cannot update stable hash history for a dev version.")
        history_file = STABLE_HISTORY_FILE
        print("Updating stable hash history...")

    modules_dict, components_count = _import_components()
    print(f"Found {components_count} components.")
    if not components_count:
        print("No components found. Exiting.")
        return

    history = load_hash_history(Path(history_file))

    for category_name, components_dict in modules_dict.items():
        for comp_name, comp_details in components_dict.items():
            if "metadata" not in comp_details:
                print(f"Warning: Component {comp_name} in category {category_name} is missing metadata. Skipping.")
                continue

            code_hash = comp_details["metadata"].get("code_hash")

            if not code_hash:
                print(f"Warning: Component {comp_name} in category {category_name} is missing code_hash. Skipping.")
                continue

            history = update_history(history, comp_name, code_hash, current_version)

    save_hash_history(Path(history_file), history)
    print(f"Successfully updated {history_file}")


if __name__ == "__main__":
    main()
