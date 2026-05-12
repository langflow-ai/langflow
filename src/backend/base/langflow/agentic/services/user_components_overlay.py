"""Registry overlay that merges base components with user-registered code.

The base ``load_local_registry()`` from ``lfx.graph.flow_builder.builder``
ships a static set of component types compiled into the package. When a
user generates a Component via the Assistant (and it passes Layer-2
validation), it lands in ``<sandbox>/.components/<ClassName>.py`` via
``register_user_component()``.

This overlay walks that directory at lookup time and produces additional
registry entries so ``BuildFlowFromSpec`` / ``SearchComponentTypes`` /
``DescribeComponentType`` / ``AddComponent`` see the user's types as
first-class options.

Design constraints:
    - Same shape as the base registry: ``{type_name: template_dict}``.
    - User-named collisions with the base registry are dropped (base
      wins). Otherwise a user could shadow ``ChatInput`` and surprise
      the agent on subsequent runs.
    - Files that fail to load are silently skipped — one bad component
      must not break the overlay for the rest.
    - No template introspection at overlay time: we reuse the base
      ``CustomComponent`` template (which carries a ``code`` field) and
      graft the user's source into it. The agent and the canvas treat
      the resulting node as a CustomComponent, with the user's code
      already embedded. This avoids running ``build_custom_component_template``
      on every overlay call — heavy and would import user code into the
      assistant process.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from lfx.graph.flow_builder.builder import load_local_registry

if TYPE_CHECKING:
    from pathlib import Path
from lfx.log.logger import logger

from langflow.agentic.services.user_components import (
    MAX_COMPONENT_SOURCE_BYTES,
    get_user_components_dir,
)
from langflow.agentic.services.user_components_context import current_user_id

# The base template every user component is grafted onto. We resolve it
# from the base registry at module import (it's cached there anyway) and
# fall back to ``None`` if the platform's CustomComponent entry was
# stripped from the build — overlay degrades to no-op rather than crash.
_BASE_CUSTOM_TEMPLATE_KEY = "CustomComponent"


def load_registry_with_user_overlay(*, user_id: str | None) -> dict[str, dict]:
    """Return the base registry merged with the user's overlay.

    Always returns the base registry. Adds entries for each
    ``<ClassName>.py`` file under the user's ``.components/`` directory,
    using the base ``CustomComponent`` template as the scaffold and
    grafting the user's source code into the ``code`` field.

    Skips silently when:
        - ``user_id`` is ``None`` (no namespace to look up).
        - The user's components directory does not exist or is empty.
        - The platform's base ``CustomComponent`` template is missing.
        - A specific user file is unreadable, oversized, or empty.
    Collisions with base type names are dropped (base wins).
    """
    base_registry = load_local_registry()

    if user_id is None:
        return base_registry

    base_template = base_registry.get(_BASE_CUSTOM_TEMPLATE_KEY)
    if base_template is None:
        logger.debug("Base CustomComponent template missing; overlay disabled")
        return base_registry

    components_dir = get_user_components_dir(user_id=user_id)
    if components_dir is None or not components_dir.exists():
        return base_registry

    overlay: dict[str, dict] = {}
    for py_file in sorted(components_dir.glob("*.py")):
        entry = _build_overlay_entry(py_file, base_template)
        if entry is None:
            continue
        class_name = py_file.stem
        if class_name in base_registry:
            logger.warning(
                "User component %s collides with base registry; ignored",
                class_name,
            )
            continue
        overlay[class_name] = entry

    if not overlay:
        return base_registry

    # Merge without mutating the cached base registry. Shallow copy of
    # the top dict is enough — the consumer only adds keys; the per-type
    # template dicts are not mutated by downstream code paths.
    merged = dict(base_registry)
    merged.update(overlay)
    return merged


def load_registry_for_current_user() -> dict[str, dict]:
    """Convenience wrapper that reads ``user_id`` from the ContextVar.

    Used by the MCP tools so they don't have to plumb ``user_id``
    through their argument schemas. Returns the base registry merged
    with whatever overlay applies to the currently-bound user (or just
    the base registry if no user is bound).
    """
    return load_registry_with_user_overlay(user_id=current_user_id())


def _build_overlay_entry(py_file: Path, base_template: dict) -> dict | None:
    """Produce one overlay registry entry from a user file.

    Returns ``None`` to skip a file silently (so a broken component
    doesn't take down the overlay for the user's other components).
    """
    try:
        stat = py_file.stat()
    except OSError as exc:
        logger.debug("Skipping %s: stat failed: %s", py_file.name, exc)
        return None
    if stat.st_size > MAX_COMPONENT_SOURCE_BYTES:
        logger.warning(
            "Skipping %s: size %d exceeds %d",
            py_file.name,
            stat.st_size,
            MAX_COMPONENT_SOURCE_BYTES,
        )
        return None
    try:
        code = py_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.debug("Skipping %s: read failed: %s", py_file.name, exc)
        return None
    if not code.strip():
        return None

    class_name = py_file.stem

    # Defense in depth: even though register_user_component validates
    # the class name when WRITING, the overlay also rejects anything
    # that doesn't look like a clean identifier at READ time. Files
    # planted via some other path (manual filesystem access, future
    # bug, etc.) are skipped.
    if not _is_safe_overlay_name(class_name):
        logger.warning("Skipping %s: unsafe overlay name", py_file.name)
        return None

    # Optionally validate that the file at least parses as Python. Drop
    # syntax-broken files rather than letting downstream consumers crash.
    if not _is_parseable_python(code):
        logger.debug("Skipping %s: not parseable Python", py_file.name)
        return None

    entry = copy.deepcopy(base_template)
    entry["display_name"] = class_name
    # The template's "code" field is a dict wrapper {"value": str, ...}
    # in the live registry. Mutate the value in place rather than
    # rebuilding the wrapper (preserves other fields like "show",
    # "advanced", "field_type", etc. that the canvas relies on).
    code_field = entry.get("template", {}).get("code")
    if isinstance(code_field, dict):
        code_field["value"] = code
    else:
        # Shouldn't happen with the current CustomComponent template,
        # but stay resilient if the platform ever flattens the field.
        entry.setdefault("template", {})["code"] = {"value": code}
    return entry


def _is_safe_overlay_name(name: str) -> bool:
    """Mirror the write-time class-name regex without re-importing it.

    Kept inline so the overlay module has no dependency on the writer's
    private constants (the contract is the on-disk filename shape).
    """
    if not name:
        return False
    if not name[0].isupper():
        return False
    return all(ch.isalnum() or ch == "_" for ch in name)


def _is_parseable_python(code: str) -> bool:
    import ast

    try:
        ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    return True
