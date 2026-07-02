"""Schema-hardening wrapper around composio_langchain.LangchainProvider.

Composio's runtime file-substitution helpers (composio.core.models._files) and
its Pydantic schema builder (composio.utils.shared.pydantic_model_from_param_schema)
raw-subscript ``properties[name]["type"]``. When a Composio tool's
``input_parameters`` schema contains a property without an explicit ``"type"``
(common for Gmail/Calendar actions whose properties only specify
``anyOf``/``additionalProperties``), tool execution raises
``KeyError: 'type'`` (issues #12894, #12895).

We sanitize ``tool.input_parameters`` in-place at wrap time, and also patch
both the FileHelper file-substitution helpers and the pydantic schema builder
so the agent path, the direct ``execute_action`` path, and the legacy
``tools.get`` path all see a schema with a ``"type"`` for every node.
"""

from __future__ import annotations

import keyword
from typing import TYPE_CHECKING, Any

try:
    import composio_langchain.provider as _composio_lc_provider
    from composio.core.models import _files as _composio_files
    from composio.core.models._files import FileHelper
    from composio.utils import shared as _composio_shared
    from composio_langchain import LangchainProvider
except ImportError:  # composio extra not installed; module becomes a no-op
    _composio_files = None  # type: ignore[assignment]
    _composio_shared = None  # type: ignore[assignment]
    _composio_lc_provider = None  # type: ignore[assignment]
    FileHelper = None  # type: ignore[assignment]
    LangchainProvider = None  # type: ignore[assignment,misc]
    _COMPOSIO_AVAILABLE = False
else:
    _COMPOSIO_AVAILABLE = True
    # composio_langchain hardcodes only {"for", "async"} as reserved Python
    # keywords. Any action whose schema contains a field named after another
    # keyword (e.g. Outlook's "from") hits inspect.Parameter's validation and
    # raises ValueError. Expand the set to the full Python keyword list once at
    # import time so _substitute_reserved_python_keywords handles all of them.
    _composio_lc_provider._python_reserved = set(keyword.kwlist)  # noqa: SLF001

if TYPE_CHECKING:
    from collections.abc import Callable

    from composio.types import Tool
    from composio_langchain.provider import StructuredTool


def _sanitize_schema(schema: Any) -> None:
    """Recursively guarantee every JSON-schema node has a ``type`` key.

    Composio's runtime walkers raw-subscript ``properties[name]["type"]`` (see
    ``composio.core.models._files`` lines 235/308 and
    ``composio.utils.shared.pydantic_model_from_param_schema`` line 232). They
    don't resolve ``$ref``/``anyOf``/``oneOf``/``allOf`` before that lookup, so
    *any* property without a literal ``"type"`` key crashes with
    ``KeyError('type')`` even if a union arm or referenced ``$def`` would have
    provided one.

    We mutate ``schema`` in place with these inference rules:
      - has ``properties`` -> ``type`` defaults to ``"object"``
      - has ``items``      -> ``type`` defaults to ``"array"``
      - otherwise          -> ``type`` defaults to ``"string"``

    Existing ``type`` keys are never overwritten. The string default is
    deliberately conservative: composio compares ``type == "object"`` to decide
    whether to recurse into a nested file-substitution walk, so defaulting to
    ``"string"`` is a safe no-op for that branch.
    """
    if not isinstance(schema, dict):
        return

    has_type = "type" in schema
    has_props = "properties" in schema
    has_items = "items" in schema

    if not has_type:
        if has_props:
            schema["type"] = "object"
        elif has_items:
            schema["type"] = "array"
        else:
            schema["type"] = "string"

    if has_props:
        for sub in schema["properties"].values():
            _sanitize_schema(sub)
    if has_items:
        _sanitize_schema(schema["items"])
    for union_key in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(union_key, []) or []:
            _sanitize_schema(sub)
    for defs_key in ("$defs", "definitions"):
        defs = schema.get(defs_key)
        if isinstance(defs, dict):
            for sub in defs.values():
                _sanitize_schema(sub)


if _COMPOSIO_AVAILABLE:

    class SafeLangchainProvider(LangchainProvider, name="langchain"):
        """LangchainProvider that patches tool schemas before delegating."""

        def wrap_tool(self, tool: Tool, execute_tool: Callable[..., Any]) -> StructuredTool:
            _sanitize_schema(tool.input_parameters)
            return super().wrap_tool(tool=tool, execute_tool=execute_tool)


def _extract_schema_arg(args: tuple, kwargs: dict, positional_index: int, keyword: str) -> Any:
    """Pull a schema-shaped argument out of ``*args``/``**kwargs`` for sanitization.

    Wrappers accept ``*args, **kwargs`` so they tolerate either calling
    convention (Composio currently uses keywords, but a future release could
    switch to positionals). We only need to *find* the schema dict — the
    underlying call is forwarded verbatim, so we never need to rewrite the
    arguments.
    """
    if keyword in kwargs:
        return kwargs[keyword]
    if len(args) > positional_index:
        return args[positional_index]
    return None


