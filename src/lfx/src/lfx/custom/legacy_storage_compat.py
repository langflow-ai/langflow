"""Recognize shipped saved source before evaluating removed-provider imports.

Flows persist Python source, not merely a component ID. Only an exact semantic
fingerprint from our shipped-source inventory may resolve to the current class.
Custom edits are never rewritten on the basis of a matching class name. The
saved flow definition is untouched so its original source remains recoverable.
"""

from __future__ import annotations

import ast
import hashlib
import json
from functools import lru_cache
from importlib import import_module
from importlib.resources import files


@lru_cache(maxsize=256)
def source_fingerprint(code: str) -> str:
    """Hash Python semantics, independent of comments, layout and AST positions."""

    def canonical(node):
        """Normalize syntax recursively for trusted legacy-source compatibility checks."""
        if isinstance(node, ast.AST):
            return [
                type(node).__name__,
                {
                    key: canonical(value)
                    for key, value in ast.iter_fields(node)
                    # Python 3.12 added this empty field to class/function nodes.
                    # Nonempty type parameters remain part of the fingerprint.
                    if not (key == "type_params" and not value)
                },
            ]
        if isinstance(node, list):
            return [canonical(item) for item in node]
        if isinstance(node, (bytes, complex)) or node is Ellipsis:
            return {"literal_type": type(node).__name__, "value": repr(node)}
        return node

    tree = ast.parse(code)
    payload = json.dumps(canonical(tree), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


@lru_cache(maxsize=1)
def _known_sources() -> dict[str, tuple[str, str]]:
    """Cache recognized shipped sources for safe resolution to current retired-component classes."""
    path = files("lfx").joinpath("_assets", "legacy_storage_sources.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["sha256"]: (entry["module"], entry["class_name"]) for entry in data["entries"]}


def resolve_shipped_storage_component(code: str):
    """Return an updated class only for inventoried shipped component source."""
    # Keep unrelated custom components on their existing evaluation path.
    if not any(
        name in code
        for name in (
            "KnowledgeComponent",
            "KnowledgeIngestionComponent",
            "KnowledgeBaseComponent",
            "KnowledgeRetrievalComponent",
            "MemoryRetrievalComponent",
            "MemoryBaseComponent",
            "ChromaVectorStoreComponent",
            "LocalDBComponent",
            "ALTKAgentComponent",
        )
    ):
        return None
    try:
        identity = _known_sources().get(source_fingerprint(code))
    except (SyntaxError, ValueError, RecursionError, OSError, KeyError, TypeError):
        return None
    if identity is None:
        return None
    module, class_name = identity
    return getattr(import_module(module), class_name)
