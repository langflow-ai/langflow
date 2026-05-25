"""Tests for langflow.api.v1.global_variable_defaults.

Covers the gap where API-uploaded flows ignore global-variable default_fields
because load_from_db isn't auto-set on the stored template.

See https://github.com/langflow-ai/langflow/issues/11781.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.api.v1.global_variable_defaults import (
    apply_global_variable_defaults,
    apply_unavailable_fields_to_graph,
    build_unavailable_fields_map,
)


def _make_node(
    node_id: str,
    fields: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a minimal graph node with the given template fields."""
    return {
        "id": node_id,
        "data": {
            "node": {
                "template": {**fields, "_type": "Component"},
                "display_name": node_id,
            }
        },
    }


def _make_field(
    *,
    display_name: str,
    value: Any = "",
    field_type: str = "str",
    load_from_db: bool = False,
    show: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    """Build a minimal template field dict with reasonable defaults."""
    return {
        "display_name": display_name,
        "value": value,
        "type": field_type,
        "load_from_db": load_from_db,
        "show": show,
        **extra,
    }


class TestBuildUnavailableFieldsMap:
    """Tests for build_unavailable_fields_map (frontend-parity matcher)."""

    def test_single_variable_with_default_fields(self) -> None:
        result = build_unavailable_fields_map([("OPENAI_API_KEY", ["OpenAI API Key", "API Key"])])
        assert result == {
            "OpenAI API Key": "OPENAI_API_KEY",
            "API Key": "OPENAI_API_KEY",
        }

    def test_multiple_variables(self) -> None:
        result = build_unavailable_fields_map(
            [
                ("OPENAI_API_KEY", ["OpenAI API Key"]),
                ("ANTHROPIC_API_KEY", ["Anthropic API Key"]),
            ]
        )
        assert result == {
            "OpenAI API Key": "OPENAI_API_KEY",
            "Anthropic API Key": "ANTHROPIC_API_KEY",
        }

    def test_later_variable_wins_on_collision(self) -> None:
        # Mirrors the frontend's forEach last-write-wins behaviour.
        result = build_unavailable_fields_map(
            [
                ("FIRST", ["Shared Field"]),
                ("SECOND", ["Shared Field"]),
            ]
        )
        assert result == {"Shared Field": "SECOND"}

    def test_empty_or_none_default_fields_skipped(self) -> None:
        result = build_unavailable_fields_map(
            [
                ("EMPTY_LIST", []),
                ("NONE_FIELDS", None),
                ("REAL", ["X"]),
            ]
        )
        assert result == {"X": "REAL"}

    def test_empty_input(self) -> None:
        assert build_unavailable_fields_map([]) == {}

    def test_non_string_field_entries_skipped(self) -> None:
        # Defensive: tolerate malformed data in the JSON column.
        result = build_unavailable_fields_map([("V", ["Good", "", 42, None])])  # type: ignore[list-item]
        assert result == {"Good": "V"}


class TestApplyUnavailableFieldsToGraph:
    """Tests for apply_unavailable_fields_to_graph (pure transformer)."""

    def test_empty_field_with_matching_display_name_is_bound(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "openai-1",
                    {"api_key": _make_field(display_name="OpenAI API Key")},
                )
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})
        field = result["nodes"][0]["data"]["node"]["template"]["api_key"]
        assert field["value"] == "OPENAI_API_KEY"
        assert field["load_from_db"] is True

    def test_field_with_existing_value_is_left_alone(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "openai-1",
                    {"api_key": _make_field(display_name="OpenAI API Key", value="sk-explicit")},
                )
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})
        field = result["nodes"][0]["data"]["node"]["template"]["api_key"]
        assert field["value"] == "sk-explicit"
        assert field["load_from_db"] is False

    def test_field_already_load_from_db_is_left_alone(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "openai-1",
                    {
                        "api_key": _make_field(
                            display_name="OpenAI API Key",
                            value="CUSTOM_VAR",
                            load_from_db=True,
                        )
                    },
                )
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})
        field = result["nodes"][0]["data"]["node"]["template"]["api_key"]
        # Value preserved, flag preserved -- we don't clobber an explicit choice.
        assert field["value"] == "CUSTOM_VAR"
        assert field["load_from_db"] is True

    @pytest.mark.parametrize(
        "field_type",
        ["dict", "code", "table", "NestedDict", "bool", "int", "float", "sortableList"],
    )
    def test_non_str_field_types_are_skipped(self, field_type: str) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "n1",
                    {"f": _make_field(display_name="OpenAI API Key", field_type=field_type)},
                )
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})
        field = result["nodes"][0]["data"]["node"]["template"]["f"]
        assert field["value"] == ""
        assert field["load_from_db"] is False

    def test_hidden_field_is_skipped(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "n1",
                    {"api_key": _make_field(display_name="OpenAI API Key", show=False)},
                )
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})
        field = result["nodes"][0]["data"]["node"]["template"]["api_key"]
        assert field["value"] == ""
        assert field["load_from_db"] is False

    def test_unmatched_display_name_is_left_alone(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "n1",
                    {"api_key": _make_field(display_name="Some Other Field")},
                )
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})
        field = result["nodes"][0]["data"]["node"]["template"]["api_key"]
        assert field["value"] == ""
        assert field["load_from_db"] is False

    def test_multiple_nodes_mixed_eligibility(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "openai-1",
                    {"api_key": _make_field(display_name="OpenAI API Key")},
                ),
                _make_node(
                    "anthropic-1",
                    {"api_key": _make_field(display_name="Anthropic API Key", value="sk-real")},
                ),
                _make_node(
                    "other-1",
                    {"text": _make_field(display_name="Plain Text Input")},
                ),
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(
            graph_data,
            {
                "OpenAI API Key": "OPENAI_API_KEY",
                "Anthropic API Key": "ANTHROPIC_API_KEY",
            },
        )
        openai_field = result["nodes"][0]["data"]["node"]["template"]["api_key"]
        anthropic_field = result["nodes"][1]["data"]["node"]["template"]["api_key"]
        text_field = result["nodes"][2]["data"]["node"]["template"]["text"]

        assert openai_field["value"] == "OPENAI_API_KEY"
        assert openai_field["load_from_db"] is True
        # Existing value -- left alone.
        assert anthropic_field["value"] == "sk-real"
        assert anthropic_field["load_from_db"] is False
        # No matching display_name -- left alone.
        assert text_field["value"] == ""
        assert text_field["load_from_db"] is False

    def test_empty_unavailable_map_returns_input_unchanged(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "n1",
                    {"api_key": _make_field(display_name="OpenAI API Key")},
                )
            ],
            "edges": [],
        }
        result = apply_unavailable_fields_to_graph(graph_data, {})
        assert result is graph_data

    def test_input_is_not_mutated(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "n1",
                    {"api_key": _make_field(display_name="OpenAI API Key")},
                )
            ],
            "edges": [],
        }
        original_field = graph_data["nodes"][0]["data"]["node"]["template"]["api_key"]
        original_value = original_field["value"]
        original_flag = original_field["load_from_db"]

        apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})

        # Caller's dict is untouched.
        assert original_field["value"] == original_value
        assert original_field["load_from_db"] == original_flag

    def test_skips_type_marker_field(self) -> None:
        # _type is a metadata key in templates, not a real field. It must not crash.
        graph_data = {
            "nodes": [
                _make_node(
                    "n1",
                    {"api_key": _make_field(display_name="OpenAI API Key")},
                )
            ]
        }
        result = apply_unavailable_fields_to_graph(graph_data, {"OpenAI API Key": "OPENAI_API_KEY"})
        # Sanity: real field was still bound.
        assert result["nodes"][0]["data"]["node"]["template"]["api_key"]["load_from_db"] is True

    def test_malformed_graph_is_tolerated(self) -> None:
        # Missing "nodes" / non-dict node entries shouldn't crash.
        assert apply_unavailable_fields_to_graph({}, {"X": "Y"}) == {}
        assert apply_unavailable_fields_to_graph({"nodes": "not-a-list"}, {"X": "Y"}) == {"nodes": "not-a-list"}
        assert apply_unavailable_fields_to_graph({"nodes": [None, "string", {}]}, {"X": "Y"}) == {
            "nodes": [None, "string", {}]
        }


