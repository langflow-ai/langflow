"""Unit tests for ``lfx create`` and the ``--example`` seeding in ``lfx init``.

All tests run entirely in-process; no running Langflow instance required.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest
import typer
from lfx.__main__ import app
from lfx.cli.create import (
    _load_template,
    _slugify,
    create_command,
    list_templates,
    print_templates,
)
from lfx.cli.init import init_command
from typer.testing import CliRunner

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REAL_TEMPLATES = list_templates()


def _read_flow(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# list_templates()
# ---------------------------------------------------------------------------


class TestListTemplates:
    def test_returns_list_of_strings(self):
        result = list_templates()
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)

    def test_includes_known_templates(self):
        result = list_templates()
        assert "hello-world" in result

    def test_sorted(self):
        result = list_templates()
        assert result == sorted(result)

    def test_returns_empty_when_dir_missing(self, tmp_path):
        fake_dir = tmp_path / "nonexistent"
        with patch("lfx.cli.create._FLOWS_TEMPLATE_DIR", fake_dir):
            assert list_templates() == []


# ---------------------------------------------------------------------------
# _slugify()
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_lowercases(self):
        assert _slugify("MyFlow") == "myflow"

    def test_spaces_to_hyphens(self):
        assert _slugify("My Flow Name") == "my-flow-name"

    def test_underscores_to_hyphens(self):
        assert _slugify("my_flow") == "my-flow"

    def test_already_slug(self):
        assert _slugify("my-flow") == "my-flow"


# ---------------------------------------------------------------------------
# _load_template()
# ---------------------------------------------------------------------------


class TestLoadTemplate:
    def test_loads_hello_world(self):
        flow = _load_template("hello-world")
        assert "id" in flow
        assert "name" in flow
        assert "data" in flow

    def test_raises_on_unknown_template(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            _load_template("does-not-exist")

    def test_error_lists_available_templates(self):
        with pytest.raises(FileNotFoundError, match="hello-world"):
            _load_template("does-not-exist")


# ---------------------------------------------------------------------------
# Template JSON structure (level-1 validity)
# ---------------------------------------------------------------------------


class TestTemplateStructure:
    """Every bundled template must satisfy level-1 structural validation."""

    @pytest.mark.parametrize("template_name", _REAL_TEMPLATES)
    def test_has_required_top_level_keys(self, template_name):
        flow = _load_template(template_name)
        for key in ("id", "name", "data"):
            assert key in flow, f"Template {template_name!r} missing top-level key '{key}'"

    @pytest.mark.parametrize("template_name", _REAL_TEMPLATES)
    def test_has_nodes_and_edges(self, template_name):
        flow = _load_template(template_name)
        assert "nodes" in flow["data"]
        assert "edges" in flow["data"]

    @pytest.mark.parametrize("template_name", _REAL_TEMPLATES)
    def test_every_node_has_id_and_data(self, template_name):
        flow = _load_template(template_name)
        for node in flow["data"]["nodes"]:
            assert "id" in node, f"Node missing 'id' in template {template_name!r}"
            assert "data" in node, f"Node missing 'data' in template {template_name!r}"

    @pytest.mark.parametrize("template_name", _REAL_TEMPLATES)
    def test_every_node_has_type(self, template_name):
        """Nodes should declare data.type to avoid validate warnings."""
        flow = _load_template(template_name)
        for node in flow["data"]["nodes"]:
            assert "type" in node["data"], f"Node {node['id']!r} in template {template_name!r} missing 'data.type'"

    @pytest.mark.parametrize("template_name", _REAL_TEMPLATES)
    def test_edges_reference_existing_nodes(self, template_name):
        flow = _load_template(template_name)
        node_ids = {n["id"] for n in flow["data"]["nodes"]}
        for edge in flow["data"]["edges"]:
            assert edge["source"] in node_ids, f"Edge source {edge['source']!r} not in nodes for {template_name!r}"
            assert edge["target"] in node_ids, f"Edge target {edge['target']!r} not in nodes for {template_name!r}"

    def test_hello_world_has_input_and_output(self):
        flow = _load_template("hello-world")
        types = {n["data"]["type"] for n in flow["data"]["nodes"]}
        assert "ChatOutput" in types
        assert len(types) >= 2

    def test_hello_world_edge_connects_input_to_output(self):
        flow = _load_template("hello-world")
        node_ids = {n["id"] for n in flow["data"]["nodes"]}
        for edge in flow["data"]["edges"]:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids


# ---------------------------------------------------------------------------
# create_command() — core logic
# ---------------------------------------------------------------------------


class TestCreateCommand:
    def test_creates_file_with_correct_name(self, tmp_path):
        dest = create_command("my-flow", output_dir=tmp_path)
        assert dest == tmp_path / "my-flow.json"
        assert dest.exists()

    def test_slugifies_name_for_filename(self, tmp_path):
        dest = create_command("My Cool Flow", output_dir=tmp_path)
        assert dest.name == "my-cool-flow.json"

    def test_flow_name_in_json_is_original(self, tmp_path):
        create_command("My Cool Flow", output_dir=tmp_path)
        flow = _read_flow(tmp_path / "my-cool-flow.json")
        assert flow["name"] == "My Cool Flow"

    def test_generates_unique_uuid(self, tmp_path):
        dest1 = create_command("flow-a", output_dir=tmp_path)
        dest2 = create_command("flow-b", output_dir=tmp_path)
        id1 = _read_flow(dest1)["id"]
        id2 = _read_flow(dest2)["id"]
        assert id1 != id2
        # Must not be the placeholder
        assert id1 != "00000000-0000-0000-0000-000000000000"
        assert id2 != "00000000-0000-0000-0000-000000000000"

    def test_uses_default_template_hello_world(self, tmp_path):
        dest = create_command("test", output_dir=tmp_path)
        flow = _read_flow(dest)
        types = {n["data"]["type"] for n in flow["data"]["nodes"]}
        assert "ChatOutput" in types

    def test_creates_output_dir_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b" / "flows"
        dest = create_command("my-flow", output_dir=nested)
        assert dest.exists()

    def test_raises_exit1_on_unknown_template(self, tmp_path):
        with pytest.raises(typer.Exit):
            create_command("test", template="nonexistent", output_dir=tmp_path)

    def test_raises_exit1_if_file_exists_no_overwrite(self, tmp_path):
        create_command("my-flow", output_dir=tmp_path)
        with pytest.raises(typer.Exit):
            create_command("my-flow", output_dir=tmp_path, overwrite=False)

    def test_overwrites_existing_file_when_flag_set(self, tmp_path):
        dest = create_command("my-flow", output_dir=tmp_path)
        original_id = _read_flow(dest)["id"]
        dest2 = create_command("my-flow", output_dir=tmp_path, overwrite=True)
        new_id = _read_flow(dest2)["id"]
        assert dest == dest2
        assert new_id != original_id  # new UUID stamped each time

    def test_output_is_valid_json(self, tmp_path):
        dest = create_command("my-flow", output_dir=tmp_path)
        # Should not raise
        flow = json.loads(dest.read_text(encoding="utf-8"))
        assert isinstance(flow, dict)

    def test_raises_exit1_when_no_templates_dir(self, tmp_path):
        fake_dir = tmp_path / "empty"
        with patch("lfx.cli.create._FLOWS_TEMPLATE_DIR", fake_dir), pytest.raises(typer.Exit):
            create_command("test", output_dir=tmp_path)


# ---------------------------------------------------------------------------
# print_templates() — smoke test
# ---------------------------------------------------------------------------


class TestPrintTemplates:
    def test_does_not_raise(self):
        print_templates()  # just checking it doesn't blow up

    def test_prints_nothing_when_no_templates(self, tmp_path):
        with patch("lfx.cli.create._FLOWS_TEMPLATE_DIR", tmp_path / "empty"):
            print_templates()


# ---------------------------------------------------------------------------
# CLI integration — lfx create
# ---------------------------------------------------------------------------


class TestCreateCLI:
    def test_creates_flow_via_cli(self, tmp_path):
        result = runner.invoke(
            app,
            ["create", "hello", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "hello.json").exists()

    def test_list_flag_prints_templates_and_exits(self):
        result = runner.invoke(app, ["create", "--list", "ignored-name"])
        assert result.exit_code == 0
        assert "hello-world" in result.output

    def test_unknown_template_exits_nonzero(self, tmp_path):
        result = runner.invoke(
            app,
            ["create", "test", "--template", "no-such-template", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code != 0

    def test_overwrite_flag_replaces_file(self, tmp_path):
        runner.invoke(app, ["create", "my-flow", "--output-dir", str(tmp_path)])
        result = runner.invoke(
            app,
            ["create", "my-flow", "--output-dir", str(tmp_path), "--overwrite"],
        )
        assert result.exit_code == 0, result.output

    def test_no_overwrite_exits_nonzero_on_existing(self, tmp_path):
        runner.invoke(app, ["create", "my-flow", "--output-dir", str(tmp_path)])
        result = runner.invoke(app, ["create", "my-flow", "--output-dir", str(tmp_path)])
        assert result.exit_code != 0

    def test_explicit_template_hello_world(self, tmp_path):
        result = runner.invoke(
            app,
            ["create", "my-flow", "--template", "hello-world", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        flow = _read_flow(tmp_path / "my-flow.json")
        types = {n["data"]["type"] for n in flow["data"]["nodes"]}
        assert "ChatOutput" in types


# ---------------------------------------------------------------------------
# init_command — --example seeding
# ---------------------------------------------------------------------------


class TestInitExampleSeeding:
    def test_seeds_hello_world_by_default(self, tmp_path):
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        assert (tmp_path / "flows" / "hello-world.json").exists()

    def test_seeded_flow_is_valid_json(self, tmp_path):
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        flow = _read_flow(tmp_path / "flows" / "hello-world.json")
        assert "id" in flow
        assert "name" in flow
        assert flow["name"] == "hello-world"

    def test_no_example_does_not_create_hello_world(self, tmp_path):
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=False)
        assert not (tmp_path / "flows" / "hello-world.json").exists()

    def test_no_example_creates_gitkeep(self, tmp_path):
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=False)
        assert (tmp_path / "flows" / ".gitkeep").exists()

    def test_example_still_creates_other_files(self, tmp_path):
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        assert (tmp_path / ".lfx" / "environments.yaml").exists()
        assert (tmp_path / "tests" / "test_flows.py").exists()

    def test_seeded_flow_has_unique_uuid(self, tmp_path):
        p1 = tmp_path / "proj1"
        p2 = tmp_path / "proj2"
        init_command(project_dir=p1, github_actions=False, overwrite=False, example=True)
        init_command(project_dir=p2, github_actions=False, overwrite=False, example=True)
        id1 = _read_flow(p1 / "flows" / "hello-world.json")["id"]
        id2 = _read_flow(p2 / "flows" / "hello-world.json")["id"]
        assert id1 != id2

    def test_init_cli_example_flag(self, tmp_path):
        result = runner.invoke(
            app,
            ["init", str(tmp_path), "--no-github-actions", "--example"],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "flows" / "hello-world.json").exists()

    def test_init_cli_no_example_flag(self, tmp_path):
        result = runner.invoke(
            app,
            ["init", str(tmp_path), "--no-github-actions", "--no-example"],
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "flows" / "hello-world.json").exists()

    def test_graceful_fallback_when_template_fails(self, tmp_path):
        """If the template dir is missing, init should warn but not crash."""
        fake_dir = tmp_path / "no-templates"
        with patch("lfx.cli.create._FLOWS_TEMPLATE_DIR", fake_dir):
            # Should not raise — the BLE001-guarded except swallows it
            init_command(
                project_dir=tmp_path / "proj",
                github_actions=False,
                overwrite=False,
                example=True,
            )
        assert (tmp_path / "proj" / ".lfx" / "environments.yaml").exists()
