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
"""

from __future__ import annotations

import json
from typing import Any

from lfx.extension.manifest import EXTENSION_SCHEMA_URL, ExtensionManifest

JSON_SCHEMA_DIALECT: str = "https://json-schema.org/draft/2020-12/schema"


def build_schema() -> dict[str, Any]:
    """Build the JSON Schema dict for :class:`ExtensionManifest`.

    Adds the canonical ``$id`` and ``$schema`` so the schema is publishable
    as-is.  Pydantic produces a Draft 2020-12 dialect schema by default.
    """
    schema = ExtensionManifest.model_json_schema(
        ref_template="#/$defs/{model}",
    )
    schema["$schema"] = JSON_SCHEMA_DIALECT
    schema["$id"] = EXTENSION_SCHEMA_URL
    schema["title"] = "Langflow Extension Manifest (v1)"
    schema["description"] = (
        "Schema for the v0 Langflow Extension manifest (LE-1014). "
        "See https://docs.langflow.org/extensions/manifest for the author's guide."
    )
    return schema


def build_schema_json(*, indent: int = 2) -> str:
    """Build the JSON Schema and return its serialized JSON form."""
    return json.dumps(build_schema(), indent=indent, sort_keys=True) + "\n"
