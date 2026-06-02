"""Extract translatable strings from Langflow component classes.

Walks the lfx.components package, reads class-level display_name/description
and field-level display_names directly from component class definitions
(no running server needed), and writes a flat GP-compatible JSON file.

Output format — hybrid key: human-readable path + content-hash suffix:
    "components.chatinput.display_name.a1b2c3d4": "Chat Input"
    "components.chatinput.description.f9e8d7c6": "Get chat inputs from the Playground."
    "components.chatinput.inputs.input_value.display_name.12345678": "Input Text"
    "components.chatinput.outputs.message.display_name.abcdef01": "Chat Message"

The norm_name is the component registry key lowercased with spaces removed.
The 8-char suffix is SHA-256(english_value)[:8].  When an English string
changes, its hash changes, the old key is orphaned, and GP issues a fresh
translation for the new key on the next upload/download cycle.

Usage:
    # From repo root with the backend virtualenv active:
    python scripts/gp/extract_backend_strings.py

    # Check only (exit 1 if en.json would change — use in CI):
    python scripts/gp/extract_backend_strings.py --check
"""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent.parent / "src/backend/base/langflow/locales/en.json"
STARTER_PROJECTS_DIR = Path(__file__).parent.parent.parent / "src/backend/base/langflow/initial_setup/starter_projects"


