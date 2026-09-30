"""Unit tests for langflow_sdk.serialization."""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langflow_sdk.serialization import flow_to_json, normalize_flow, normalize_flow_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VOLATILE_FLOW: dict = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "name": "Test Flow",
    "description": "A flow",
    "updated_at": "2024-01-01T00:00:00",
    "created_at": "2024-01-01T00:00:00",
    "user_id": "bbbbbbbb-0000-0000-0000-000000000002",
    "folder_id": "cccccccc-0000-0000-0000-000000000003",
    "data": {
        "nodes": [],
        "edges": [],
    },
}

_NODE_WITH_SECRETS: dict = {
    "id": "node-1",
    "type": "genericNode",
    "positionAbsolute": {"x": 100, "y": 200},
    "dragging": False,
    "selected": True,
    "data": {
        "type": "OpenAI",
        "id": "node-1",
        "node": {
            "template": {
                "openai_api_key": {
                    "type": "str",
                    "password": True,
                    "load_from_db": False,
                    "value": "fake-secret-value",  # pragma: allowlist secret
                },
                "model_name": {
                    "type": "str",
                    "password": False,
                    "load_from_db": False,
                    "value": "gpt-4o",
                },
                "custom_code": {
                    "type": "code",
                    "password": False,
                    "value": "line one\nline two\nline three",
                },
                "db_field": {
                    "type": "str",
                    "password": False,
                    "load_from_db": True,
                    "value": "should-be-cleared",  # pragma: allowlist secret
                },
            }
        },
    },
}


def _flow_with_node(node: dict) -> dict:
    return {
        "id": "flow-1",
        "name": "My Flow",
        "data": {"nodes": [node], "edges": []},
        "updated_at": "2024-01-01T00:00:00",
        "user_id": "user-1",
    }


# ---------------------------------------------------------------------------
# Volatile field stripping
# ---------------------------------------------------------------------------


def test_strip_volatile_removes_instance_fields():
    result = normalize_flow(_VOLATILE_FLOW)
    for key in ("updated_at", "created_at", "user_id", "folder_id"):
        assert key not in result


def test_keep_volatile_preserves_fields():
    result = normalize_flow(_VOLATILE_FLOW, strip_volatile=False)
    assert result["updated_at"] == "2024-01-01T00:00:00"
    assert result["user_id"] == "bbbbbbbb-0000-0000-0000-000000000002"


def test_strip_volatile_keeps_id_and_name():
    result = normalize_flow(_VOLATILE_FLOW)
    assert result["id"] == "aaaaaaaa-0000-0000-0000-000000000001"
    assert result["name"] == "Test Flow"


# ---------------------------------------------------------------------------
# Secret stripping
# ---------------------------------------------------------------------------


def test_strip_secrets_clears_password_fields():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow)
    field = result["data"]["nodes"][0]["data"]["node"]["template"]["openai_api_key"]
    assert field["value"] == ""


def test_strip_secrets_clears_load_from_db_fields():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow)
    field = result["data"]["nodes"][0]["data"]["node"]["template"]["db_field"]
    assert field["value"] == ""


def test_keep_secrets_preserves_values():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow, strip_secrets=False)
    field = result["data"]["nodes"][0]["data"]["node"]["template"]["openai_api_key"]
    assert field["value"] == "fake-secret-value"  # pragma: allowlist secret


def test_non_secret_fields_are_unchanged():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow)
    field = result["data"]["nodes"][0]["data"]["node"]["template"]["model_name"]
    assert field["value"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Code-as-lines
# ---------------------------------------------------------------------------


def test_code_as_lines_splits_value():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow, code_as_lines=True)
    field = result["data"]["nodes"][0]["data"]["node"]["template"]["custom_code"]
    assert field["value"] == ["line one", "line two", "line three"]


def test_code_as_lines_off_by_default():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow)
    field = result["data"]["nodes"][0]["data"]["node"]["template"]["custom_code"]
    assert isinstance(field["value"], str)


def test_code_as_lines_idempotent_on_list():
    """If value is already a list, it stays a list."""
    node = {
        "id": "n",
        "data": {
            "type": "Custom",
            "node": {
                "template": {
                    "code": {"type": "code", "value": ["already", "lines"]},
                }
            },
        },
    }
    flow = {"id": "f", "name": "F", "data": {"nodes": [node], "edges": []}}
    result = normalize_flow(flow, code_as_lines=True)
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == ["already", "lines"]


# ---------------------------------------------------------------------------
# Node volatile key stripping
# ---------------------------------------------------------------------------


def test_strip_node_volatile_removes_ui_keys():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow)
    node = result["data"]["nodes"][0]
    for key in ("positionAbsolute", "dragging", "selected"):
        assert key not in node


def test_keep_node_volatile_preserves_ui_keys():
    flow = _flow_with_node(_NODE_WITH_SECRETS)
    result = normalize_flow(flow, strip_node_volatile=False)
    node = result["data"]["nodes"][0]
    assert node["positionAbsolute"] == {"x": 100, "y": 200}


# ---------------------------------------------------------------------------
# Key sorting
# ---------------------------------------------------------------------------


def test_sort_keys_produces_deterministic_output():
    flow_a = {"id": "1", "name": "A", "z_key": 1, "a_key": 2, "data": {"nodes": [], "edges": []}}
    flow_b = {"a_key": 2, "z_key": 1, "name": "A", "id": "1", "data": {"edges": [], "nodes": []}}
    assert normalize_flow(flow_a) == normalize_flow(flow_b)
    assert flow_to_json(normalize_flow(flow_a)) == flow_to_json(normalize_flow(flow_b))


def test_sort_keys_off_preserves_insertion_order():
    flow = {"z": 1, "a": 2, "data": {"nodes": [], "edges": []}}
    result = normalize_flow(flow, sort_keys=False)
    assert next(iter(result.keys())) == "z"


# ---------------------------------------------------------------------------
# Original not mutated
# ---------------------------------------------------------------------------


def test_original_flow_not_mutated():
    original = _flow_with_node(_NODE_WITH_SECRETS)
    original_copy = json.loads(json.dumps(original))
    normalize_flow(original, strip_secrets=True, code_as_lines=True)
    assert original == original_copy


# ---------------------------------------------------------------------------
# normalize_flow_file
# ---------------------------------------------------------------------------


def test_normalize_flow_file(tmp_path: Path):
    flow = {"id": "x", "name": "Test", "updated_at": "ts", "data": {"nodes": [], "edges": []}}
    src = tmp_path / "flow.json"
    src.write_text(json.dumps(flow), encoding="utf-8")

    result = normalize_flow_file(src)
    assert "updated_at" not in result
    assert result["id"] == "x"


def test_normalize_flow_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        normalize_flow_file(tmp_path / "missing.json")


def test_normalize_flow_file_bad_json(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        normalize_flow_file(bad)


# ---------------------------------------------------------------------------
# flow_to_json
# ---------------------------------------------------------------------------


def test_flow_to_json_ends_with_newline():
    result = flow_to_json({"id": "1", "name": "X"})
    assert result.endswith("\n")


def test_flow_to_json_is_valid_json():
    flow = {"id": "1", "name": "X", "data": {"nodes": [], "edges": []}}
    result = flow_to_json(flow)
    parsed = json.loads(result)
    assert parsed == flow
