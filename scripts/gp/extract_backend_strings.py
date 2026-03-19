"""Extract translatable strings from Langflow component classes.

Walks the lfx.components package, reads class-level display_name/description
and field-level display_names directly from component class definitions
(no running server needed), and writes a flat GP-compatible JSON file.

Output format (flat dot-notation, same as frontend en.json):
    "components.ChatInput.display_name": "Chat Input"
    "components.ChatInput.description": "Get chat inputs from the Playground."
    "components.ChatInput.inputs.input_value.display_name": "Input Text"
    "components.ChatInput.outputs.message.display_name": "Chat Message"

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


def collect_strings() -> dict[str, str]:
    """Walk lfx.components and extract all translatable display_name strings."""
    try:
        import lfx.components as components_pkg
    except ImportError:
        print("ERROR: Could not import lfx.components. Run this script from inside the backend virtualenv.")
        sys.exit(1)

    flat: dict[str, str] = {}
    seen_names: set[str] = set()

    for _finder, modname, _ispkg in pkgutil.walk_packages(
        components_pkg.__path__, components_pkg.__name__ + "."
    ):
        if "deactivated" in modname:
            continue

        try:
            module = importlib.import_module(modname)
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP {modname}: {e}")
            continue

        for attr_name, cls in vars(module).items():
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

            # Tier 1 — component-level
            flat[f"components.{component_key}.display_name"] = display_name
            description = getattr(cls, "description", "") or ""
            if isinstance(description, str) and description:
                flat[f"components.{component_key}.description"] = description

            # Tier 2 — input field display_names
            for inp in getattr(cls, "inputs", []) or []:
                field_display = getattr(inp, "display_name", None)
                field_name = getattr(inp, "name", None)
                if isinstance(field_name, str) and isinstance(field_display, str) and field_name and field_display:
                    flat[f"components.{component_key}.inputs.{field_name}.display_name"] = field_display

            # Tier 2 — output display_names
            for out in getattr(cls, "outputs", []) or []:
                out_display = getattr(out, "display_name", None)
                out_name = getattr(out, "name", None)
                if isinstance(out_name, str) and isinstance(out_display, str) and out_name and out_display:
                    flat[f"components.{component_key}.outputs.{out_name}.display_name"] = out_display

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
    print(f"Found {len(strings)} translatable keys across {sum(1 for k in strings if k.endswith('.display_name') and '.inputs.' not in k and '.outputs.' not in k)} components.")

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