def collect_strings() -> dict[str, str]:
    """Walk lfx.components and extract all translatable display_name strings."""
    from langflow.utils.i18n_keys import component_field_key as _component_field_key
    from langflow.utils.i18n_keys import normalize_component_key as _normalize_component_key
    from langflow.utils.i18n_keys import safe_flow_key as _safe_key

    try:
        import lfx.components as components_pkg
    except ImportError:
        print("ERROR: Could not import lfx.components. Run this script from inside the backend virtualenv.")
        sys.exit(1)

    flat: dict[str, str] = {}
    seen_names: set[str] = set()

    for _finder, modname, _ispkg in pkgutil.walk_packages(components_pkg.__path__, components_pkg.__name__ + "."):
        if "deactivated" in modname:
            continue

        try:
            module = importlib.import_module(modname)
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP {modname}: {e}")
            continue

        for cls in vars(module).values():
            if not isinstance(cls, type):
                continue
            # Only process classes defined in this module (avoid re-processing imports)
            if getattr(cls, "__module__", None) != modname:
                continue
            # Component marker set by the base class
            if not getattr(cls, "code_class_base_inheritance", None):
                continue
            display_name = getattr(cls, "display_name", None)
            # Skip if not a plain string (e.g. @property descriptors on the class)
            if not isinstance(display_name, str) or not display_name:
                continue

            # Use cls.name if defined (stable identifier used in API), else class name
            component_key = getattr(cls, "name", None) or cls.__name__
            if not isinstance(component_key, str):
                component_key = cls.__name__

            if component_key in seen_names:
                continue
            seen_names.add(component_key)

            norm_key = _normalize_component_key(component_key)

            # Tier 1 — component-level
            flat[_component_field_key(norm_key, "display_name", display_name)] = display_name
            # If description is a @property, getattr on the class returns the descriptor
            # object (not a string).  Fall back to _base_description when that happens.
            raw_desc = cls.__dict__.get("description")
            if isinstance(raw_desc, property):
                description = getattr(cls, "_base_description", "") or ""
            else:
                description = getattr(cls, "description", "") or ""
            if isinstance(description, str) and description:
                flat[_component_field_key(norm_key, "description", description)] = description

            # Tier 2 — input field display_names, info, and placeholder
            for inp in getattr(cls, "inputs", []) or []:
                field_display = getattr(inp, "display_name", None)
                field_name = getattr(inp, "name", None)
                field_info = getattr(inp, "info", None)
                field_placeholder = getattr(inp, "placeholder", None)
                if isinstance(field_name, str) and field_name:
                    if isinstance(field_display, str) and field_display:
                        flat[_component_field_key(norm_key, f"inputs.{field_name}.display_name", field_display)] = (
                            field_display
                        )
                    if isinstance(field_info, str) and field_info:
                        flat[_component_field_key(norm_key, f"inputs.{field_name}.info", field_info)] = field_info
                    if isinstance(field_placeholder, str) and field_placeholder:
                        flat[_component_field_key(norm_key, f"inputs.{field_name}.placeholder", field_placeholder)] = (
                            field_placeholder
                        )

            # Tier 2 — output display_names and info
            for out in getattr(cls, "outputs", []) or []:
                out_display = getattr(out, "display_name", None)
                out_name = getattr(out, "name", None)
                out_info = getattr(out, "info", None)
                if isinstance(out_name, str) and out_name:
                    if isinstance(out_display, str) and out_display:
                        flat[_component_field_key(norm_key, f"outputs.{out_name}.display_name", out_display)] = (
                            out_display
                        )
                    if isinstance(out_info, str) and out_info:
                        flat[_component_field_key(norm_key, f"outputs.{out_name}.info", out_info)] = out_info

    # Tier 3 — starter project names & descriptions (auto-discovered from JSON files)
    starter_count = 0
    for project_file in sorted(STARTER_PROJECTS_DIR.glob("*.json")):
        try:
            with project_file.open(encoding="utf-8") as f:
                project = json.load(f)
        except Exception:  # noqa: BLE001, S112
            continue
        name = project.get("name")
        description = project.get("description", "")
        if name and isinstance(name, str):
            key = _safe_key(name)
            flat[f"starter_flows.{key}.name"] = name
            starter_count += 1
            if description and isinstance(description, str):
                flat[f"starter_flows.{key}.description"] = description

    print(f"Found {starter_count} starter project(s) in {STARTER_PROJECTS_DIR.name}/")

    # Tier 4 — note node descriptions in starter projects (keys baked by bake_note_keys.py)
    note_count = 0
    missing_keys: list[str] = []
    for project_file in sorted(STARTER_PROJECTS_DIR.glob("*.json")):
        try:
            with project_file.open(encoding="utf-8") as f:
                project = json.load(f)
        except Exception:  # noqa: BLE001, S112
            continue
        nodes = project.get("data", {}).get("nodes", [])
        for node in nodes:
            if node.get("type") != "noteNode":
                continue
            node_data = node.get("data", {}).get("node", {})
            i18n_key = node_data.get("i18n_key")
            description = node_data.get("description", "")
            if not i18n_key:
                missing_keys.append(project_file.name)
                continue
            if description and isinstance(description, str):
                flat[i18n_key] = description
                note_count += 1

    if missing_keys:
        print(
            f"WARNING: {len(missing_keys)} noteNode(s) are missing i18n_key. "
            "Run scripts/gp/bake_note_keys.py to assign keys."
        )
    print(f"Found {note_count} note node(s) across starter projects.")

    # Shared tool-mode output — injected dynamically on every component when tool_mode is
    # enabled, so it's never part of any component's static output list.  Uses the sentinel
    # norm "_toolmode" so the runtime translator can look it up with a single shared key.
    # Constants are inlined (not imported from lfx.base) so this script can run without
    # the full lfx package installed, matching the pattern used in bake_note_keys.py.
    _tool_output_name = "component_as_tool"
    _tool_output_display_name = "Toolset"
    flat[_component_field_key("_toolmode", f"outputs.{_tool_output_name}.display_name", _tool_output_display_name)] = (
        _tool_output_display_name
    )

    return dict(sorted(flat.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract backend component strings to locales/en.json")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Diff mode: exit 1 if en.json would change (use in CI)",
    )
    args = parser.parse_args()

    print("Scanning lfx.components for translatable strings...")
    strings = collect_strings()
    print(
        f"Found {len(strings)} translatable keys across "
        f"{sum(1 for k in strings if k.endswith('.display_name') and '.inputs.' not in k and '.outputs.' not in k)}"
        " components."
    )

    new_content = json.dumps(strings, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        if OUTPUT_PATH.exists():
            existing = OUTPUT_PATH.read_text(encoding="utf-8")
            if existing == new_content:
                print("OK: locales/en.json is up to date.")
                sys.exit(0)
            else:
                print("FAIL: locales/en.json is out of sync. Run extract_backend_strings.py to update it.")
                sys.exit(1)
        else:
            print("FAIL: locales/en.json does not exist. Run extract_backend_strings.py to create it.")
            sys.exit(1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(new_content, encoding="utf-8")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
