"""JSON Schema export tests.

Acceptance criterion: published JSON Schema validates the v0 example and
rejects at least 10 malformed manifests with distinct error paths.
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema
import pytest
from lfx.extension.manifest import DEFERRED_FIELDS, EXTENSION_SCHEMA_URL, ExtensionManifest
from lfx.extension.schema import build_schema, build_schema_json

_VALID = {
    "$schema": EXTENSION_SCHEMA_URL,
    "id": "lfx-openai",
    "version": "1.2.3",
    "name": "OpenAI Bundle",
    "lfx": {"compat": ["1"]},
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


def _published_deferred_names() -> list[str]:
    """Resolve DEFERRED_FIELDS to the alias-aware names seen in the published schema."""
    fields = ExtensionManifest.model_fields
    return [(fields[name].alias or name) for name in DEFERRED_FIELDS]


def test_published_schema_does_not_carry_schema_version() -> None:
    """``schema_version`` must NOT appear in the published schema's properties.

    The schema's major version is pinned by ``$id`` (and by the author's
    ``$schema`` URL when present); a separate in-band ``schema_version`` field
    would create a second source of truth at every version bump.
    """
    schema = build_schema()
    assert "schema_version" not in schema["properties"]


def test_published_schema_strips_deferred_fields() -> None:
    """Deferred fields must NOT appear in the schema's ``properties`` map.

    The Pydantic model still carries them (so internal callers can do
    ``manifest.services is None``) but a third-party JSON Schema validator
    should reject ``services: {...}`` via ``additionalProperties: false`` with
    a generic "additional property" message rather than a confusing
    "expected null" one.  ``x-deferred-fields`` re-publishes the reserved
    names with their descriptions so tooling that wants a friendlier hint
    can find them.
    """
    schema = build_schema()
    assert schema["additionalProperties"] is False
    deferred = _published_deferred_names()
    for name in deferred:
        assert name not in schema["properties"], f"Deferred field {name!r} leaked into the published schema"
    assert "x-deferred-fields" in schema
    assert set(schema["x-deferred-fields"].keys()) == set(deferred)
    # Every entry must carry a non-empty description so tooling can render it.
    for name, description in schema["x-deferred-fields"].items():
        assert isinstance(description, str), f"x-deferred-fields[{name!r}] description must be a string"
        assert description, f"x-deferred-fields[{name!r}] description must be non-empty"


@pytest.mark.parametrize("deferred_name", _published_deferred_names())
def test_published_schema_rejects_each_deferred_field_via_additional_properties(
    deferred_name: str,
) -> None:
    """Each deferred field must be rejected via ``additionalProperties``.

    The error must NOT come from a ``type`` mismatch (which would surface to
    third-party validators as "expected null" — the older shape we replaced).
    """
    validator = _validator()
    case = {**_VALID, deferred_name: {"foo": "bar"}}
    errors = list(validator.iter_errors(case))
    assert errors, f"manifest with {deferred_name!r} unexpectedly passed schema validation"
    assert any(deferred_name in err.message and err.validator == "additionalProperties" for err in errors), (
        f"{deferred_name!r} did not produce an additionalProperties error: {[(e.validator, e.message) for e in errors]}"
    )


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
    # 6. lfx.compat missing
    ("lfx", {**_VALID, "lfx": {}}),
    # 7. lfx.compat empty
    ("lfx", {**_VALID, "lfx": {"compat": []}}),
    # 8. lfx.compat wrong element type (must be a string, not int)
    ("lfx", {**_VALID, "lfx": {"compat": [1]}}),
    # 9. bundles empty
    ("bundles", {**_VALID, "bundles": []}),
    # 10. bundles[0].path wrong type
    ("bundles", {**_VALID, "bundles": [{"name": "x", "path": 7}]}),
    # 11. multi-bundle (must be encoded as maxItems in the published schema, not
    # only as a model_validator that lives behind the JSON Schema export)
    (
        "bundles",
        {
            **_VALID,
            "bundles": [
                {"name": "a", "path": "a"},
                {"name": "b", "path": "b"},
            ],
        },
    ),
    # 12. capabilities extra field
    ("capabilities", {**_VALID, "capabilities": {"requiresCredentials": True, "extra": 1}}),
    # 13. id missing entirely
    ("id", {k: v for k, v in _VALID.items() if k != "id"}),
    # 14. deferred field set to a non-null value -- rejected via
    # ``additionalProperties: false`` rather than the older "expected null".
    ("(root)", {**_VALID, "services": {"foo": "bar"}}),
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
