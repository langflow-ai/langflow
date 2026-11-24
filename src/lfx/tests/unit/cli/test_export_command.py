"""Unit tests for lfx export -- export_command and helpers.

All tests run entirely in-process; no real Langflow instance or SDK required.
The SDK module is replaced wholesale with MagicMock so only the export logic
(file normalization, output routing, remote pull, project export) is under test.
"""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

import json
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import typer

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_BASE_URL = "http://langflow.test"
_API_KEY = "test-api-key-export"  # pragma: allowlist secret
_FLOW_ID = "aaaaaaaa-0000-0000-0000-000000000001"
_PROJECT_ID = "bbbbbbbb-0000-0000-0000-000000000001"

_FLOW_DICT: dict = {
    "id": _FLOW_ID,
    "name": "My Test Flow",
    "data": {"nodes": [], "edges": []},
}

_NORMALIZED_JSON = json.dumps(_FLOW_DICT, indent=2)


# ---------------------------------------------------------------------------
# Fake SDK helpers
# ---------------------------------------------------------------------------


def _make_flow_obj(name: str = "My Test Flow", flow_id: str = _FLOW_ID) -> MagicMock:
    """Return a mock flow object with .name, .model_dump()."""
    obj = MagicMock()
    obj.name = name
    obj.id = flow_id
    obj.model_dump.return_value = {"id": flow_id, "name": name, "data": {}}
    return obj


def _make_project_obj(
    name: str = "My Project",
    project_id: str = _PROJECT_ID,
    flows: list | None = None,
) -> MagicMock:
    obj = MagicMock()
    obj.name = name
    obj.id = project_id
    obj.flows = flows if flows is not None else [_make_flow_obj()]
    return obj


def _make_client_mock(
    flow_obj: MagicMock | None = None,
    project_obj: MagicMock | None = None,
) -> MagicMock:
    client = MagicMock()
    client.get_flow.return_value = flow_obj if flow_obj is not None else _make_flow_obj()
    client.get_project.return_value = project_obj if project_obj is not None else _make_project_obj()
    return client


def _make_sdk_mock(client_mock: MagicMock | None = None) -> MagicMock:
    """Return a mock langflow_sdk module wired up for export tests."""
    if client_mock is None:
        client_mock = _make_client_mock()
    sdk = MagicMock()
    sdk.Client.return_value = client_mock
    sdk.normalize_flow_file.return_value = _FLOW_DICT
    sdk.normalize_flow.return_value = _FLOW_DICT
    sdk.flow_to_json.return_value = _NORMALIZED_JSON
    return sdk


def _make_env_cfg(url: str = _BASE_URL, api_key: str | None = _API_KEY) -> MagicMock:
    env_cfg = MagicMock()
    env_cfg.url = url
    env_cfg.api_key = api_key
    return env_cfg


def _run_export(
    flow_paths: list[str],
    *,
    output: str | None = None,
    output_dir: str | None = None,
    env: str | None = None,
    flow_id: str | None = None,
    project_id: str | None = None,
    environments_file: str | None = None,
    target: str | None = _BASE_URL,
    api_key: str | None = _API_KEY,
    in_place: bool = False,
    strip_volatile: bool = False,
    strip_secrets: bool = False,
    code_as_lines: bool = False,
    strip_node_volatile: bool = False,
    indent: int = 2,
    sdk_mock: MagicMock | None = None,
    env_cfg: MagicMock | None = None,
) -> None:
    """Invoke export_command with a mocked SDK and optional mocked env."""
    from lfx.cli.export import export_command

    mock = sdk_mock if sdk_mock is not None else _make_sdk_mock()
    resolved_env = env_cfg if env_cfg is not None else _make_env_cfg()

    with (
        patch("lfx.cli.export.load_sdk", return_value=mock),
        patch("lfx.config.resolve_environment", return_value=resolved_env),
    ):
        export_command(
            flow_paths=flow_paths,
            output=output,
            output_dir=output_dir,
            env=env,
            flow_id=flow_id,
            project_id=project_id,
            environments_file=environments_file,
            target=target,
            api_key=api_key,
            in_place=in_place,
            strip_volatile=strip_volatile,
            strip_secrets=strip_secrets,
            code_as_lines=code_as_lines,
            strip_node_volatile=strip_node_volatile,
            indent=indent,
        )


