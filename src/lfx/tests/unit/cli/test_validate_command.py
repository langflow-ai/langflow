"""Unit tests for lfx validate — structural, extended checks, directory scanning, strict mode.

All tests run entirely in-process (no running Langflow instance or component
registry required).  Level-2 component checks are skipped via skip_components=True
so the registry never needs to be loaded.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from lfx.cli.validate import (
    ValidationResult,
    _check_missing_credentials,
    _check_orphaned_nodes,
    _check_unused_nodes,
    _check_version_mismatch,
    _expand_paths,
    validate_command,
    validate_flow_file,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_MINIMAL_VALID = {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Test Flow",
    "data": {"nodes": [], "edges": []},
}

_NODE = {
    "id": "node-a",
    "data": {
        "id": "node-a",
        "type": "ChatInput",
        "node": {
            "display_name": "Chat Input",
            "template": {},
        },
    },
    "position": {"x": 0, "y": 0},
}


def _write_flow(tmp_path: Path, name: str, flow: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(flow), encoding="utf-8")
    return p


def _make_result(issues=None) -> ValidationResult:
    result = ValidationResult(path=Path("test.json"))
    if issues:
        result.issues = issues
    return result


# ---------------------------------------------------------------------------
# validate_flow_file — Level 1: structural
# ---------------------------------------------------------------------------


class TestStructural:
    def test_valid_minimal_flow(self, tmp_path):
        p = _write_flow(tmp_path, "flow.json", _MINIMAL_VALID)
        result = validate_flow_file(p, level=1)
        assert result.ok
        assert not result.errors

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json", encoding="utf-8")
        result = validate_flow_file(p, level=1)
        assert not result.ok
        assert any("Invalid JSON" in i.message for i in result.errors)

    def test_missing_top_level_id(self, tmp_path):
        flow = {k: v for k, v in _MINIMAL_VALID.items() if k != "id"}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=1)
        assert not result.ok
        assert any("id" in i.message for i in result.errors)

    def test_missing_top_level_name(self, tmp_path):
        flow = {k: v for k, v in _MINIMAL_VALID.items() if k != "name"}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=1)
        assert not result.ok

    def test_missing_data_nodes(self, tmp_path):
        flow = {**_MINIMAL_VALID, "data": {"edges": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=1)
        assert not result.ok
        assert any("data.nodes" in i.message for i in result.errors)

    def test_missing_data_edges(self, tmp_path):
        flow = {**_MINIMAL_VALID, "data": {"nodes": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=1)
        assert not result.ok

    def test_data_not_object(self, tmp_path):
        flow = {**_MINIMAL_VALID, "data": "not-an-object"}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=1)
        assert not result.ok

    def test_file_not_found(self, tmp_path):
        result = validate_flow_file(tmp_path / "missing.json", level=1)
        assert not result.ok
        assert any("Cannot read" in i.message for i in result.errors)


# ---------------------------------------------------------------------------
# _check_orphaned_nodes
# ---------------------------------------------------------------------------


class TestOrphanedNodes:
    def _result(self):
        return ValidationResult(path=Path("x.json"))

    def test_single_node_not_orphaned(self):
        """Single-node flows are exempt from orphan detection."""
        flow = {
            "data": {
                "nodes": [_NODE],
                "edges": [],
            }
        }
        result = self._result()
        _check_orphaned_nodes(flow, result)
        assert not result.warnings

    def test_empty_flow_not_orphaned(self):
        flow = {"data": {"nodes": [], "edges": []}}
        result = self._result()
        _check_orphaned_nodes(flow, result)
        assert not result.warnings

    def test_connected_two_nodes_not_orphaned(self):
        node_b = {**_NODE, "id": "node-b", "data": {**_NODE["data"], "id": "node-b"}}
        flow = {
            "data": {
                "nodes": [_NODE, node_b],
                "edges": [{"source": "node-a", "target": "node-b"}],
            }
        }
        result = self._result()
        _check_orphaned_nodes(flow, result)
        assert not result.warnings

    def test_disconnected_node_is_orphaned(self):
        node_b = {**_NODE, "id": "node-b", "data": {**_NODE["data"], "id": "node-b"}}
        node_c = {**_NODE, "id": "node-c", "data": {**_NODE["data"], "id": "node-c"}}
        flow = {
            "data": {
                # node-c has no edges
                "nodes": [_NODE, node_b, node_c],
                "edges": [{"source": "node-a", "target": "node-b"}],
            }
        }
        result = self._result()
        _check_orphaned_nodes(flow, result)
        orphan_warnings = [w for w in result.warnings if "Orphaned" in w.message]
        assert len(orphan_warnings) == 1
        assert orphan_warnings[0].node_id == "node-c"


# ---------------------------------------------------------------------------
# _check_unused_nodes
# ---------------------------------------------------------------------------


class TestUnusedNodes:
    def _result(self):
        return ValidationResult(path=Path("x.json"))

    def _output_node(self, node_id: str) -> dict:
        return {
            "id": node_id,
            "data": {
                "id": node_id,
                "type": "ChatOutput",
                "node": {"display_name": "Chat Output", "template": {}},
            },
        }

    def _middle_node(self, node_id: str) -> dict:
        return {
            "id": node_id,
            "data": {
                "id": node_id,
                "type": "TextSplitter",
                "node": {"display_name": "Splitter", "template": {}},
            },
        }

    def test_single_node_exempt(self):
        flow = {"data": {"nodes": [_NODE], "edges": []}}
        result = self._result()
        _check_unused_nodes(flow, result)
        assert not result.warnings

    def test_no_output_nodes_skipped(self):
        """If there are no output nodes, unused check is skipped entirely."""
        node_b = self._middle_node("node-b")
        flow = {
            "data": {
                "nodes": [_NODE, node_b],
                "edges": [],
            }
        }
        result = self._result()
        _check_unused_nodes(flow, result)
        assert not result.warnings

    def test_node_feeding_output_is_used(self):
        out = self._output_node("out")
        flow = {
            "data": {
                "nodes": [_NODE, out],
                "edges": [{"source": "node-a", "target": "out"}],
            }
        }
        result = self._result()
        _check_unused_nodes(flow, result)
        assert not result.warnings

    def test_dangling_node_not_reaching_output_is_unused(self):
        out = self._output_node("out")
        mid = self._middle_node("mid")
        dangling = self._middle_node("dangling")
        flow = {
            "data": {
                "nodes": [_NODE, mid, out, dangling],
                "edges": [
                    {"source": "node-a", "target": "mid"},
                    {"source": "mid", "target": "out"},
                    # dangling has no path to out
                ],
            }
        }
        result = self._result()
        _check_unused_nodes(flow, result)
        unused = [w for w in result.warnings if "Unused" in w.message]
        assert len(unused) == 1
        assert unused[0].node_id == "dangling"


# ---------------------------------------------------------------------------
# validate_flow_file — levels 3 & 4 (no component registry needed)
# ---------------------------------------------------------------------------


class TestEdgeTypeCheck:
    def test_edge_to_missing_node_is_error(self, tmp_path):
        flow = {
            **_MINIMAL_VALID,
            "data": {
                "nodes": [_NODE],
                "edges": [{"source": "node-a", "target": "DOES-NOT-EXIST"}],
            },
        }
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=3, skip_components=True)
        assert any("non-existent" in i.message for i in result.errors)

    def test_compatible_types_no_warning(self, tmp_path):
        node_b = {**_NODE, "id": "node-b", "data": {**_NODE["data"], "id": "node-b"}}
        edge = {
            "source": "node-a",
            "target": "node-b",
            "data": {
                "sourceHandle": {"output_types": ["Message"]},
                "targetHandle": {"type": "Message", "fieldName": "input_value"},
            },
        }
        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE, node_b], "edges": [edge]}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=3, skip_components=True)
        type_warnings = [i for i in result.warnings if "type mismatch" in i.message.lower()]
        assert not type_warnings

    def test_incompatible_types_gives_warning(self, tmp_path):
        node_b = {**_NODE, "id": "node-b", "data": {**_NODE["data"], "id": "node-b"}}
        edge = {
            "source": "node-a",
            "target": "node-b",
            "data": {
                "sourceHandle": {"output_types": ["Message"]},
                "targetHandle": {"type": "DataFrame", "fieldName": "input_value"},
            },
        }
        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE, node_b], "edges": [edge]}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=3, skip_components=True)
        type_warnings = [i for i in result.warnings if "type mismatch" in i.message.lower()]
        assert type_warnings


class TestRequiredInputs:
    def _node_with_required_field(self, has_value: bool) -> dict:  # noqa: FBT001
        return {
            "id": "node-req",
            "data": {
                "id": "node-req",
                "type": "SomeComponent",
                "node": {
                    "display_name": "Some",
                    "template": {
                        "my_field": {
                            "required": True,
                            "show": True,
                            "value": "filled" if has_value else None,
                        }
                    },
                },
            },
        }

    def test_required_field_with_value_passes(self, tmp_path):
        node = self._node_with_required_field(has_value=True)
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=4, skip_components=True, skip_edge_types=True)
        req_errors = [e for e in result.errors if "Required input" in e.message]
        assert not req_errors

    def test_required_field_without_value_or_edge_fails(self, tmp_path):
        node = self._node_with_required_field(has_value=False)
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=4, skip_components=True, skip_edge_types=True)
        req_errors = [e for e in result.errors if "Required input" in e.message]
        assert req_errors

    def test_required_field_with_incoming_edge_passes(self, tmp_path):
        node = self._node_with_required_field(has_value=False)
        edge = {
            "source": "other",
            "target": "node-req",
            "data": {"targetHandle": {"fieldName": "my_field"}},
        }
        src = {**_NODE, "id": "other"}
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node, src], "edges": [edge]}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=4, skip_components=True, skip_edge_types=True)
        req_errors = [e for e in result.errors if "Required input" in e.message]
        assert not req_errors


# ---------------------------------------------------------------------------
# Directory expansion (_expand_paths)
# ---------------------------------------------------------------------------


class TestExpandPaths:
    def test_single_file(self, tmp_path):
        p = _write_flow(tmp_path, "a.json", _MINIMAL_VALID)
        result = _expand_paths([str(p)])
        assert result == [p]

    def test_directory_finds_json_files(self, tmp_path):
        _write_flow(tmp_path, "a.json", _MINIMAL_VALID)
        _write_flow(tmp_path, "b.json", _MINIMAL_VALID)
        (tmp_path / "readme.txt").write_text("ignore me")
        result = _expand_paths([str(tmp_path)])
        assert len(result) == 2
        assert all(p.suffix == ".json" for p in result)

    def test_directory_recurses_into_subdirs(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        _write_flow(tmp_path, "root.json", _MINIMAL_VALID)
        _write_flow(sub, "nested.json", _MINIMAL_VALID)
        result = _expand_paths([str(tmp_path)])
        assert len(result) == 2

    def test_empty_directory_returns_no_paths(self, tmp_path):
        # Should not raise; validate_command handles empty list separately
        result = _expand_paths([str(tmp_path)])
        assert result == []

    def test_missing_path_raises_exit(self, tmp_path):
        import typer

        with pytest.raises(typer.Exit):
            _expand_paths([str(tmp_path / "nonexistent.json")])


# ---------------------------------------------------------------------------
# --strict mode
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_strict_warning_becomes_failure(self, tmp_path):
        """A flow with only warnings passes normally but fails under --strict."""
        # Two-node flow with one orphaned node → produces a warning
        node_b = {**_NODE, "id": "node-b", "data": {**_NODE["data"], "id": "node-b"}}
        flow = {
            **_MINIMAL_VALID,
            "data": {
                "nodes": [_NODE, node_b],
                "edges": [],  # both nodes are orphaned → warnings
            },
        }
        p = _write_flow(tmp_path, "flow.json", flow)

        # Without strict — should pass (only warnings)
        result = validate_flow_file(p, level=1, skip_components=True)
        assert result.ok  # no errors, so ok=True
        assert result.warnings  # but there are warnings

        # validate_command --strict should exit 1
        import typer

        with pytest.raises(typer.Exit) as exc_info:
            validate_command(
                flow_paths=[str(p)],
                level=1,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=True,
                skip_credentials=True,
                strict=True,
                verbose=False,
                output_format="text",
            )
        assert exc_info.value.exit_code == 1

    def test_no_issues_strict_passes(self, tmp_path):
        """A fully clean flow passes even under --strict."""
        p = _write_flow(tmp_path, "flow.json", _MINIMAL_VALID)
        # Should not raise
        validate_command(
            flow_paths=[str(p)],
            level=1,
            skip_components=True,
            skip_edge_types=True,
            skip_required_inputs=True,
            skip_version_check=True,
            skip_credentials=True,
            strict=True,
            verbose=False,
            output_format="text",
        )

    def test_strict_json_output_marks_ok_false(self, tmp_path, capsys):
        """Under --strict, JSON output sets ok=false for flows with warnings."""
        node_b = {**_NODE, "id": "node-b", "data": {**_NODE["data"], "id": "node-b"}}
        flow = {
            **_MINIMAL_VALID,
            "data": {"nodes": [_NODE, node_b], "edges": []},
        }
        p = _write_flow(tmp_path, "flow.json", flow)

        import typer

        with pytest.raises(typer.Exit):
            validate_command(
                flow_paths=[str(p)],
                level=1,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=True,
                skip_credentials=True,
                strict=True,
                verbose=False,
                output_format="json",
            )

        captured = capsys.readouterr()
        out = json.loads(captured.out)
        assert len(out) == 1
        assert out[0]["ok"] is False


# ---------------------------------------------------------------------------
# --format json output shape
# ---------------------------------------------------------------------------


class TestJsonOutput:
    def test_json_output_shape(self, tmp_path, capsys):
        p = _write_flow(tmp_path, "flow.json", _MINIMAL_VALID)
        validate_command(
            flow_paths=[str(p)],
            level=1,
            skip_components=True,
            skip_edge_types=True,
            skip_required_inputs=True,
            skip_version_check=True,
            skip_credentials=True,
            strict=False,
            verbose=False,
            output_format="json",
        )
        captured = capsys.readouterr()
        out = json.loads(captured.out)
        assert isinstance(out, list)
        assert out[0]["ok"] is True
        assert "issues" in out[0]
        assert "path" in out[0]

    def test_json_output_includes_errors(self, tmp_path, capsys):
        bad_flow = {k: v for k, v in _MINIMAL_VALID.items() if k != "id"}
        p = _write_flow(tmp_path, "flow.json", bad_flow)
        import typer

        with pytest.raises(typer.Exit):
            validate_command(
                flow_paths=[str(p)],
                level=1,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=True,
                skip_credentials=True,
                strict=False,
                verbose=False,
                output_format="json",
            )
        captured = capsys.readouterr()
        out = json.loads(captured.out)
        assert out[0]["ok"] is False
        errors = [i for i in out[0]["issues"] if i["severity"] == "error"]
        assert errors


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_clean_flow_exits_0(self, tmp_path):
        p = _write_flow(tmp_path, "flow.json", _MINIMAL_VALID)
        # No exception raised means exit 0
        validate_command(
            flow_paths=[str(p)],
            level=1,
            skip_components=True,
            skip_edge_types=True,
            skip_required_inputs=True,
            skip_version_check=True,
            skip_credentials=True,
            strict=False,
            verbose=False,
            output_format="text",
        )

    def test_invalid_flow_exits_1(self, tmp_path):
        import typer

        bad = {k: v for k, v in _MINIMAL_VALID.items() if k != "name"}
        p = _write_flow(tmp_path, "flow.json", bad)
        with pytest.raises(typer.Exit) as exc_info:
            validate_command(
                flow_paths=[str(p)],
                level=1,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=True,
                skip_credentials=True,
                strict=False,
                verbose=False,
                output_format="text",
            )
        assert exc_info.value.exit_code == 1

    def test_missing_file_exits_2(self, tmp_path):
        import typer

        with pytest.raises(typer.Exit) as exc_info:
            validate_command(
                flow_paths=[str(tmp_path / "ghost.json")],
                level=1,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=True,
                skip_credentials=True,
                strict=False,
                verbose=False,
                output_format="text",
            )
        assert exc_info.value.exit_code == 2

    def test_directory_with_invalid_flow_exits_1(self, tmp_path):
        import typer

        bad = {k: v for k, v in _MINIMAL_VALID.items() if k != "name"}
        _write_flow(tmp_path, "bad.json", bad)
        with pytest.raises(typer.Exit) as exc_info:
            validate_command(
                flow_paths=[str(tmp_path)],
                level=1,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=True,
                skip_credentials=True,
                strict=False,
                verbose=False,
                output_format="text",
            )
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# Extended check: version mismatch / outdated components
# ---------------------------------------------------------------------------

_NODE_WITH_VERSION = {
    "id": "node-v",
    "data": {
        "id": "node-v",
        "type": "ChatInput",
        "node": {
            "display_name": "Chat Input",
            "lf_version": "1.8.0",
            "template": {},
        },
    },
}


class TestVersionMismatch:
    def _make_result(self) -> ValidationResult:
        return ValidationResult(path=Path("test.json"))

    def test_no_lf_version_field_produces_no_warning(self):
        """Nodes without lf_version metadata are ignored."""
        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE], "edges": []}}
        result = self._make_result()
        with patch("lfx.cli.validation.core._get_lf_version", return_value="1.9.0"):
            _check_version_mismatch(flow, result)
        assert not result.warnings

    def test_matching_version_produces_no_warning(self):
        """lf_version equal to installed version → no warning."""
        node = {
            **_NODE_WITH_VERSION,
            "data": {
                **_NODE_WITH_VERSION["data"],
                "node": {**_NODE_WITH_VERSION["data"]["node"], "lf_version": "1.9.0"},
            },
        }
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        result = self._make_result()
        with patch("lfx.cli.validation.core._get_lf_version", return_value="1.9.0"):
            _check_version_mismatch(flow, result)
        assert not result.warnings

    def test_mismatched_version_produces_warning(self):
        """lf_version != installed → one warning mentioning both versions."""
        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE_WITH_VERSION], "edges": []}}
        result = self._make_result()
        with patch("lfx.cli.validation.core._get_lf_version", return_value="1.9.0"):
            _check_version_mismatch(flow, result)
        assert len(result.warnings) == 1
        msg = result.warnings[0].message
        assert "1.8.0" in msg
        assert "1.9.0" in msg

    def test_multiple_different_versions_produce_one_warning_each(self):
        """Two distinct old versions → two separate warnings."""
        node_b = {
            "id": "node-b",
            "data": {
                "id": "node-b",
                "type": "ChatOutput",
                "node": {"display_name": "Chat Output", "lf_version": "1.7.0", "template": {}},
            },
        }
        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE_WITH_VERSION, node_b], "edges": []}}
        result = self._make_result()
        with patch("lfx.cli.validation.core._get_lf_version", return_value="1.9.0"):
            _check_version_mismatch(flow, result)
        assert len(result.warnings) == 2

    def test_langflow_not_installed_skips_check(self):
        """If Langflow is not installed, version check is skipped silently."""
        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE_WITH_VERSION], "edges": []}}
        result = self._make_result()
        with patch("lfx.cli.validation.core._get_lf_version", return_value=None):
            _check_version_mismatch(flow, result)
        assert not result.warnings

    def test_skip_version_check_flag_suppresses_warning(self, tmp_path):
        """--skip-version-check prevents version warnings from appearing."""
        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE_WITH_VERSION], "edges": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        with patch("lfx.cli.validation.core._get_lf_version", return_value="1.9.0"):
            result = validate_flow_file(p, level=1, skip_components=True, skip_version_check=True)
        assert not result.warnings

    def test_version_warning_strict_mode_causes_exit_1(self, tmp_path):
        """Version mismatch warning + --strict → exit 1."""
        import typer

        flow = {**_MINIMAL_VALID, "data": {"nodes": [_NODE_WITH_VERSION], "edges": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        with (
            patch("lfx.cli.validation.core._get_lf_version", return_value="1.9.0"),
            pytest.raises(typer.Exit) as exc_info,
        ):
            validate_command(
                flow_paths=[str(p)],
                level=1,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=False,
                skip_credentials=True,
                strict=True,
                verbose=False,
                output_format="text",
            )
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# Extended check: missing credentials
# ---------------------------------------------------------------------------


def _node_with_password_field(value: str | None = None, *, show: bool = True) -> dict:
    return {
        "id": "node-cred",
        "data": {
            "id": "node-cred",
            "type": "OpenAIModel",
            "node": {
                "display_name": "OpenAI",
                "template": {
                    "openai_api_key": {
                        "password": True,
                        "show": show,
                        "required": False,
                        "value": value,
                    }
                },
            },
        },
    }


class TestMissingCredentials:
    def _make_result(self) -> ValidationResult:
        return ValidationResult(path=Path("test.json"))

    def test_password_field_with_value_no_warning(self):
        """Password field that already has a value → no warning."""
        node = _node_with_password_field(value="sk-test")
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        result = self._make_result()
        _check_missing_credentials(flow, result)
        assert not result.warnings

    def test_password_field_no_value_no_env_warns(self, monkeypatch):
        """Password field with no value and no env var → warning."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        node = _node_with_password_field(value=None)
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        result = self._make_result()
        _check_missing_credentials(flow, result)
        assert len(result.warnings) == 1
        assert "openai_api_key" in result.warnings[0].message
        assert "OPENAI_API_KEY" in result.warnings[0].message

    def test_password_field_env_var_set_no_warning(self, monkeypatch):
        """Env var matching field name → no warning."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        node = _node_with_password_field(value=None)
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        result = self._make_result()
        _check_missing_credentials(flow, result)
        assert not result.warnings

    def test_hidden_password_field_skipped(self, monkeypatch):
        """Password fields with show=False are not surfaced."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        node = _node_with_password_field(value=None, show=False)
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        result = self._make_result()
        _check_missing_credentials(flow, result)
        assert not result.warnings

    def test_password_field_with_incoming_edge_no_warning(self):
        """Password field covered by an incoming edge → no warning."""
        node = _node_with_password_field(value=None)
        edge = {
            "source": "other-node",
            "target": "node-cred",
            "data": {
                "targetHandle": {"fieldName": "openai_api_key", "type": "str"},
                "sourceHandle": {"output_types": ["str"]},
            },
        }
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": [edge]}}
        result = self._make_result()
        _check_missing_credentials(flow, result)
        assert not result.warnings

    def test_non_password_field_not_checked(self, monkeypatch):
        """Regular (non-password) fields are ignored even when empty."""
        monkeypatch.delenv("MY_PARAM", raising=False)
        node = {
            "id": "node-text",
            "data": {
                "id": "node-text",
                "type": "TextInput",
                "node": {
                    "display_name": "Text",
                    "template": {
                        "my_param": {
                            "password": False,
                            "show": True,
                            "required": False,
                            "value": None,
                        }
                    },
                },
            },
        }
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        result = self._make_result()
        _check_missing_credentials(flow, result)
        assert not result.warnings

    def test_display_password_field_also_triggers_warning(self, monkeypatch):
        """Fields with display_password=True are also treated as credentials."""
        monkeypatch.delenv("SECRET_TOKEN", raising=False)
        node = {
            "id": "node-dp",
            "data": {
                "id": "node-dp",
                "type": "CustomComp",
                "node": {
                    "display_name": "Custom",
                    "template": {
                        "secret_token": {
                            "display_password": True,
                            "show": True,
                            "required": False,
                            "value": None,
                        }
                    },
                },
            },
        }
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        result = self._make_result()
        _check_missing_credentials(flow, result)
        assert len(result.warnings) == 1

    def test_skip_credentials_flag_suppresses_warning(self, tmp_path, monkeypatch):
        """--skip-credentials prevents missing-credential warnings."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        node = _node_with_password_field(value=None)
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        result = validate_flow_file(p, level=4, skip_components=True, skip_edge_types=True, skip_credentials=True)
        cred_warnings = [w for w in result.warnings if "openai_api_key" in w.message]
        assert not cred_warnings

    def test_credential_warning_strict_causes_exit_1(self, tmp_path, monkeypatch):
        """Missing credential warning + --strict → exit 1."""
        import typer

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        node = _node_with_password_field(value=None)
        flow = {**_MINIMAL_VALID, "data": {"nodes": [node], "edges": []}}
        p = _write_flow(tmp_path, "flow.json", flow)
        with pytest.raises(typer.Exit) as exc_info:
            validate_command(
                flow_paths=[str(p)],
                level=4,
                skip_components=True,
                skip_edge_types=True,
                skip_required_inputs=True,
                skip_version_check=True,
                skip_credentials=False,
                strict=True,
                verbose=False,
                output_format="text",
            )
        assert exc_info.value.exit_code == 1
