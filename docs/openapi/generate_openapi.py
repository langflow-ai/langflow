#!/usr/bin/env python3
"""Generate the Langflow OpenAPI specification.

This script imports the Langflow FastAPI application and writes its OpenAPI
schema to a JSON file in this directory.

Usage (from repository root):

    uv run python docs/openapi/generate_openapi.py
    uv run python docs/openapi/generate_openapi.py --output openapi-1.5.0.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from langflow.main import create_app


def _clean_descriptions(spec: dict[str, Any]) -> None:
    """Convert newlines in operation descriptions to <br> for better ReDoc rendering."""
    paths = spec.get("paths") or {}
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            description = operation.get("description")
            if isinstance(description, str) and description:
                operation["description"] = description.replace("\n", "<br>")


def _collect_and_rewrite_defs(node: Any, collected: dict[str, Any]) -> None:
    """Hoist JSON Schema `$defs` into `components.schemas` and rewrite refs.

    Some tooling (like Redoc's sampler) cannot handle JSON Pointer segments
    that contain `$defs`. To keep the schema tool-friendly, we:
    - Collect any `$defs` blocks we find anywhere in the tree.
    - Remove those local `$defs` blocks.
    - Rewrite `"$ref": "#/$defs/Name"` to `"#/components/schemas/Name"`.
    """
    if isinstance(node, dict):
        # Hoist local $defs
        if "$defs" in node and isinstance(node["$defs"], dict):
            for name, schema in node["$defs"].items():
                # Only add if not already present; avoid clobbering explicit components
                collected.setdefault(name, schema)
            node.pop("$defs", None)

        # Rewrite local refs
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.split("/")[-1]
            node["$ref"] = f"#/components/schemas/{name}"

        # Recurse into values
        for value in node.values():
            _collect_and_rewrite_defs(value, collected)

    elif isinstance(node, list):
        for item in node:
            _collect_and_rewrite_defs(item, collected)


def _normalize_defs(spec: dict[str, Any]) -> None:
    """Normalize `$defs` usage for better compatibility with tooling."""
    collected: dict[str, Any] = {}
    _collect_and_rewrite_defs(spec, collected)

    if not collected:
        return

    components = spec.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for name, schema in collected.items():
        schemas.setdefault(name, schema)


def generate_openapi(output_path: Path) -> None:
    """Generate the OpenAPI spec and write it to ``output_path``."""
    app = create_app()
    spec = app.openapi()

    _clean_descriptions(spec)
    _normalize_defs(spec)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, sort_keys=True, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Langflow OpenAPI specification.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent / "openapi.json",
        help="Output file path (default: docs/openapi/openapi.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_openapi(args.output)


if __name__ == "__main__":
    main()
