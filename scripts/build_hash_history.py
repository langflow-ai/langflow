import ast
import re
import hashlib
import argparse
from lfx.interface import components
import orjson
from packaging.version import Version
import asyncio
import pkgutil
import importlib
import os
import sys
from pathlib import Path


STABLE_HISTORY_FILE = "stable_hash_history.json"
NIGHTLY_HISTORY_FILE = "nightly_hash_history.json"


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


def _import_components_direct(root_path: Path | None = None) -> dict:
    """Imports components by directly reading and parsing their source files using AST."""
    if root_path is None:
        root_path = Path("src/lfx/src/lfx/components")

    components = {}
    component_files = list(root_path.glob("**/*.py"))

    for file_path in component_files:
        if file_path.name == "__init__.py" or "deactivated" in str(file_path):
            continue

        try:
            content = file_path.read_text()
            tree = ast.parse(content)
            category = file_path.parent.name

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it's a Component subclass
                    is_component = False
                    for base in node.bases:
                        if isinstance(base, ast.Name) and "Component" in base.id:
                            is_component = True
                            break
                        elif isinstance(base, ast.Attribute) and "Component" in base.attr:
                            is_component = True
                            break
                    if not is_component:
                        # Also check for decorators
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Name) and "component" in decorator.id.lower():
                                is_component = True
                                break
                    
                    if not is_component:
                        continue
                        
                    component_id = None
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == "component_id":
                            if isinstance(item.value, ast.Constant):
                                component_id = item.value.value
                                break
                        elif isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == "component_id":
                                    if isinstance(item.value, ast.Constant):
                                        component_id = item.value.value
                                        break
                            if component_id:
                                break

                    if component_id:
                        class_source = ast.get_source_segment(content, node)
                        code_hash = hashlib.sha256(class_source.encode("utf-8")).hexdigest()
                        
                        components[component_id] = {
                            "name": node.name,
                            "category": category,
                            "code_hash": code_hash,
                        }
                    # else:
                    #     print(f"Warning: Component ID not found in {file_path} for class {node.name}")

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
    
    print(f"Discovered {len(components)} components by direct file parsing.")
    return components

def update_history(history: dict, component_name: str, component_info: dict, current_version: str) -> dict:
    """Updates the hash history for a single component."""
    current_version_parsed = Version(current_version)
    minor_version = f"{current_version_parsed.major}.{current_version_parsed.minor}"

    component_id = component_info["metadata"]["component_id"]
    code_hash = component_info["metadata"]["code_hash"]

    if component_id not in history:
        history[component_id] = {
            "name": component_name,
            "versions": {},
        }

    # Close "current" ranges in other minor versions if this is a new minor version
    for mv in history[component_id]["versions"]:
        if mv != minor_version:
            for hash_key, ranges in history[component_id]["versions"][mv].items():
                for i, version_range in enumerate(ranges):
                    if version_range[1] == "current":
                        history[component_id]["versions"][mv][hash_key][i][1] = current_version

    if minor_version not in history[component_id]["versions"]:
        history[component_id]["versions"][minor_version] = {}

    if code_hash not in history[component_id]["versions"][minor_version]:
        history[component_id]["versions"][minor_version][code_hash] = [[current_version, "current"]]
    else:
        last_range = history[component_id]["versions"][minor_version][code_hash][-1]
        if last_range[1] != "current":
            history[component_id]["versions"][minor_version][code_hash].append([current_version, "current"])

    # Close "current" ranges for other hashes of the same minor version
    for hash_key, ranges in history[component_id]["versions"][minor_version].items():
        if hash_key != code_hash:
            for i, version_range in enumerate(ranges):
                if version_range[1] == "current":
                    history[component_id]["versions"][minor_version][hash_key][i][1] = current_version

    return history


def main(argv=None):
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Build and update component hash history.")
    parser.add_argument("--nightly", action="store_true", help="Update the nightly hash history.")
    args = parser.parse_args(argv)

    if args.nightly:
        history_file = NIGHTLY_HISTORY_FILE
        print("Updating nightly hash history...")
    else:
        history_file = STABLE_HISTORY_FILE
        print("Updating stable hash history...")

    current_version = get_lfx_version()
    print(f"Current LFX version: {current_version}")

    (modules_dict, components_count) = _import_components()
    print(f"Found {components_count} components across {len(modules_dict)} categories.")


    history = load_hash_history(Path(history_file))

    for _, components_dict in modules_dict.items():
        for component_name, component_template in components_dict.items():
            component_id = component_template["metadata"]["component_id"]
            if not component_id:
                print(f"Warning: Component {component_name} has no component_id. Skipping.")
                continue

            history = update_history(history, component_name, component_template, current_version)

    save_hash_history(Path(history_file), history)
    print(f"Successfully updated {history_file}")



if __name__ == "__main__":
    main()