"""Canonical provider records must fit the durable source contract."""

from __future__ import annotations

import pytest
from langflow.services.triggers.source_items import validate_source_items


def _item(**changes):
    return {"provider": "pilot", "resource": "items", "id": "1", "version": "1", "data": {}, **changes}


@pytest.mark.parametrize(("field", "limit"), [("provider", 32), ("resource", 512), ("id", 512), ("version", 255)])
def test_source_identity_fields_enforce_database_limits(field, limit):
    validate_source_items([_item(**{field: "x" * limit})])
    with pytest.raises(ValueError, match=f"invalid {field}"):
        validate_source_items([_item(**{field: "x" * (limit + 1)})])


@pytest.mark.parametrize("field", ["provider", "resource", "id", "version", "data"])
def test_source_items_require_every_canonical_field(field):
    item = _item()
    item.pop(field)
    with pytest.raises(ValueError, match="source item"):
        validate_source_items([item])


@pytest.mark.parametrize(
    "item",
    [
        None,
        [],
        "record",
        _item(id=1),
        _item(resource=""),
        _item(data=[]),
        _item(deleted="false"),
        _item(session_key=None),
    ],
)
def test_source_items_reject_invalid_record_shapes(item):
    with pytest.raises(ValueError, match="source item"):
        validate_source_items([item])


@pytest.mark.parametrize("data", [{"unsupported": object()}, {"nonfinite": float("nan")}])
def test_source_data_must_be_json_serializable(data):
    with pytest.raises(ValueError, match="JSON data"):
        validate_source_items([_item(data=data)])


def test_source_item_provider_must_match_the_verified_owner():
    with pytest.raises(ValueError, match="different provider"):
        validate_source_items([_item(provider="other")], provider="pilot")
    validate_source_items((_item(),), provider="pilot")
    validate_source_items([], provider="pilot")
