"""Unit tests for lfx pull -- pull_command and helpers.

All tests run entirely in-process; no real Langflow instance or SDK required.
The SDK module is replaced wholesale with MagicMock so only the pull logic
(flow fetching, file writing, project resolution, result rendering)
is under test.
"""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
import typer

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_BASE_URL = "http://langflow.test"
_API_KEY = "test-key"  # pragma: allowlist secret
_FLOW_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
_FLOW_ID_2 = UUID("aaaaaaaa-0000-0000-0000-000000000002")
_PROJECT_ID = UUID("bbbbbbbb-0000-0000-0000-000000000001")

_FLOW_DICT: dict = {
    "id": str(_FLOW_ID),
    "name": "My Flow",
    "data": {"nodes": [], "edges": []},
}

_FLOW_DICT_2: dict = {
    "id": str(_FLOW_ID_2),
    "name": "Second Flow",
    "data": {"nodes": [], "edges": []},
}

_FLOW_JSON = json.dumps(_FLOW_DICT, indent=2)
_FLOW_JSON_2 = json.dumps(_FLOW_DICT_2, indent=2)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _fake_env_config(
    url: str = _BASE_URL,
    api_key: str = _API_KEY,
    name: str = "local",
) -> MagicMock:
    """Return a MagicMock that looks like a resolved EnvironmentConfig."""
    cfg = MagicMock()
    cfg.url = url
    cfg.api_key = api_key
    cfg.name = name
    return cfg


def _fake_flow_obj(
    flow_id: UUID = _FLOW_ID,
    name: str = "My Flow",
    flow_dict: dict | None = None,
) -> MagicMock:
    """Return a MagicMock that looks like a langflow_sdk Flow object."""
    flow = MagicMock()
    flow.id = flow_id
    flow.name = name
    flow.model_dump.return_value = flow_dict if flow_dict is not None else _FLOW_DICT
    return flow


def _fake_project(
    name: str = "My Project",
    project_id: UUID = _PROJECT_ID,
    flows: list | None = None,
) -> MagicMock:
    """Return a MagicMock that looks like a langflow_sdk Project object."""
    proj = MagicMock()
    proj.name = name
    proj.id = project_id
    proj.flows = flows if flows is not None else []
    return proj


def _fake_project_summary(
    name: str = "My Project",
    project_id: UUID = _PROJECT_ID,
) -> SimpleNamespace:
    """Return a lightweight project summary like sdk.list_projects() provides."""
    return SimpleNamespace(name=name, id=project_id)


def _make_client_mock(flows: list | None = None) -> MagicMock:
    """Return a mock SDK client pre-configured for common pull scenarios."""
    client = MagicMock()
    client.list_flows.return_value = flows if flows is not None else []
    client.list_projects.return_value = []
    return client


def _make_sdk_mock(
    client_mock: MagicMock | None = None,
    flow_json: str | None = None,
) -> MagicMock:
    """Return a mock langflow_sdk module wired to client_mock."""
    if client_mock is None:
        client_mock = _make_client_mock()

    sdk = MagicMock()
    sdk.Client.return_value = client_mock
    sdk.normalize_flow.side_effect = lambda d, **_kw: d
    sdk.flow_to_json.return_value = flow_json if flow_json is not None else _FLOW_JSON
    return sdk


def _run_pull(
    *,
    tmp_path: Path | None = None,  # noqa: ARG001 — kept for call-site readability
    env: str | None = None,
    output_dir: str | None = None,
    flow_id: str | None = None,
    project: str | None = None,
    project_id: str | None = None,
    environments_file: str | None = None,
    strip_secrets: bool = False,
    indent: int = 2,
    sdk_mock: MagicMock | None = None,
    env_cfg: MagicMock | None = None,
) -> None:
    """Invoke pull_command with mocked SDK and env resolution."""
    from lfx.cli.pull import pull_command

    mock_sdk = sdk_mock if sdk_mock is not None else _make_sdk_mock()
    mock_cfg = env_cfg if env_cfg is not None else _fake_env_config()

    with (
        patch("lfx.cli.pull.load_sdk", return_value=mock_sdk),
        patch("lfx.config.resolve_environment", return_value=mock_cfg),
    ):
        pull_command(
            env=env,
            output_dir=output_dir,
            flow_id=flow_id,
            project=project,
            project_id=project_id,
            environments_file=environments_file,
            target=_BASE_URL,
            api_key=_API_KEY,
            strip_secrets=strip_secrets,
            indent=indent,
        )


