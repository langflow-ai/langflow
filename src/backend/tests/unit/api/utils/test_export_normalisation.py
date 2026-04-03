"""Unit tests for normalize_flow_for_export / normalize_code_for_import.

These tests run entirely in-process — no database or HTTP server required.
"""

from __future__ import annotations

import copy
import json

from langflow.api.utils.core import normalize_code_for_import, normalize_flow_for_export

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# split("\n") keeps trailing newlines as a final empty string, making the
# round-trip lossless.  splitlines() would drop the trailing "\n".
_CODE_STRING = "def build(self):\n    return self.input\n"
_CODE_LINES = ["def build(self):", "    return self.input", ""]


def _make_flow(*, extra_top: dict | None = None, code_value: str | list | None = _CODE_STRING) -> dict:
    """Return a minimal flow dict that exercises all normalisation paths."""
    flow: dict = {
        "id": "17050493-96dd-4dc9-ba42-4bd0075fd23d",
        "name": "Test Flow",
        "description": "A test flow",
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "position": {"x": 100, "y": 200},
                    "positionAbsolute": {"x": 100, "y": 200},
                    "dragging": False,
                    "selected": True,
                    "data": {
                        "id": "node-1",
                        "type": "PythonFunctionComponent",
                        "node": {
                            "template": {
                                "code": {
                                    "type": "code",
                                    "value": code_value,
                                    "name": "code",
                                },
                                "api_key": {
                                    "type": "str",
                                    "value": "sk-secret",
                                    "name": "api_key",
                                    "password": True,
                                },
                            }
                        },
                    },
                }
            ],
            "edges": [],
        },
        "updated_at": "2024-01-01T12:00:00Z",
        "created_at": "2023-06-15T08:00:00Z",
        "user_id": "user-uuid-123",
        "folder_id": "folder-uuid-456",
        "access_type": "PRIVATE",
        "gradient": "linear-gradient(to right, #f00, #00f)",
        "is_component": False,
        "endpoint_name": "test-flow",
    }
    if extra_top:
        flow.update(extra_top)
    return flow


# ---------------------------------------------------------------------------
# normalize_flow_for_export — volatile field stripping
# ---------------------------------------------------------------------------


class TestNormaliseVolatileFields:
    def test_strips_updated_at(self):
        result = normalize_flow_for_export(_make_flow())
        assert "updated_at" not in result

    def test_strips_created_at(self):
        result = normalize_flow_for_export(_make_flow())
        assert "created_at" not in result

    def test_strips_user_id(self):
        result = normalize_flow_for_export(_make_flow())
        assert "user_id" not in result

    def test_strips_folder_id(self):
        result = normalize_flow_for_export(_make_flow())
        assert "folder_id" not in result

    def test_strips_access_type(self):
        result = normalize_flow_for_export(_make_flow())
        assert "access_type" not in result

    def test_strips_gradient(self):
        result = normalize_flow_for_export(_make_flow())
        assert "gradient" not in result

    def test_keeps_stable_fields(self):
        result = normalize_flow_for_export(_make_flow())
        assert result["id"] == "17050493-96dd-4dc9-ba42-4bd0075fd23d"
        assert result["name"] == "Test Flow"
        assert result["description"] == "A test flow"
        assert result["endpoint_name"] == "test-flow"
        assert result["is_component"] is False

    def test_missing_volatile_fields_do_not_raise(self):
        """Calling on a minimal flow without any volatile fields is safe."""
        minimal = {"id": "abc", "name": "Minimal", "data": {"nodes": [], "edges": []}}
        result = normalize_flow_for_export(minimal)
        assert result["name"] == "Minimal"


# ---------------------------------------------------------------------------
# normalize_flow_for_export — node UI state stripping
# ---------------------------------------------------------------------------


class TestNormaliseNodeUiState:
    def test_strips_position_absolute(self):
        result = normalize_flow_for_export(_make_flow())
        node = result["data"]["nodes"][0]
        assert "positionAbsolute" not in node

    def test_strips_dragging(self):
        result = normalize_flow_for_export(_make_flow())
        node = result["data"]["nodes"][0]
        assert "dragging" not in node

    def test_strips_selected(self):
        result = normalize_flow_for_export(_make_flow())
        node = result["data"]["nodes"][0]
        assert "selected" not in node

    def test_keeps_position(self):
        """Position (canvas coords) is kept — only the derived positionAbsolute is stripped."""
        result = normalize_flow_for_export(_make_flow())
        node = result["data"]["nodes"][0]
        assert node["position"] == {"x": 100, "y": 200}


