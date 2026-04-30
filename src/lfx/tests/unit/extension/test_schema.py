"""JSON Schema export tests (LE-1014).

Acceptance criterion: published JSON Schema validates the v0 example and
rejects at least 10 malformed manifests with distinct error paths.
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema
import pytest
from lfx.extension.manifest import EXTENSION_SCHEMA_URL
from lfx.extension.schema import build_schema, build_schema_json

_VALID = {
    "$schema": EXTENSION_SCHEMA_URL,
    "id": "lfx-openai",
    "version": "1.2.3",
    "name": "OpenAI Bundle",
    "lfx": {"bundle_api": [1]},
    "bundles": [{"name": "openai", "path": "openai"}],
}


def _validator() -> jsonschema.Draft202012Validator:
    schema = build_schema()
    return jsonschema.Draft202012Validator(schema)


def test_schema_metadata_published_form() -> None:
    schema = build_schema()
    assert schema["$id"] == EXTENSION_SCHEMA_URL
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "title" in schema
    # Schema must use $defs (so nested $refs resolve correctly).
    assert "$defs" in schema


def test_schema_json_is_serializable_and_stable() -> None:
    payload = build_schema_json()
    # round-trip parses
    parsed = json.loads(payload)
    assert parsed["$id"] == EXTENSION_SCHEMA_URL
    # Stable ordering -- two runs produce the same bytes.
    assert build_schema_json() == payload


def test_schema_validates_v0_example() -> None:
    _validator().validate(_VALID)


# ---------------------------------------------------------------------------
# At least 10 malformed manifests with DISTINCT error paths.
# Acceptance criterion from LE-1014.
# ---------------------------------------------------------------------------


_MALFORMED_CASES: list[tuple[str, dict[str, Any]]] = [
    # 1. id wrong type
    ("id", {**_VALID, "id": 123}),
    # 2. id wrong pattern
    ("id", {**_VALID, "id": "Bad_ID"}),
    # 3. version wrong type
    ("version", {**_VALID, "version": 1}),
    # 4. version wrong pattern
    ("version", {**_VALID, "version": "v1"}),
    # 5. name empty
    ("name", {**_VALID, "name": ""}),
    # 6. lfx.bundle_api missing
    ("lfx", {**_VALID, "lfx": {}}),
    # 7. lfx.bundle_api empty
    ("lfx", {**_VALID, "lfx": {"bundle_api": []}}),
    # 8. lfx.bundle_api wrong element type
    ("lfx", {**_VALID, "lfx": {"bundle_api": ["1"]}}),
    # 9. bundles empty
    ("bundles", {**_VALID, "bundles": []}),
    # 10. bundles[0].path wrong type
    ("bundles", {**_VALID, "bundles": [{"name": "x", "path": 7}]}),
    # 11. capabilities extra field
    ("capabilities", {**_VALID, "capabilities": {"requiresCredentials": True, "extra": 1}}),
    # 12. id missing entirely
    ("id", {k: v for k, v in _VALID.items() if k != "id"}),
]


def test_schema_rejects_at_least_10_distinct_paths() -> None:
    validator = _validator()
    seen_paths: set[str] = set()
    for label, case in _MALFORMED_CASES:
        errors = list(validator.iter_errors(case))
        assert errors, f"Case {label!r} expected to fail but passed: {case}"
        # Capture the first error's path; this is what authors see.
        path = "/".join(str(p) for p in errors[0].absolute_path) or "(root)"
        seen_paths.add(path)
    # The acceptance criterion says >= 10 *distinct* error paths.
    assert len(seen_paths) >= 10, f"Only {len(seen_paths)} distinct paths: {seen_paths}"


@pytest.mark.parametrize(("label", "case"), _MALFORMED_CASES)
def test_each_malformed_case_fails(label: str, case: dict[str, Any]) -> None:
    """Per-case test so a regression pinpoints exactly which case stopped failing."""
    validator = _validator()
    errors = list(validator.iter_errors(case))
    assert errors, f"{label} case unexpectedly passed validation"