# ---------------------------------------------------------------------------
# _safe_filename
# ---------------------------------------------------------------------------


class TestSafeFilename:
    def test_alphanumeric_passthrough(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("MyFlow123") == "MyFlow123"

    def test_spaces_become_underscores(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("My Flow") == "My_Flow"

    def test_multiple_spaces_become_underscores(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("a b c") == "a_b_c"

    def test_special_chars_become_underscores(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("flow@version#1!")
        assert "@" not in result
        assert "#" not in result
        assert "!" not in result

    def test_leading_whitespace_stripped(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("  My Flow") == "My_Flow"

    def test_trailing_whitespace_stripped(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("My Flow  ") == "My_Flow"

    def test_both_ends_stripped(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("  My Flow  ") == "My_Flow"

    def test_hyphens_preserved(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("my-flow") == "my-flow"

    def test_underscores_preserved(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("my_flow") == "my_flow"

    def test_empty_string_returns_empty(self):
        from lfx.cli.common import safe_filename as _safe_filename

        assert _safe_filename("") == ""

    def test_slash_becomes_underscore(self):
        from lfx.cli.common import safe_filename as _safe_filename

        result = _safe_filename("flows/version")
        assert "/" not in result


# ---------------------------------------------------------------------------
# _write_flow helper
# ---------------------------------------------------------------------------


class TestWriteFlow:
    def test_status_created_when_file_does_not_exist(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock()
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert result.status == "created"

    def test_status_updated_when_file_exists_with_different_content(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock(flow_json=_FLOW_JSON)
        # Write different content first
        (tmp_path / "My_Flow.json").write_text("old content", encoding="utf-8")
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert result.status == "updated"

    def test_status_unchanged_when_file_exists_with_same_content(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock(flow_json=_FLOW_JSON)
        # Write identical content first
        (tmp_path / "My_Flow.json").write_text(_FLOW_JSON, encoding="utf-8")
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert result.status == "unchanged"

    def test_status_error_when_normalize_raises(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock()
        sdk.normalize_flow.side_effect = RuntimeError("normalize failed")
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert result.status == "error"
        assert result.error is not None
        assert "normalize failed" in result.error

    def test_error_result_is_not_ok(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock()
        sdk.normalize_flow.side_effect = RuntimeError("boom")
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert result.ok is False

    def test_written_file_has_correct_content(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        expected_content = json.dumps(_FLOW_DICT, indent=4)
        sdk = _make_sdk_mock(flow_json=expected_content)
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=4)
        assert result.path.exists()
        assert result.path.read_text(encoding="utf-8") == expected_content

    def test_file_not_written_when_unchanged(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock(flow_json=_FLOW_JSON)
        out_path = tmp_path / "My_Flow.json"
        out_path.write_text(_FLOW_JSON, encoding="utf-8")
        mtime_before = out_path.stat().st_mtime
        _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert out_path.stat().st_mtime == mtime_before

    def test_result_contains_correct_flow_id(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj(flow_id=_FLOW_ID)
        sdk = _make_sdk_mock()
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert result.flow_id == _FLOW_ID

    def test_result_contains_correct_flow_name(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj(name="Special Flow")
        sdk = _make_sdk_mock()
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert result.flow_name == "Special Flow"

    def test_normalize_called_with_strip_secrets_true(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock()
        _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=True, indent=2)
        sdk.normalize_flow.assert_called_once()
        call_kwargs = sdk.normalize_flow.call_args.kwargs
        assert call_kwargs.get("strip_secrets") is True

    def test_normalize_called_with_strip_secrets_false(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock()
        _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        call_kwargs = sdk.normalize_flow.call_args.kwargs
        assert call_kwargs.get("strip_secrets") is False

    def test_flow_to_json_called_with_indent(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj()
        sdk = _make_sdk_mock()
        _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=4)
        sdk.flow_to_json.assert_called_once()
        call_kwargs = sdk.flow_to_json.call_args.kwargs
        assert call_kwargs.get("indent") == 4

    def test_error_result_has_dummy_path(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj(flow_id=_FLOW_ID)
        sdk = _make_sdk_mock()
        sdk.normalize_flow.side_effect = RuntimeError("fail")
        result = _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)
        assert str(_FLOW_ID) in str(result.path)

    def test_logs_debug_when_write_fails(self, tmp_path: Path):
        from lfx.cli.pull import _write_flow

        flow = _fake_flow_obj(flow_id=_FLOW_ID)
        sdk = _make_sdk_mock()
        sdk.normalize_flow.side_effect = RuntimeError("fail")

        with patch("lfx.cli.pull.logger") as mock_logger:
            _write_flow(flow, sdk=sdk, dest_dir=tmp_path, strip_secrets=False, indent=2)

        mock_logger.debug.assert_called_once_with("Failed to write flow %s", _FLOW_ID, exc_info=True)


# ---------------------------------------------------------------------------
# PullResult
# ---------------------------------------------------------------------------


class TestPullResult:
    def test_created_is_ok(self, tmp_path: Path):
        from lfx.cli.pull import PullResult

        r = PullResult(flow_id=_FLOW_ID, flow_name="F", path=tmp_path / "f.json", status="created")
        assert r.ok is True

    def test_updated_is_ok(self, tmp_path: Path):
        from lfx.cli.pull import PullResult

        r = PullResult(flow_id=_FLOW_ID, flow_name="F", path=tmp_path / "f.json", status="updated")
        assert r.ok is True

    def test_unchanged_is_ok(self, tmp_path: Path):
        from lfx.cli.pull import PullResult

        r = PullResult(flow_id=_FLOW_ID, flow_name="F", path=tmp_path / "f.json", status="unchanged")
        assert r.ok is True

    def test_error_is_not_ok(self, tmp_path: Path):
        from lfx.cli.pull import PullResult

        r = PullResult(flow_id=_FLOW_ID, flow_name="F", path=tmp_path / "f.json", status="error", error="timeout")
        assert r.ok is False

    def test_error_message_stored(self, tmp_path: Path):
        from lfx.cli.pull import PullResult

        r = PullResult(flow_id=_FLOW_ID, flow_name="F", path=tmp_path / "f.json", status="error", error="some error")
        assert r.error == "some error"


# ---------------------------------------------------------------------------
# pull_command — single flow by ID
# ---------------------------------------------------------------------------


class TestPullCommandSingleFlow:
    def test_file_is_written_to_output_dir(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock()
        client.get_flow.return_value = flow
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(tmp_path=tmp_path, flow_id=str(_FLOW_ID), output_dir=str(tmp_path), sdk_mock=sdk)
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 1

    def test_uses_correct_flow_id_uuid(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock()
        client.get_flow.return_value = flow
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(tmp_path=tmp_path, flow_id=str(_FLOW_ID), output_dir=str(tmp_path), sdk_mock=sdk)
        client.get_flow.assert_called_once_with(_FLOW_ID)

    def test_exits_0_on_success(self, tmp_path: Path):
        """pull_command should not raise typer.Exit on success."""
        flow = _fake_flow_obj()
        client = _make_client_mock()
        client.get_flow.return_value = flow
        sdk = _make_sdk_mock(client_mock=client)
        # Should not raise
        _run_pull(tmp_path=tmp_path, flow_id=str(_FLOW_ID), output_dir=str(tmp_path), sdk_mock=sdk)

    def test_exits_1_if_get_flow_raises(self, tmp_path: Path):
        client = _make_client_mock()
        client.get_flow.side_effect = RuntimeError("not found")
        sdk = _make_sdk_mock(client_mock=client)
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, flow_id=str(_FLOW_ID), output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_single_flow_write_error_exits_1(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock()
        client.get_flow.return_value = flow
        sdk = _make_sdk_mock(client_mock=client)
        sdk.normalize_flow.side_effect = RuntimeError("normalize failed")
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, flow_id=str(_FLOW_ID), output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# pull_command — project by name
# ---------------------------------------------------------------------------


class TestPullCommandProjectByName:
    def test_resolves_project_from_list_projects(self, tmp_path: Path):
        flow = _fake_flow_obj()
        proj = _fake_project(name="My Project", flows=[flow])
        client = _make_client_mock()
        client.list_projects.return_value = [_fake_project_summary(name="My Project", project_id=proj.id)]
        client.get_project.return_value = proj
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(tmp_path=tmp_path, project="My Project", output_dir=str(tmp_path), sdk_mock=sdk)
        client.list_projects.assert_called_once()
        client.get_project.assert_called_once_with(proj.id)

    def test_exits_1_if_project_name_not_found(self, tmp_path: Path):
        client = _make_client_mock()
        client.list_projects.return_value = [_fake_project_summary(name="Other Project")]
        sdk = _make_sdk_mock(client_mock=client)
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, project="Nonexistent", output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_exits_1_when_no_projects_exist(self, tmp_path: Path):
        client = _make_client_mock()
        client.list_projects.return_value = []
        sdk = _make_sdk_mock(client_mock=client)
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, project="My Project", output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_writes_all_flows_in_project(self, tmp_path: Path):
        flow1 = _fake_flow_obj(flow_id=_FLOW_ID, name="Flow One")
        flow2 = _fake_flow_obj(flow_id=_FLOW_ID_2, name="Flow Two")
        proj = _fake_project(name="My Project", flows=[flow1, flow2])
        client = _make_client_mock()
        client.list_projects.return_value = [_fake_project_summary(name="My Project", project_id=proj.id)]
        client.get_project.return_value = proj
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(tmp_path=tmp_path, project="My Project", output_dir=str(tmp_path), sdk_mock=sdk)
        assert sdk.normalize_flow.call_count == 2

    def test_uses_first_matching_project(self, tmp_path: Path):
        proj1 = _fake_project(name="My Project", project_id=_PROJECT_ID, flows=[_fake_flow_obj()])
        proj2 = _fake_project(
            name="My Project",
            project_id=UUID("bbbbbbbb-0000-0000-0000-000000000002"),
            flows=[],
        )
        client = _make_client_mock()
        client.list_projects.return_value = [
            _fake_project_summary(name="My Project", project_id=proj1.id),
            _fake_project_summary(name="My Project", project_id=proj2.id),
        ]
        client.get_project.return_value = proj1
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(tmp_path=tmp_path, project="My Project", output_dir=str(tmp_path), sdk_mock=sdk)
        # Only flows from proj1 are written (1 flow)
        assert sdk.normalize_flow.call_count == 1

    def test_exits_1_if_get_project_for_name_raises(self, tmp_path: Path):
        client = _make_client_mock()
        client.list_projects.return_value = [_fake_project_summary(name="My Project", project_id=_PROJECT_ID)]
        client.get_project.side_effect = RuntimeError("boom")
        sdk = _make_sdk_mock(client_mock=client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, project="My Project", output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# pull_command — project by ID
# ---------------------------------------------------------------------------


class TestPullCommandProjectById:
    def test_uses_get_project_with_uuid(self, tmp_path: Path):
        proj = _fake_project(flows=[_fake_flow_obj()])
        client = _make_client_mock()
        client.get_project.return_value = proj
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(
            tmp_path=tmp_path,
            project_id=str(_PROJECT_ID),
            output_dir=str(tmp_path),
            sdk_mock=sdk,
        )
        client.get_project.assert_called_once_with(_PROJECT_ID)

    def test_exits_1_if_get_project_raises(self, tmp_path: Path):
        client = _make_client_mock()
        client.get_project.side_effect = RuntimeError("not found")
        sdk = _make_sdk_mock(client_mock=client)
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(
                tmp_path=tmp_path,
                project_id=str(_PROJECT_ID),
                output_dir=str(tmp_path),
                sdk_mock=sdk,
            )
        assert exc_info.value.exit_code == 1

    def test_skips_list_projects_when_project_id_given(self, tmp_path: Path):
        proj = _fake_project(flows=[_fake_flow_obj()])
        client = _make_client_mock()
        client.get_project.return_value = proj
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(
            tmp_path=tmp_path,
            project_id=str(_PROJECT_ID),
            output_dir=str(tmp_path),
            sdk_mock=sdk,
        )
        client.list_projects.assert_not_called()

    def test_writes_flows_from_fetched_project(self, tmp_path: Path):
        flow1 = _fake_flow_obj(flow_id=_FLOW_ID, name="Alpha")
        flow2 = _fake_flow_obj(flow_id=_FLOW_ID_2, name="Beta")
        proj = _fake_project(flows=[flow1, flow2])
        client = _make_client_mock()
        client.get_project.return_value = proj
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(
            tmp_path=tmp_path,
            project_id=str(_PROJECT_ID),
            output_dir=str(tmp_path),
            sdk_mock=sdk,
        )
        assert sdk.normalize_flow.call_count == 2


# ---------------------------------------------------------------------------
# pull_command — all flows
# ---------------------------------------------------------------------------


class TestPullCommandAllFlows:
    def test_calls_list_flows_with_correct_args(self, tmp_path: Path):
        client = _make_client_mock(flows=[_fake_flow_obj()])
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk)
        client.list_flows.assert_called_once_with(get_all=True, remove_example_flows=True)

    def test_prints_warning_and_returns_when_no_flows(self, tmp_path: Path):
        client = _make_client_mock(flows=[])
        sdk = _make_sdk_mock(client_mock=client)
        # Should not raise, should return early
        _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk)
        sdk.normalize_flow.assert_not_called()

    def test_writes_multiple_flows(self, tmp_path: Path):
        flow1 = _fake_flow_obj(flow_id=_FLOW_ID, name="Alpha")
        flow2 = _fake_flow_obj(flow_id=_FLOW_ID_2, name="Beta")
        client = _make_client_mock(flows=[flow1, flow2])
        sdk = _make_sdk_mock(client_mock=client)
        _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk)
        assert sdk.normalize_flow.call_count == 2

    def test_exits_1_if_list_flows_raises(self, tmp_path: Path):
        client = _make_client_mock()
        client.list_flows.side_effect = RuntimeError("connection refused")
        sdk = _make_sdk_mock(client_mock=client)
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_exits_1_if_any_flow_write_fails(self, tmp_path: Path):
        flow1 = _fake_flow_obj(flow_id=_FLOW_ID, name="Good")
        flow2 = _fake_flow_obj(flow_id=_FLOW_ID_2, name="Bad")
        client = _make_client_mock(flows=[flow1, flow2])
        sdk = _make_sdk_mock(client_mock=client)
        call_count = 0

        def maybe_fail(d, **_kw):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                msg = "write failed"
                raise RuntimeError(msg)
            return d

        sdk.normalize_flow.side_effect = maybe_fail
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_all_flows_attempted_even_on_partial_error(self, tmp_path: Path):
        flow1 = _fake_flow_obj(flow_id=_FLOW_ID, name="Good")
        flow2 = _fake_flow_obj(flow_id=_FLOW_ID_2, name="Bad")
        client = _make_client_mock(flows=[flow1, flow2])
        sdk = _make_sdk_mock(client_mock=client)
        call_count = 0

        def maybe_fail(d, **_kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "first fails"
                raise RuntimeError(msg)
            return d

        sdk.normalize_flow.side_effect = maybe_fail
        with pytest.raises(typer.Exit):
            _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk)
        assert call_count == 2


# ---------------------------------------------------------------------------
# pull_command — error handling
# ---------------------------------------------------------------------------


class TestPullCommandErrorHandling:
    def test_config_error_exits_1(self, tmp_path: Path):
        from lfx.cli.pull import pull_command
        from lfx.config import ConfigError

        sdk = _make_sdk_mock()
        with (
            patch("lfx.cli.pull.load_sdk", return_value=sdk),
            patch("lfx.config.resolve_environment", side_effect=ConfigError("bad config")),
            pytest.raises(typer.Exit) as exc_info,
        ):
            pull_command(
                env="nonexistent",
                output_dir=str(tmp_path),
                flow_id=None,
                project=None,
                project_id=None,
                environments_file=None,
                target=None,
                api_key=None,
                strip_secrets=False,
                indent=2,
            )
        assert exc_info.value.exit_code == 1

    def test_sdk_not_installed_raises_bad_parameter(self, tmp_path: Path):
        from lfx.cli.pull import pull_command

        with (
            patch("lfx.cli.pull.load_sdk", side_effect=typer.BadParameter("langflow-sdk is required")),
            pytest.raises(typer.BadParameter),
        ):
            pull_command(
                env=None,
                output_dir=str(tmp_path),
                flow_id=None,
                project=None,
                project_id=None,
                environments_file=None,
                target=_BASE_URL,
                api_key=_API_KEY,
                strip_secrets=False,
                indent=2,
            )

    def test_pull_errors_exit_1(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock(flows=[flow])
        sdk = _make_sdk_mock(client_mock=client)
        sdk.normalize_flow.side_effect = RuntimeError("corrupted")
        with pytest.raises(typer.Exit) as exc_info:
            _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_client_constructed_with_resolved_url_and_key(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock(flows=[flow])
        sdk = _make_sdk_mock(client_mock=client)
        cfg = _fake_env_config(url="http://custom.server", api_key="custom-key")  # pragma: allowlist secret
        _run_pull(tmp_path=tmp_path, output_dir=str(tmp_path), sdk_mock=sdk, env_cfg=cfg)
        sdk.Client.assert_called_once_with(
            base_url="http://custom.server",
            api_key="custom-key",  # pragma: allowlist secret
        )


# ---------------------------------------------------------------------------
# pull_command — output_dir behaviour
# ---------------------------------------------------------------------------


class TestPullCommandOutputDir:
    def test_defaults_to_flows_dir_when_not_specified(self, tmp_path: Path):
        """When output_dir is None the command uses 'flows' as the destination."""
        from lfx.cli.pull import pull_command

        flow = _fake_flow_obj()
        client = _make_client_mock(flows=[flow])
        sdk = _make_sdk_mock(client_mock=client)
        cfg = _fake_env_config()

        import os
        from pathlib import Path as _Path

        original_cwd = _Path.cwd()
        os.chdir(tmp_path)
        try:
            with (
                patch("lfx.cli.pull.load_sdk", return_value=sdk),
                patch("lfx.config.resolve_environment", return_value=cfg),
            ):
                pull_command(
                    env=None,
                    output_dir=None,
                    flow_id=None,
                    project=None,
                    project_id=None,
                    environments_file=None,
                    target=_BASE_URL,
                    api_key=_API_KEY,
                    strip_secrets=False,
                    indent=2,
                )
            flows_dir = tmp_path / "flows"
            assert flows_dir.exists()
        finally:
            os.chdir(original_cwd)

    def test_creates_output_dir_if_not_exists(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock(flows=[flow])
        sdk = _make_sdk_mock(client_mock=client)
        new_dir = tmp_path / "brand_new_dir"
        assert not new_dir.exists()
        _run_pull(tmp_path=tmp_path, output_dir=str(new_dir), sdk_mock=sdk)
        assert new_dir.exists()

    def test_uses_custom_dir_when_specified(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock(flows=[flow])
        sdk = _make_sdk_mock(client_mock=client)
        custom_dir = tmp_path / "my_custom_flows"
        _run_pull(tmp_path=tmp_path, output_dir=str(custom_dir), sdk_mock=sdk)
        assert custom_dir.exists()
        json_files = list(custom_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_creates_nested_output_dir(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock(flows=[flow])
        sdk = _make_sdk_mock(client_mock=client)
        nested_dir = tmp_path / "a" / "b" / "c"
        _run_pull(tmp_path=tmp_path, output_dir=str(nested_dir), sdk_mock=sdk)
        assert nested_dir.exists()

    def test_uses_existing_output_dir(self, tmp_path: Path):
        flow = _fake_flow_obj()
        client = _make_client_mock(flows=[flow])
        sdk = _make_sdk_mock(client_mock=client)
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        _run_pull(tmp_path=tmp_path, output_dir=str(existing_dir), sdk_mock=sdk)
        json_files = list(existing_dir.glob("*.json"))
        assert len(json_files) == 1


# ---------------------------------------------------------------------------
# _render_results
# ---------------------------------------------------------------------------


class TestRenderResults:
    def test_does_not_crash_with_mixed_statuses(self, tmp_path: Path):
        from lfx.cli.pull import PullResult, _render_results

        results = [
            PullResult(flow_id=_FLOW_ID, flow_name="A", path=tmp_path / "a.json", status="created"),
            PullResult(flow_id=_FLOW_ID_2, flow_name="B", path=tmp_path / "b.json", status="updated"),
            PullResult(
                flow_id=UUID("cccccccc-0000-0000-0000-000000000001"),
                flow_name="C",
                path=tmp_path / "c.json",
                status="unchanged",
            ),
            PullResult(
                flow_id=UUID("dddddddd-0000-0000-0000-000000000001"),
                flow_name="D",
                path=tmp_path / "d.json",
                status="error",
                error="something went wrong",
            ),
        ]
        # Should not raise
        _render_results(results)

    def test_does_not_crash_with_empty_results(self):
        from lfx.cli.pull import _render_results

        _render_results([])

    def test_does_not_crash_with_all_unchanged(self, tmp_path: Path):
        from lfx.cli.pull import PullResult, _render_results

        results = [
            PullResult(flow_id=_FLOW_ID, flow_name="A", path=tmp_path / "a.json", status="unchanged"),
            PullResult(flow_id=_FLOW_ID_2, flow_name="B", path=tmp_path / "b.json", status="unchanged"),
        ]
        _render_results(results)

    def test_does_not_crash_with_all_errors(self, tmp_path: Path):
        from lfx.cli.pull import PullResult, _render_results

        results = [
            PullResult(
                flow_id=_FLOW_ID,
                flow_name="A",
                path=tmp_path / "a.json",
                status="error",
                error="network error",
            ),
        ]
        _render_results(results)

    def test_does_not_crash_with_single_created(self, tmp_path: Path):
        from lfx.cli.pull import PullResult, _render_results

        results = [
            PullResult(flow_id=_FLOW_ID, flow_name="My Flow", path=tmp_path / "my_flow.json", status="created"),
        ]
        _render_results(results)