class TestApplyGlobalVariableDefaultsAsync:
    """Tests for the async wrapper that fetches the user's variables."""

    @pytest.mark.asyncio
    async def test_applies_defaults_from_variable_service(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "openai-1",
                    {"api_key": _make_field(display_name="OpenAI API Key")},
                )
            ],
            "edges": [],
        }
        mock_var = MagicMock()
        mock_var.name = "OPENAI_API_KEY"
        mock_var.default_fields = ["OpenAI API Key"]

        mock_service = MagicMock()
        mock_service.get_all = AsyncMock(return_value=[mock_var])

        # session_scope is an async context manager -- give it the minimum protocol.
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "langflow.api.v1.global_variable_defaults.get_variable_service",
                return_value=mock_service,
            ),
            patch(
                "langflow.api.v1.global_variable_defaults.session_scope",
                return_value=mock_session_cm,
            ),
        ):
            result = await apply_global_variable_defaults(graph_data, user_id="user-1")

        field = result["nodes"][0]["data"]["node"]["template"]["api_key"]
        assert field["value"] == "OPENAI_API_KEY"
        assert field["load_from_db"] is True

    @pytest.mark.asyncio
    async def test_variable_service_exception_is_swallowed(self) -> None:
        graph_data = {
            "nodes": [
                _make_node(
                    "openai-1",
                    {"api_key": _make_field(display_name="OpenAI API Key")},
                )
            ]
        }
        with patch(
            "langflow.api.v1.global_variable_defaults.get_variable_service",
            side_effect=RuntimeError("DB unavailable"),
        ):
            result = await apply_global_variable_defaults(graph_data, user_id="user-1")

        # Original graph_data returned unchanged; no exception propagated.
        assert result is graph_data
        assert result["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == ""

    @pytest.mark.asyncio
    async def test_no_user_id_returns_input_unchanged(self) -> None:
        graph_data: dict[str, Any] = {"nodes": []}
        result = await apply_global_variable_defaults(graph_data, user_id=None)  # type: ignore[arg-type]
        assert result is graph_data