def _patch_file_helper_once() -> None:
    """Wrap Composio's file substitution helpers so untyped properties don't KeyError.

    ``_substitute_file_uploads_recursively`` and ``_substitute_file_downloads_recursively``
    raw-subscript ``params[name]["type"]`` while walking ``tool.input_parameters``. The
    methods run on every ``composio.tools.execute`` call (including direct component
    runs that don't go through ``configure_tools``), so we patch them here once at
    import time.

    Side effects: this mutates ``composio.core.models._files.FileHelper`` for the
    entire Python process. Any other consumer that imports Composio in the same
    runtime (Astra integrations, plugin bundles, scripts) will see the patched
    methods. Intentional — the upstream raw subscript is a bug, and the wrapper
    only inserts missing ``"type"`` keys before delegating to the original
    helpers, so it is a strict superset of the original behavior. Idempotent via
    the ``_lfx_safe_patched`` sentinel; safe across repeated imports / pytest
    process reuse.
    """
    if not _COMPOSIO_AVAILABLE or getattr(FileHelper, "_lfx_safe_patched", False):
        return

    original_uploads = FileHelper._substitute_file_uploads_recursively  # noqa: SLF001
    original_downloads = FileHelper._substitute_file_downloads_recursively  # noqa: SLF001

    # ``*args, **kwargs`` keeps the wrapper signature tolerant of either
    # positional or keyword invocation. Upstream Composio currently uses
    # keywords (composio/core/models/_files.py:236-240, :309-312), but pinning
    # the wrapper to a stricter signature would silently break if a future
    # release switches to positionals.
    def safe_uploads(self, *args, **kwargs):
        _sanitize_schema(_extract_schema_arg(args, kwargs, positional_index=1, keyword="schema"))
        return original_uploads(self, *args, **kwargs)

    def safe_downloads(self, *args, **kwargs):
        _sanitize_schema(_extract_schema_arg(args, kwargs, positional_index=1, keyword="schema"))
        return original_downloads(self, *args, **kwargs)

    FileHelper._substitute_file_uploads_recursively = safe_uploads  # noqa: SLF001
    FileHelper._substitute_file_downloads_recursively = safe_downloads  # noqa: SLF001
    FileHelper._lfx_safe_patched = True  # noqa: SLF001


def _patch_pydantic_builder_once() -> None:
    """Wrap ``composio.utils.shared.pydantic_model_from_param_schema`` so untyped properties don't KeyError.

    The builder raw-subscripts ``prop_info["type"]`` while iterating
    ``properties`` (composio/utils/shared.py:232 in 0.9.2). It runs during
    ``tools.get`` for the legacy direct-execute path that bypasses
    ``configure_tools``'s cached-schema sanitizer, so the FileHelper patch
    alone is not sufficient. Sanitizing the schema before delegation injects a
    default ``"type"`` for every node and is a no-op for already-typed
    schemas. Recursive calls inside the builder go through the module-level
    name we just rebound, so they're sanitized (idempotently) too.

    Idempotent via the ``_lfx_safe_patched`` sentinel on the module.
    """
    if not _COMPOSIO_AVAILABLE or getattr(_composio_shared, "_lfx_safe_patched", False):
        return

    original_builder = _composio_shared.pydantic_model_from_param_schema

    def safe_builder(*args, **kwargs):
        _sanitize_schema(_extract_schema_arg(args, kwargs, positional_index=0, keyword="param_schema"))
        return original_builder(*args, **kwargs)

    _composio_shared.pydantic_model_from_param_schema = safe_builder
    _composio_shared._lfx_safe_patched = True  # noqa: SLF001


def _patch_identifier_substitution_once() -> None:
    """Extend composio_langchain's keyword substitution to cover all invalid Python identifiers.

    composio_langchain.substitute_reserved_python_keywords only renames schema
    properties that are in its hardcoded _python_reserved set. Property names
    like 'extension-id' (hyphen) are valid JSON Schema names but not valid
    Python identifiers, causing inspect.Parameter to raise ValueError when the
    tool signature is built.

    We wrap substitute_reserved_python_keywords so that after it runs, any
    remaining property whose name is not a valid Python identifier is also
    renamed (invalid chars replaced with underscores) and registered in the
    keywords dict. This ensures _reinstate_reserved_python_keywords maps the
    cleaned name back to the original when the action is executed.

    Idempotent via the _lfx_identifier_patched sentinel.
    """
    if not _COMPOSIO_AVAILABLE or getattr(_composio_lc_provider, "_lfx_identifier_patched", False):
        return

    import re as _re

    _invalid_char_re = _re.compile(r"[^a-zA-Z0-9_]")
    # composio-langchain>=0.16.0 made this function public (dropped leading underscore)
    _fn_name = (
        "substitute_reserved_python_keywords"
        if hasattr(_composio_lc_provider, "substitute_reserved_python_keywords")
        else "_substitute_reserved_python_keywords"
    )
    original_substitute = getattr(_composio_lc_provider, _fn_name)

    def safe_substitute(schema: dict) -> tuple:
        schema, keywords = original_substitute(schema)
        if "properties" not in schema:
            return schema, keywords
        for p_name in list(schema["properties"]):
            if p_name.isidentifier():
                continue
            clean_name = _invalid_char_re.sub("_", p_name)
            if clean_name and clean_name[0].isdigit():
                clean_name = f"_{clean_name}"
            while clean_name in schema["properties"]:
                clean_name = f"{clean_name}_"
            schema["properties"][clean_name] = schema["properties"].pop(p_name)
            keywords[clean_name] = p_name
        return schema, keywords

    setattr(_composio_lc_provider, _fn_name, safe_substitute)
    _composio_lc_provider._lfx_identifier_patched = True  # noqa: SLF001


_patch_file_helper_once()
_patch_pydantic_builder_once()
_patch_identifier_substitution_once()