# ---------------------------------------------------------------------------
# normalize_flow_for_export — code → list-of-lines
# ---------------------------------------------------------------------------


class TestNormaliseCodeToLines:
    def test_code_field_becomes_list(self):
        result = normalize_flow_for_export(_make_flow())
        code_field = result["data"]["nodes"][0]["data"]["node"]["template"]["code"]
        assert isinstance(code_field["value"], list)

    def test_code_lines_content(self):
        result = normalize_flow_for_export(_make_flow())
        code_field = result["data"]["nodes"][0]["data"]["node"]["template"]["code"]
        assert code_field["value"] == _CODE_LINES

    def test_non_code_field_untouched(self):
        result = normalize_flow_for_export(_make_flow())
        api_key_field = result["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]
        assert api_key_field["value"] == "sk-secret"  # unchanged

    def test_already_list_code_unchanged(self):
        """If code is already a list (re-export scenario), it should stay as-is."""
        result = normalize_flow_for_export(_make_flow(code_value=_CODE_LINES))
        code_field = result["data"]["nodes"][0]["data"]["node"]["template"]["code"]
        assert code_field["value"] == _CODE_LINES

    def test_empty_code_string(self):
        # "".split("\n") == [""], preserving the empty line
        result = normalize_flow_for_export(_make_flow(code_value=""))
        code_field = result["data"]["nodes"][0]["data"]["node"]["template"]["code"]
        assert code_field["value"] == [""]  # split("\n") on "" gives [""]

    def test_no_data_nodes_safe(self):
        flow = {"id": "x", "name": "Empty", "data": {"nodes": [], "edges": []}}
        # Must not raise
        normalize_flow_for_export(flow)


# ---------------------------------------------------------------------------
# normalize_flow_for_export — does not mutate the original
# ---------------------------------------------------------------------------


class TestNormalisationIsNonMutating:
    def test_original_unchanged(self):
        original = _make_flow()
        original_copy = copy.deepcopy(original)
        normalize_flow_for_export(original)
        assert original == original_copy


# ---------------------------------------------------------------------------
# normalize_code_for_import — list → string
# ---------------------------------------------------------------------------


class TestNormaliseCodeForImport:
    def test_rejoins_list_to_string(self):
        flow = _make_flow(code_value=_CODE_LINES)
        result = normalize_code_for_import(flow)
        code_field = result["data"]["nodes"][0]["data"]["node"]["template"]["code"]
        assert isinstance(code_field["value"], str)
        assert code_field["value"] == "\n".join(_CODE_LINES)

    def test_string_format_passthrough(self):
        """Legacy string format must survive import normalisation unchanged."""
        flow = _make_flow(code_value=_CODE_STRING)
        result = normalize_code_for_import(flow)
        code_field = result["data"]["nodes"][0]["data"]["node"]["template"]["code"]
        assert code_field["value"] == _CODE_STRING

    def test_none_code_value_passthrough(self):
        flow = _make_flow(code_value=None)
        result = normalize_code_for_import(flow)
        code_field = result["data"]["nodes"][0]["data"]["node"]["template"]["code"]
        assert code_field["value"] is None

    def test_original_unchanged(self):
        flow = _make_flow(code_value=_CODE_LINES)
        original_copy = copy.deepcopy(flow)
        normalize_code_for_import(flow)
        assert flow == original_copy


# ---------------------------------------------------------------------------
# Round-trip: export → import restores code strings
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_code_round_trips_to_identical_string(self):
        original = _make_flow()
        exported = normalize_flow_for_export(original)
        imported = normalize_code_for_import(exported)
        code_orig = original["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"]
        code_trip = imported["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"]
        assert code_trip == code_orig

    def test_two_exports_byte_identical(self):
        """Consecutive exports of the same flow must produce identical JSON bytes."""
        import orjson

        flow = _make_flow()
        export1 = orjson.dumps(normalize_flow_for_export(flow), option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
        export2 = orjson.dumps(normalize_flow_for_export(flow), option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
        assert export1 == export2

    def test_sorted_keys_top_level(self):
        """All top-level keys must be in lexicographic order after export."""
        import orjson

        flow = _make_flow()
        raw = orjson.dumps(normalize_flow_for_export(flow), option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2).decode()
        parsed = json.loads(raw)
        top_keys = list(parsed.keys())
        assert top_keys == sorted(top_keys)
