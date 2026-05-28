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
    - Real introspection (``build_custom_component_template``) is done
      once per file and cached by ``(path, mtime, size)``. The MCP tools
      hit the overlay many times per turn; an unchanged file is built
      once, and a genuine edit (re-registration changes mtime/size)
      invalidates the cached entry. The scaffold-graft is a fallback
      when introspection fails.
"""

from __future__ import annotations

import copy
from collections import OrderedDict
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

# Built overlay entries keyed by file path → ((mtime_ns, size), entry).
# Bounded (LRU) so many users/components can't grow it without limit.
_OVERLAY_ENTRY_CACHE: OrderedDict[str, tuple[tuple[int, int], dict]] = OrderedDict()
_OVERLAY_CACHE_MAXSIZE = 512


def _cache_overlay_entry(cache_key: str, sig: tuple[int, int], entry: dict) -> dict:
    """Store a deep copy under (key, sig) and return the entry unchanged.

    A copy is cached so a downstream consumer mutating the returned dict
    can never poison a future cache hit.
    """
    _OVERLAY_ENTRY_CACHE[cache_key] = (sig, copy.deepcopy(entry))
    _OVERLAY_ENTRY_CACHE.move_to_end(cache_key)
    if len(_OVERLAY_ENTRY_CACHE) > _OVERLAY_CACHE_MAXSIZE:
        _OVERLAY_ENTRY_CACHE.popitem(last=False)
    return entry


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
        # Tag the entry so the flow-builder emits its canvas node as
        # ``CustomComponent`` (see ``_make_node``). Without this, a node the
        # assistant builds from a user component carries the class name as its
        # type, which the frontend can't find in the global template list and
        # paints with a bogus "Update available" badge.
        entry["custom"] = True
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
    sig = (stat.st_mtime_ns, stat.st_size)
    cache_key = str(py_file)
    cached = _OVERLAY_ENTRY_CACHE.get(cache_key)
    if cached is not None and cached[0] == sig:
        _OVERLAY_ENTRY_CACHE.move_to_end(cache_key)
        return copy.deepcopy(cached[1])

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

    # PRIMARY: build the REAL template by introspecting the component —
    # exactly what the normal create-component "Add to canvas" path does
    # (Component(_code=code) + build_custom_component_template). This makes
    # the node's inputs, outputs, base_classes and output-types match the
    # actual class, so `config: A.<real_input>` works and the run calls a
    # method that exists. The scaffold-graft below is only a resilience
    # fallback. (The code is already validated+executed by Layer-2
    # generation, so instantiating it here crosses no new boundary.)
    try:
        from lfx.custom import Component
        from lfx.custom.utils import build_custom_component_template

        template_dict, _instance = build_custom_component_template(Component(_code=code))
        template_dict["display_name"] = class_name
        template_dict.setdefault("category", base_template.get("category", "custom_component"))
    except Exception as exc:  # noqa: BLE001 — one bad component must not break the overlay
        logger.debug("Real template build failed for %s; using scaffold: %s", py_file.name, exc)
    else:
        return _cache_overlay_entry(cache_key, sig, template_dict)

    # FALLBACK: graft the code onto the base CustomComponent scaffold and
    # patch outputs from the AST (no code execution) so a build that
    # couldn't introspect still calls the right method.
    entry = copy.deepcopy(base_template)
    entry["display_name"] = class_name
    code_field = entry.get("template", {}).get("code")
    if isinstance(code_field, dict):
        code_field["value"] = code
    else:
        entry.setdefault("template", {})["code"] = {"value": code}
    real_outputs = _extract_outputs_from_ast(code, class_name)
    if real_outputs:
        base_out = (entry.get("outputs") or [{}])[0]
        entry["outputs"] = [
            {**copy.deepcopy(base_out), "name": name, "method": method, "display_name": display_name or name}
            for (name, method, display_name) in real_outputs
        ]
    return _cache_overlay_entry(cache_key, sig, entry)


def _extract_outputs_from_ast(code: str, class_name: str) -> list[tuple[str, str, str | None]] | None:
    """Parse ``outputs = [Output(name=..., method=...)]`` from the class.

    Returns ``[(name, method, display_name|None), ...]`` for the target
    class, or ``None`` when it can't be determined (caller keeps the base
    scaffold). Pure AST — never imports or executes the user's code.
    """
    import ast

    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return None

    def _kw(call: ast.Call, key: str) -> str | None:
        for kw in call.keywords:
            if kw.arg == key and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return kw.value.value
        return None

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue
        for stmt in node.body:
            if not (isinstance(stmt, ast.Assign) and any(getattr(t, "id", None) == "outputs" for t in stmt.targets)):
                continue
            if not isinstance(stmt.value, ast.List):
                return None
            outputs: list[tuple[str, str, str | None]] = []
            for elt in stmt.value.elts:
                if isinstance(elt, ast.Call) and getattr(elt.func, "id", None) == "Output":
                    name = _kw(elt, "name")
                    method = _kw(elt, "method")
                    if name and method:
                        outputs.append((name, method, _kw(elt, "display_name")))
            return outputs or None
    return None


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
