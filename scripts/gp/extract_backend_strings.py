"""Extract translatable strings from Langflow component classes.

Walks two component sources, reads class-level display_name/description and
field-level display_names directly from component class definitions (no
running server needed), and writes a flat GP-compatible JSON file:

    1. ``lfx.components`` -- the in-tree component tree, including the
       ``# lfx-bundles-shim`` compatibility packages that re-point at an
       installed bundle distribution.
    2. **Installed extension bundles** -- every pip-installed distribution
       that ships an ``extension.json`` manifest (``src/bundles/*``, published
       as ``lfx-<provider>``).  These are loaded through the extension
       system's own ``load_installed_extensions()``, i.e. the exact call the
       palette makes in ``lfx.interface.components``, so the bundle set here
       equals the bundle set the palette shows.

Source 2 exists because a shim is not a reliable bridge.  A shim that
re-points ``sys.modules`` (``sys.modules[__name__] = import_module(...)``)
leaves the re-pointed classes carrying their *canonical* ``__module__``
(``lfx_datastax.components.cassandra.cassandra``), which does not match the
``lfx.components.…`` name the walk is iterating, so the "defined in this
module" guard below drops them.  Bundles with no shim at all (``lfx-ibm``,
``lfx-docling``, ``lfx-oracle``, ``lfx-toolguard``) were never visible.
Walking the installed distributions directly fixes both cases and means a
new bundle needs no shim to be translated -- which matters because
``scripts/ci/check_bare_names.py`` rejects new shims.

Only *installed distributions* are walked.  The palette's other sources
(``LANGFLOW_SEED_DIR``, the ``lfx.bundles`` metapackage, ``lfx extension
dev`` registrations and ``LANGFLOW_COMPONENTS_PATH``) are operator- or
developer-local: including them would make the generated catalog depend on
the machine that ran the generator, and en.json is a committed artifact.

Output format -- hybrid key: human-readable path + content-hash suffix:
    "components.chatinput.display_name.a1b2c3d4": "Chat Input"
    "components.chatinput.description.f9e8d7c6": "Get chat inputs from the Playground."
    "components.chatinput.inputs.input_value.display_name.12345678": "Input Text"
    "components.chatinput.outputs.message.display_name.abcdef01": "Chat Message"

The norm_name is the component registry key lowercased with spaces removed.
The 8-char suffix is SHA-256(english_value)[:8].  When an English string
changes, its hash changes, the old key is orphaned, and GP issues a fresh
translation for the new key on the next upload/download cycle.  Bundle
components use the identical key shape -- the key is derived from the
component's registry name and the English value only, never from the module
it was imported through -- so a component that is reachable through both
sources produces one key, not two.

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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

OUTPUT_PATH = Path(__file__).parent.parent.parent / "src/backend/base/langflow/locales/en.json"
STARTER_PROJECTS_DIR = Path(__file__).parent.parent.parent / "src/backend/base/langflow/initial_setup/starter_projects"


def emit_component_strings(
    cls: type,
    flat: dict[str, str],
    seen_names: set[str],
    *,
    component_field_key: Callable[[str, str, str], str],
    normalize_component_key: Callable[[str], str],
) -> bool:
    """Write every translatable string on *cls* into *flat*.

    Shared by both component sources so a bundle component and an in-tree
    component are keyed by exactly the same rules.  Returns ``True`` when the
    class contributed keys, ``False`` when it was skipped (not a component,
    no usable display_name, or a duplicate registry name claimed earlier).
    """
    # Component marker set by the base class
    if not getattr(cls, "code_class_base_inheritance", None):
        return False
    display_name = getattr(cls, "display_name", None)
    # Skip if not a plain string (e.g. @property descriptors on the class)
    if not isinstance(display_name, str) or not display_name:
        return False

    # Use cls.name if defined (stable identifier used in API), else class name
    component_key = getattr(cls, "name", None) or cls.__name__
    if not isinstance(component_key, str):
        component_key = cls.__name__

    if component_key in seen_names:
        return False
    seen_names.add(component_key)

    norm_key = normalize_component_key(component_key)

    # Tier 1 — component-level
    flat[component_field_key(norm_key, "display_name", display_name)] = display_name
    # If description is a @property, getattr on the class returns the descriptor
    # object (not a string).  Fall back to _base_description when that happens.
    raw_desc = cls.__dict__.get("description")
    if isinstance(raw_desc, property):
        description = getattr(cls, "_base_description", "") or ""
    else:
        description = getattr(cls, "description", "") or ""
    if isinstance(description, str) and description:
        flat[component_field_key(norm_key, "description", description)] = description

    # Tier 2 — input field display_names, info, and placeholder
    for inp in getattr(cls, "inputs", []) or []:
        field_display = getattr(inp, "display_name", None)
        field_name = getattr(inp, "name", None)
        field_info = getattr(inp, "info", None)
        field_placeholder = getattr(inp, "placeholder", None)
        if isinstance(field_name, str) and field_name:
            if isinstance(field_display, str) and field_display:
                flat[component_field_key(norm_key, f"inputs.{field_name}.display_name", field_display)] = field_display
            if isinstance(field_info, str) and field_info:
                flat[component_field_key(norm_key, f"inputs.{field_name}.info", field_info)] = field_info
            if isinstance(field_placeholder, str) and field_placeholder:
                flat[component_field_key(norm_key, f"inputs.{field_name}.placeholder", field_placeholder)] = (
                    field_placeholder
                )

    # Tier 2 — output display_names and info
    for out in getattr(cls, "outputs", []) or []:
        out_display = getattr(out, "display_name", None)
        out_name = getattr(out, "name", None)
        out_info = getattr(out, "info", None)
        if isinstance(out_name, str) and out_name:
            if isinstance(out_display, str) and out_display:
                flat[component_field_key(norm_key, f"outputs.{out_name}.display_name", out_display)] = out_display
            if isinstance(out_info, str) and out_info:
                flat[component_field_key(norm_key, f"outputs.{out_name}.info", out_info)] = out_info

    return True


def iter_installed_bundle_classes() -> Iterator[tuple[str, type]]:
    """Yield ``(bundle_name, component_class)`` for every installed extension bundle.

    Delegates discovery *and* import to ``lfx.extension.load_installed_extensions``
    -- the same call ``lfx.interface.components.import_extension_components``
    makes -- so this walk cannot drift from what the palette loads.  The loader
    already restricts each module's classes to those actually declared in it,
    so a bundle that re-exports a base class does not double-register here.

    Yield order is the loader's: lexicographic by canonical distribution name,
    then the bundle's sorted file walk.  Deterministic for a given install set.

    A missing or broken extension system is reported and skipped rather than
    raised: en.json regeneration must not become impossible because one
    distribution is in a bad state.
    """
    try:
        from lfx.extension import load_installed_extensions
    except ImportError as exc:
        print(f"  SKIP installed extension bundles (extension system unavailable): {exc}")
        return

    try:
        results = load_installed_extensions()
    except Exception as exc:  # noqa: BLE001 - one bad distribution must not abort the extraction
        print(f"  SKIP installed extension bundles (load failed): {exc}")
        return

    for result in results:
        for error in getattr(result, "errors", []) or []:
            print(f"  SKIP {getattr(result, 'distribution', '?')}: {getattr(error, 'message', error)}")
        for component in getattr(result, "components", []) or []:
            klass = getattr(component, "klass", None)
            if not isinstance(klass, type):
                continue
            bundle = getattr(component, "bundle", None) or getattr(result, "extension_id", "") or "?"
            yield bundle, klass


def collect_strings() -> dict[str, str]:
    """Walk lfx.components + installed bundles and extract translatable strings."""
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
            emit_component_strings(
                cls,
                flat,
                seen_names,
                component_field_key=_component_field_key,
                normalize_component_key=_normalize_component_key,
            )

    # Installed extension bundles (src/bundles/* published as lfx-<provider>).
    # Runs after the in-tree walk so a component reachable through both a
    # compatibility shim and its bundle is claimed once; the two paths produce
    # identical keys, so which one wins does not affect the output.
    bundle_component_count = 0
    bundle_names: set[str] = set()
    for bundle_name, klass in iter_installed_bundle_classes():
        bundle_names.add(bundle_name)
        if emit_component_strings(
            klass,
            flat,
            seen_names,
            component_field_key=_component_field_key,
            normalize_component_key=_normalize_component_key,
        ):
            bundle_component_count += 1

    print(f"Found {bundle_component_count} component(s) across {len(bundle_names)} installed extension bundle(s).")

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

    print("Scanning lfx.components and installed extension bundles for translatable strings...")
    strings = collect_strings()
    print(
        f"Found {len(strings)} translatable keys across "
        f"{sum(1 for k in strings if '.display_name.' in k and '.inputs.' not in k and '.outputs.' not in k)}"
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
