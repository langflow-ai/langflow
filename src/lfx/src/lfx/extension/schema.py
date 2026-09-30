"""JSON Schema generation and export for the Extension manifest.

The published schema lives at :data:`~lfx.extension.manifest.EXTENSION_SCHEMA_URL`
(``schemas.langflow.org/extension/v1.json``).  This module is the source of
truth for what gets uploaded there.

Two consumers:

    1. ``lfx extension schema`` (CLI, this PR) -- writes the schema to disk so
       authors can reference it locally.
    2. The release pipeline -- runs :func:`build_schema_json` and uploads the
       result to the canonical URL.

We intentionally derive the schema from the Pydantic models rather than
hand-maintaining a parallel copy.  The :func:`build_schema` post-processing
step adds ``$id``, ``$schema``, and a ``title`` so the published artifact is a
well-formed JSON Schema Draft 2020-12 document.

Deferred fields (``services``, ``routes``, ``hooks``, ``starterProjects``,
``userConfig``) are stripped from the published ``properties`` map.  The
Pydantic model still carries them as ``None``-only fields so internal callers
can do ``manifest.services is None`` and ``validate.py`` can surface the
typed ``field-deferred-in-this-milestone`` discriminant; we just don't want
third-party schema consumers to render an "expected null" error when an
author writes ``services: {...}``.  With the fields absent from the schema,
Pydantic's ``additionalProperties: false`` (from ``extra="forbid"``) rejects
them with the generic "additional properties not allowed" message, and the
``x-deferred-fields`` extension documents them for tooling that wants to
surface a more helpful hint.
"""

from __future__ import annotations

import json
from typing import Any

from lfx.extension.manifest import (
    DEFERRED_FIELDS,
    EXTENSION_SCHEMA_URL,
    ExtensionManifest,
)

JSON_SCHEMA_DIALECT: str = "https://json-schema.org/draft/2020-12/schema"


def _public_deferred_names() -> list[str]:
    """Resolve :data:`DEFERRED_FIELDS` to their published-schema names.

    The Pydantic model uses Python field names internally (so callers can do
    ``manifest.services is None``); the published schema uses aliases when
    declared (e.g. ``starter_projects`` is exposed as ``starterProjects``).
    Resolving here keeps :mod:`lfx.extension.manifest` the single source of
    truth for which fields are deferred.
    """
    fields = ExtensionManifest.model_fields
    names: list[str] = []
    for name in DEFERRED_FIELDS:
        info = fields.get(name)
        if info is None:
            msg = f"DEFERRED_FIELDS lists {name!r}, but it is not on ExtensionManifest"
            raise RuntimeError(msg)
        names.append(info.alias or name)
    return names


def build_schema() -> dict[str, Any]:
    """Build the JSON Schema dict for :class:`ExtensionManifest`.

    Adds the canonical ``$id`` and ``$schema`` so the schema is publishable
    as-is.  Pydantic produces a Draft 2020-12 dialect schema by default.

    Strips deferred fields from ``properties`` and re-publishes them under
    the ``x-deferred-fields`` extension; see the module docstring for the
    rationale.
    """
    schema = ExtensionManifest.model_json_schema(
        ref_template="#/$defs/{model}",
    )
    schema["$schema"] = JSON_SCHEMA_DIALECT
    schema["$id"] = EXTENSION_SCHEMA_URL
    schema["title"] = "Langflow Extension Manifest (v1)"

    deferred_names = _public_deferred_names()
    deferred_docs: dict[str, str] = {}
    properties = schema.setdefault("properties", {})
    for name in deferred_names:
        prop = properties.pop(name, None)
        if isinstance(prop, dict):
            description = prop.get("description")
            if isinstance(description, str) and description:
                deferred_docs[name] = description
    # The extension is non-standard (``x-`` prefix per JSON Schema convention)
    # and exists so tooling that wants to render a friendlier message than
    # "additional property" can find the reserved name list and per-field
    # descriptions in one place.
    schema["x-deferred-fields"] = deferred_docs

    schema["description"] = (
        "Schema for the v0 Langflow Extension manifest. "
        "Reserved field names that are deferred to a future milestone "
        "are absent from this schema and are listed under ``x-deferred-fields``; "
        "manifests that set them are rejected via ``additionalProperties: false``. "
        "See https://docs.langflow.org/extensions-manifest for the field-by-field reference "
        "and https://docs.langflow.org/extensions-author-guide for the author's guide."
    )
    return schema


def build_schema_json(*, indent: int = 2) -> str:
    """Build the JSON Schema and return its serialized JSON form."""
    return json.dumps(build_schema(), indent=indent, sort_keys=True) + "\n"