# ---------------------------------------------------------------------------
# _safe_filename
# ---------------------------------------------------------------------------


class TestSafeFilename:
    def test_alphanumeric_unchanged(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("MyFlow123") == "MyFlow123"

    def test_spaces_replaced_with_underscores(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("My Test Flow") == "My_Test_Flow"

    def test_special_chars_replaced_with_underscores(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("flow/name:with*special?chars")
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result
        assert "?" not in result

    def test_leading_trailing_spaces_stripped(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("  flow name  ")
        assert not result.startswith("_")
        assert not result.endswith("_")
        assert "flow_name" in result

    def test_hyphens_and_underscores_preserved(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("my-flow_name")
        assert result == "my-flow_name"

    def test_empty_string(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("")
        assert result == ""

    def test_unicode_chars_replaced(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("flow\u2019s name")
        assert "\u2019" not in result

    def test_all_spaces_produces_underscores(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("a b c")
        assert result == "a_b_c"


# ---------------------------------------------------------------------------
# _write_flow
# ---------------------------------------------------------------------------


class TestWriteFlow:
    def test_in_place_writes_to_source_path(self, tmp_path):
        from lfx.cli.export import _write_flow

        src = tmp_path / "flow.json"
        src.write_text("{}", encoding="utf-8")
        sdk = _make_sdk_mock()
        result = _write_flow(_FLOW_DICT, sdk=sdk, output=None, in_place=True, source_path=src, indent=2)
        assert result == src
        assert src.read_text(encoding="utf-8") == _NORMALIZED_JSON

    def test_in_place_returns_source_path(self, tmp_path):
        from lfx.cli.export import _write_flow

        src = tmp_path / "flow.json"
        src.write_text("{}", encoding="utf-8")
        sdk = _make_sdk_mock()
        result = _write_flow(_FLOW_DICT, sdk=sdk, output=None, in_place=True, source_path=src, indent=2)
        assert result == src

    def test_output_given_writes_to_output(self, tmp_path):
        from lfx.cli.export import _write_flow

        out = tmp_path / "out.json"
        sdk = _make_sdk_mock()
        result = _write_flow(_FLOW_DICT, sdk=sdk, output=out, in_place=False, source_path=None, indent=2)
        assert result == out
        assert out.read_text(encoding="utf-8") == _NORMALIZED_JSON

    def test_output_given_returns_output_path(self, tmp_path):
        from lfx.cli.export import _write_flow

        out = tmp_path / "result.json"
        sdk = _make_sdk_mock()
        result = _write_flow(_FLOW_DICT, sdk=sdk, output=out, in_place=False, source_path=None, indent=2)
        assert result == out

    def test_no_output_no_in_place_writes_to_stdout(self):
        from lfx.cli.export import _write_flow

        sdk = _make_sdk_mock()
        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            _write_flow(_FLOW_DICT, sdk=sdk, output=None, in_place=False, source_path=None, indent=2)
        assert _NORMALIZED_JSON in captured.getvalue()

    def test_no_output_no_in_place_returns_none(self):
        from lfx.cli.export import _write_flow

        sdk = _make_sdk_mock()
        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            result = _write_flow(_FLOW_DICT, sdk=sdk, output=None, in_place=False, source_path=None, indent=2)
        assert result is None

    def test_in_place_false_with_source_path_uses_output(self, tmp_path):
        from lfx.cli.export import _write_flow

        src = tmp_path / "src.json"
        src.write_text("{}", encoding="utf-8")
        out = tmp_path / "dest.json"
        sdk = _make_sdk_mock()
        result = _write_flow(_FLOW_DICT, sdk=sdk, output=out, in_place=False, source_path=src, indent=2)
        assert result == out
        assert out.exists()

    def test_sdk_flow_to_json_called_with_indent(self, tmp_path):
        from lfx.cli.export import _write_flow

        out = tmp_path / "out.json"
        sdk = _make_sdk_mock()
        _write_flow(_FLOW_DICT, sdk=sdk, output=out, in_place=False, source_path=None, indent=4)
        sdk.flow_to_json.assert_called_once_with(_FLOW_DICT, indent=4)


# ---------------------------------------------------------------------------
# Local mode
# ---------------------------------------------------------------------------


class TestExportCommandLocalMode:
    def test_single_file_to_stdout(self, tmp_path):
        src = tmp_path / "flow.json"
        src.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        sdk = _make_sdk_mock()
        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            _run_export([str(src)], sdk_mock=sdk)
        sdk.normalize_flow_file.assert_called_once()

    def test_single_file_with_output_writes_file(self, tmp_path):
        src = tmp_path / "flow.json"
        src.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        out = tmp_path / "exported.json"
        sdk = _make_sdk_mock()
        _run_export([str(src)], output=str(out), sdk_mock=sdk)
        assert out.exists()
        assert out.read_text(encoding="utf-8") == _NORMALIZED_JSON

    def test_single_file_in_place_overwrites_source(self, tmp_path):
        src = tmp_path / "flow.json"
        src.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        sdk = _make_sdk_mock()
        _run_export([str(src)], in_place=True, sdk_mock=sdk)
        assert src.read_text(encoding="utf-8") == _NORMALIZED_JSON

    def test_multiple_files_processed(self, tmp_path):
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        f2.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        sdk = _make_sdk_mock()
        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            _run_export([str(f1), str(f2)], sdk_mock=sdk)
        assert sdk.normalize_flow_file.call_count == 2

    def test_multiple_files_with_output_raises_exit_1(self, tmp_path):
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        f2.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        out = tmp_path / "out.json"
        sdk = _make_sdk_mock()
        with pytest.raises(typer.Exit) as exc_info:
            _run_export([str(f1), str(f2)], output=str(out), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_file_not_found_raises_exit_1(self, tmp_path):
        sdk = _make_sdk_mock()
        with pytest.raises(typer.Exit) as exc_info:
            _run_export([str(tmp_path / "missing.json")], sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_normalize_raises_exits_1(self, tmp_path):
        src = tmp_path / "flow.json"
        src.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        sdk = _make_sdk_mock()
        sdk.normalize_flow_file.side_effect = ValueError("bad flow")
        with pytest.raises(typer.Exit) as exc_info:
            _run_export([str(src)], sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_no_flow_paths_raises_exit_1(self):
        sdk = _make_sdk_mock()
        with pytest.raises(typer.Exit) as exc_info:
            _run_export([], sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_normalize_kwargs_passed_correctly(self, tmp_path):
        src = tmp_path / "flow.json"
        src.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        sdk = _make_sdk_mock()
        captured = StringIO()
        with patch.object(sys, "stdout", captured):
            _run_export(
                [str(src)],
                strip_volatile=True,
                strip_secrets=True,
                code_as_lines=True,
                strip_node_volatile=True,
                sdk_mock=sdk,
            )
        call_kwargs = sdk.normalize_flow_file.call_args.kwargs
        assert call_kwargs["strip_volatile"] is True
        assert call_kwargs["strip_secrets"] is True
        assert call_kwargs["code_as_lines"] is True
        assert call_kwargs["strip_node_volatile"] is True

    def test_indent_passed_to_flow_to_json(self, tmp_path):
        src = tmp_path / "flow.json"
        src.write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        out = tmp_path / "out.json"
        sdk = _make_sdk_mock()
        _run_export([str(src)], output=str(out), indent=4, sdk_mock=sdk)
        sdk.flow_to_json.assert_called_with(sdk.normalize_flow_file.return_value, indent=4)


# ---------------------------------------------------------------------------
# Remote mode — single flow by ID
# ---------------------------------------------------------------------------


class TestExportCommandRemoteFlowId:
    def test_missing_env_and_target_raises_exit_1(self):
        sdk = _make_sdk_mock()
        from lfx.cli.export import export_command

        with patch("lfx.cli.export.load_sdk", return_value=sdk), pytest.raises(typer.Exit) as exc_info:
            export_command(
                flow_paths=[],
                output=None,
                output_dir=None,
                env=None,
                flow_id=_FLOW_ID,
                project_id=None,
                environments_file=None,
                target=None,
                api_key=None,
                in_place=False,
                strip_volatile=False,
                strip_secrets=False,
                code_as_lines=False,
                strip_node_volatile=False,
                indent=2,
            )
        assert exc_info.value.exit_code == 1

    def test_flow_id_fetches_and_writes_to_output_dir(self, tmp_path):
        flow_obj = _make_flow_obj(name="Fetched Flow")
        client = _make_client_mock(flow_obj=flow_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            flow_id=_FLOW_ID,
            env="staging",
            output_dir=str(tmp_path),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        client.get_flow.assert_called_once()
        written = list(tmp_path.glob("*.json"))
        assert len(written) == 1

    def test_flow_id_filename_uses_safe_name(self, tmp_path):
        flow_obj = _make_flow_obj(name="My Flow: Special!")
        client = _make_client_mock(flow_obj=flow_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            flow_id=_FLOW_ID,
            env="staging",
            output_dir=str(tmp_path),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        written = list(tmp_path.glob("*.json"))
        assert len(written) == 1
        assert ":" not in written[0].name
        assert "!" not in written[0].name

    def test_flow_id_creates_output_dir_if_missing(self, tmp_path):
        dest = tmp_path / "new_dir" / "subdir"
        flow_obj = _make_flow_obj()
        client = _make_client_mock(flow_obj=flow_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            flow_id=_FLOW_ID,
            env="staging",
            output_dir=str(dest),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        assert dest.exists()

    def test_flow_id_uses_cwd_when_output_dir_not_specified(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        flow_obj = _make_flow_obj(name="CwdFlow")
        client = _make_client_mock(flow_obj=flow_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            flow_id=_FLOW_ID,
            env="staging",
            output_dir=None,
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        written = list(tmp_path.glob("*.json"))
        assert len(written) == 1

    def test_config_error_raises_exit_1(self, tmp_path):
        from lfx.cli.export import export_command
        from lfx.config import ConfigError

        sdk = _make_sdk_mock()
        with (
            patch("lfx.cli.export.load_sdk", return_value=sdk),
            patch("lfx.config.resolve_environment", side_effect=ConfigError("bad config")),
            pytest.raises(typer.Exit) as exc_info,
        ):
            export_command(
                flow_paths=[],
                output=None,
                output_dir=str(tmp_path),
                env="staging",
                flow_id=_FLOW_ID,
                project_id=None,
                environments_file=None,
                target=None,
                api_key=None,
                in_place=False,
                strip_volatile=False,
                strip_secrets=False,
                code_as_lines=False,
                strip_node_volatile=False,
                indent=2,
            )
        assert exc_info.value.exit_code == 1

    def test_client_constructed_with_env_credentials(self, tmp_path):
        flow_obj = _make_flow_obj()
        client = _make_client_mock(flow_obj=flow_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg(url=_BASE_URL, api_key=_API_KEY)
        _run_export(
            [],
            flow_id=_FLOW_ID,
            env="staging",
            output_dir=str(tmp_path),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        sdk.Client.assert_called_once_with(base_url=_BASE_URL, api_key=_API_KEY)

    def test_normalize_flow_called_with_kwargs(self, tmp_path):
        flow_obj = _make_flow_obj()
        client = _make_client_mock(flow_obj=flow_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            flow_id=_FLOW_ID,
            env="staging",
            output_dir=str(tmp_path),
            strip_volatile=True,
            strip_secrets=True,
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        call_kwargs = sdk.normalize_flow.call_args.kwargs
        assert call_kwargs["strip_volatile"] is True
        assert call_kwargs["strip_secrets"] is True


# ---------------------------------------------------------------------------
# Remote mode — project
# ---------------------------------------------------------------------------


class TestExportCommandRemoteProject:
    def test_project_exports_all_flows(self, tmp_path):
        flows = [_make_flow_obj(name=f"Flow {i}", flow_id=f"aaaaaaaa-0000-0000-0000-{i:012d}") for i in range(3)]
        project_obj = _make_project_obj(name="Test Project", flows=flows)
        client = _make_client_mock(project_obj=project_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            project_id=_PROJECT_ID,
            env="staging",
            output_dir=str(tmp_path),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        client.get_project.assert_called_once()
        written = list(tmp_path.glob("*.json"))
        assert len(written) == 3

    def test_project_creates_dir_named_after_project_when_output_dir_not_given(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        project_obj = _make_project_obj(name="My Project")
        client = _make_client_mock(project_obj=project_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            project_id=_PROJECT_ID,
            env="staging",
            output_dir=None,
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        from lfx.cli.common import safe_filename as _safe_filename

        expected_dir = tmp_path / _safe_filename("My Project")
        assert expected_dir.exists()

    def test_project_writes_json_for_each_flow(self, tmp_path):
        flows = [_make_flow_obj(name="Alpha"), _make_flow_obj(name="Beta")]
        project_obj = _make_project_obj(flows=flows)
        client = _make_client_mock(project_obj=project_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            project_id=_PROJECT_ID,
            env="staging",
            output_dir=str(tmp_path),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        assert sdk.normalize_flow.call_count == 2
        assert sdk.flow_to_json.call_count == 2

    def test_project_config_error_raises_exit_1(self, tmp_path):
        from lfx.cli.export import export_command
        from lfx.config import ConfigError

        sdk = _make_sdk_mock()
        with (
            patch("lfx.cli.export.load_sdk", return_value=sdk),
            patch("lfx.config.resolve_environment", side_effect=ConfigError("cfg error")),
            pytest.raises(typer.Exit) as exc_info,
        ):
            export_command(
                flow_paths=[],
                output=None,
                output_dir=str(tmp_path),
                env="staging",
                flow_id=None,
                project_id=_PROJECT_ID,
                environments_file=None,
                target=None,
                api_key=None,
                in_place=False,
                strip_volatile=False,
                strip_secrets=False,
                code_as_lines=False,
                strip_node_volatile=False,
                indent=2,
            )
        assert exc_info.value.exit_code == 1

    def test_project_missing_env_and_target_raises_exit_1(self):
        from lfx.cli.export import export_command

        sdk = _make_sdk_mock()
        with patch("lfx.cli.export.load_sdk", return_value=sdk), pytest.raises(typer.Exit) as exc_info:
            export_command(
                flow_paths=[],
                output=None,
                output_dir=None,
                env=None,
                flow_id=None,
                project_id=_PROJECT_ID,
                environments_file=None,
                target=None,
                api_key=None,
                in_place=False,
                strip_volatile=False,
                strip_secrets=False,
                code_as_lines=False,
                strip_node_volatile=False,
                indent=2,
            )
        assert exc_info.value.exit_code == 1

    def test_project_empty_flows_exports_zero_files(self, tmp_path):
        project_obj = _make_project_obj(flows=[])
        client = _make_client_mock(project_obj=project_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            project_id=_PROJECT_ID,
            env="staging",
            output_dir=str(tmp_path),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        written = list(tmp_path.glob("*.json"))
        assert len(written) == 0

    def test_project_flow_filenames_are_safe(self, tmp_path):
        flows = [_make_flow_obj(name="Flow: with/special*chars")]
        project_obj = _make_project_obj(flows=flows)
        client = _make_client_mock(project_obj=project_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        _run_export(
            [],
            project_id=_PROJECT_ID,
            env="staging",
            output_dir=str(tmp_path),
            sdk_mock=sdk,
            env_cfg=env_cfg,
        )
        written = list(tmp_path.glob("*.json"))
        assert len(written) == 1
        assert ":" not in written[0].name
        assert "/" not in written[0].name
        assert "*" not in written[0].name

    def test_project_target_used_without_env_name(self, tmp_path):
        """--target alone (no --env) is sufficient for project remote mode."""
        flows = [_make_flow_obj()]
        project_obj = _make_project_obj(flows=flows)
        client = _make_client_mock(project_obj=project_obj)
        sdk = _make_sdk_mock(client_mock=client)
        env_cfg = _make_env_cfg()
        from lfx.cli.export import export_command

        with (
            patch("lfx.cli.export.load_sdk", return_value=sdk),
            patch("lfx.config.resolve_environment", return_value=env_cfg),
        ):
            export_command(
                flow_paths=[],
                output=None,
                output_dir=str(tmp_path),
                env=None,
                flow_id=None,
                project_id=_PROJECT_ID,
                environments_file=None,
                target=_BASE_URL,
                api_key=_API_KEY,
                in_place=False,
                strip_volatile=False,
                strip_secrets=False,
                code_as_lines=False,
                strip_node_volatile=False,
                indent=2,
            )
        client.get_project.assert_called_once()
