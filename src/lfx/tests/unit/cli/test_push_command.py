"""Unit tests for lfx push -- push_command and helpers.

All tests run entirely in-process; no real Langflow instance or SDK required.
The SDK module is replaced wholesale with MagicMock so only the push logic
(file loading, upsert routing, dry-run, project resolution, result rendering)
is under test.
"""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

import json
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
    "name": "My Test Flow",
    "data": {"nodes": [], "edges": []},
}

_FLOW_DICT_2: dict = {
    "id": str(_FLOW_ID_2),
    "name": "Second Flow",
    "data": {"nodes": [], "edges": []},
}


# ---------------------------------------------------------------------------
# Fake exception class — avoids importing langflow_sdk in isolation mode
# ---------------------------------------------------------------------------


class _FakeLangflowHTTPError(Exception):
    """Stand-in for langflow_sdk.LangflowHTTPError in unit tests."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _write_flow(tmp_path: Path, name: str, flow: dict | None = None) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(flow if flow is not None else _FLOW_DICT), encoding="utf-8")
    return p


def _fake_project(name: str = "My Project", project_id: UUID = _PROJECT_ID) -> MagicMock:
    """Return a MagicMock that looks like a langflow_sdk.models.Project."""
    proj = MagicMock()
    proj.name = name
    proj.id = project_id
    return proj


def _fake_flow(flow_id: UUID = _FLOW_ID, name: str = "My Test Flow") -> MagicMock:
    """Return a MagicMock that looks like a langflow_sdk.models.Flow."""
    flow = MagicMock()
    flow.id = flow_id
    flow.name = name
    return flow


def _make_client_mock(*, create: bool = True) -> MagicMock:
    """Return a mock SDK client whose upsert_flow returns (flow, created)."""
    client = MagicMock()
    client.upsert_flow.return_value = (_fake_flow(), create)
    client.list_projects.return_value = []
    client.create_project.return_value = _fake_project()
    return client


def _make_sdk_mock(client_mock: MagicMock | None = None) -> MagicMock:
    """Return a mock langflow_sdk module wired to client_mock.

    SDK exception and model types are replaced with lightweight fakes so
    the test file has zero imports from langflow_sdk.
    """
    if client_mock is None:
        client_mock = _make_client_mock()

    sdk = MagicMock()
    sdk.Client.return_value = client_mock
    sdk.LangflowHTTPError = _FakeLangflowHTTPError
    # FlowCreate / ProjectCreate stay as MagicMock callables — push.py calls
    # them as constructors and passes the result to client.upsert_flow /
    # client.create_project.  We check the constructor call kwargs in tests.
    return sdk


def _run_push(
    flow_paths: list[str],
    *,
    dir_path: str | None = None,
    project: str | None = None,
    project_id: str | None = None,
    environments_file: str | None = None,
    env: str | None = None,
    dry_run: bool = False,
    normalize: bool = False,
    strip_secrets: bool = False,
    sdk_mock: MagicMock | None = None,
) -> None:
    """Invoke push_command with mocked SDK, using --target for inline env resolution."""
    from lfx.cli.push import push_command

    mock = sdk_mock if sdk_mock is not None else _make_sdk_mock()
    with patch("lfx.cli.push.load_sdk", return_value=mock):
        push_command(
            flow_paths=flow_paths,
            env=env,
            dir_path=dir_path,
            project=project,
            project_id=project_id,
            environments_file=environments_file,
            target=_BASE_URL,
            api_key=_API_KEY,
            dry_run=dry_run,
            normalize=normalize,
            strip_secrets=strip_secrets,
        )


# ---------------------------------------------------------------------------
# PushResult
# ---------------------------------------------------------------------------


class TestPushResult:
    def test_created_is_ok(self, tmp_path):
        from lfx.cli.push import PushResult

        r = PushResult(path=tmp_path / "f.json", flow_id=_FLOW_ID, flow_name="F", status="created")
        assert r.ok is True

    def test_updated_is_ok(self, tmp_path):
        from lfx.cli.push import PushResult

        r = PushResult(path=tmp_path / "f.json", flow_id=_FLOW_ID, flow_name="F", status="updated")
        assert r.ok is True

    def test_dry_run_is_ok(self, tmp_path):
        from lfx.cli.push import PushResult

        r = PushResult(path=tmp_path / "f.json", flow_id=_FLOW_ID, flow_name="F", status="dry-run")
        assert r.ok is True

    def test_error_is_not_ok(self, tmp_path):
        from lfx.cli.push import PushResult

        r = PushResult(path=tmp_path / "f.json", flow_id=_FLOW_ID, flow_name="F", status="error", error="timeout")
        assert r.ok is False

    def test_error_message_stored(self, tmp_path):
        from lfx.cli.push import PushResult

        r = PushResult(path=tmp_path / "f.json", flow_id=_FLOW_ID, flow_name="F", status="error", error="some error")
        assert r.error == "some error"


# ---------------------------------------------------------------------------
# _load_flow_file
# ---------------------------------------------------------------------------


class TestLoadFlowFile:
    def test_valid_json_returns_dict(self, tmp_path):
        from lfx.cli.push import _load_flow_file

        p = _write_flow(tmp_path, "flow.json")
        result = _load_flow_file(p)
        assert result["id"] == str(_FLOW_ID)
        assert result["name"] == "My Test Flow"

    def test_invalid_json_raises_exit(self, tmp_path):
        from lfx.cli.push import _load_flow_file

        p = tmp_path / "bad.json"
        p.write_text("not valid json", encoding="utf-8")
        with pytest.raises(typer.Exit):
            _load_flow_file(p)

    def test_missing_file_raises_exit(self, tmp_path):
        from lfx.cli.push import _load_flow_file

        with pytest.raises(typer.Exit):
            _load_flow_file(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# _extract_flow_id
# ---------------------------------------------------------------------------


class TestExtractFlowId:
    def test_valid_uuid_returned(self, tmp_path):
        from lfx.cli.push import _extract_flow_id

        path = tmp_path / "f.json"
        result = _extract_flow_id({"id": str(_FLOW_ID)}, path)
        assert result == _FLOW_ID

    def test_missing_id_raises_exit(self, tmp_path):
        from lfx.cli.push import _extract_flow_id

        with pytest.raises(typer.Exit):
            _extract_flow_id({}, tmp_path / "f.json")

    def test_null_id_raises_exit(self, tmp_path):
        from lfx.cli.push import _extract_flow_id

        with pytest.raises(typer.Exit):
            _extract_flow_id({"id": None}, tmp_path / "f.json")

    def test_invalid_uuid_raises_exit(self, tmp_path):
        from lfx.cli.push import _extract_flow_id

        with pytest.raises(typer.Exit):
            _extract_flow_id({"id": "not-a-uuid"}, tmp_path / "f.json")

    def test_uuid_type_returned(self, tmp_path):
        from lfx.cli.push import _extract_flow_id

        path = tmp_path / "f.json"
        result = _extract_flow_id({"id": "aaaaaaaa-0000-0000-0000-000000000001"}, path)
        assert isinstance(result, UUID)


# ---------------------------------------------------------------------------
# _collect_flow_files
# ---------------------------------------------------------------------------


class TestCollectFlowFiles:
    def test_single_path_returned(self, tmp_path):
        from lfx.cli.push import _collect_flow_files

        p = _write_flow(tmp_path, "a.json")
        result = _collect_flow_files([str(p)], None)
        assert result == [p]

    def test_multiple_paths_returned(self, tmp_path):
        from lfx.cli.push import _collect_flow_files

        p1 = _write_flow(tmp_path, "a.json")
        p2 = _write_flow(tmp_path, "b.json", _FLOW_DICT_2)
        result = _collect_flow_files([str(p1), str(p2)], None)
        assert set(result) == {p1, p2}

    def test_dir_finds_all_json(self, tmp_path):
        from lfx.cli.push import _collect_flow_files

        d = tmp_path / "flows"
        d.mkdir()
        (d / "a.json").write_text("{}", encoding="utf-8")
        (d / "b.json").write_text("{}", encoding="utf-8")
        (d / "notes.txt").write_text("ignore", encoding="utf-8")
        result = _collect_flow_files([], str(d))
        assert len(result) == 2
        assert all(p.suffix == ".json" for p in result)

    def test_dir_and_paths_combined(self, tmp_path):
        from lfx.cli.push import _collect_flow_files

        d = tmp_path / "flows"
        d.mkdir()
        dir_flow = d / "dir.json"
        dir_flow.write_text("{}", encoding="utf-8")
        extra = _write_flow(tmp_path, "extra.json")
        result = _collect_flow_files([str(extra)], str(d))
        assert dir_flow in result
        assert extra in result

    def test_missing_path_raises_exit(self, tmp_path):
        from lfx.cli.push import _collect_flow_files

        with pytest.raises(typer.Exit):
            _collect_flow_files([str(tmp_path / "missing.json")], None)

    def test_dir_is_file_raises_exit(self, tmp_path):
        from lfx.cli.push import _collect_flow_files

        p = _write_flow(tmp_path, "a.json")
        with pytest.raises(typer.Exit):
            _collect_flow_files([], str(p))  # file passed as dir

    def test_empty_dir_returns_empty_list(self, tmp_path):
        from lfx.cli.push import _collect_flow_files

        d = tmp_path / "empty"
        d.mkdir()
        result = _collect_flow_files([], str(d))
        assert result == []


# ---------------------------------------------------------------------------
# _upsert_single
# ---------------------------------------------------------------------------


class TestUpsertSingle:
    def _flow_create_mock(self) -> MagicMock:
        return MagicMock()

    def test_dry_run_returns_dry_run_status(self, tmp_path):
        from lfx.cli.push import _upsert_single

        client = MagicMock()
        sdk = _make_sdk_mock(client)
        result = _upsert_single(
            client,
            sdk,
            tmp_path / "f.json",
            _FLOW_ID,
            self._flow_create_mock(),
            dry_run=True,
            flow_name="T",
            base_url="http://test",
        )
        assert result.status == "dry-run"
        assert result.ok is True
        client.upsert_flow.assert_not_called()

    def test_create_returns_created_status(self, tmp_path):
        from lfx.cli.push import _upsert_single

        client = _make_client_mock(create=True)
        sdk = _make_sdk_mock(client)
        result = _upsert_single(
            client,
            sdk,
            tmp_path / "f.json",
            _FLOW_ID,
            self._flow_create_mock(),
            dry_run=False,
            flow_name="T",
            base_url="http://test",
        )
        assert result.status == "created"
        assert result.ok is True

    def test_update_returns_updated_status(self, tmp_path):
        from lfx.cli.push import _upsert_single

        client = _make_client_mock(create=False)
        sdk = _make_sdk_mock(client)
        result = _upsert_single(
            client,
            sdk,
            tmp_path / "f.json",
            _FLOW_ID,
            self._flow_create_mock(),
            dry_run=False,
            flow_name="T",
            base_url="http://test",
        )
        assert result.status == "updated"
        assert result.ok is True

    def test_http_error_returns_error_status(self, tmp_path):
        from lfx.cli.push import _upsert_single

        client = _make_client_mock()
        client.upsert_flow.side_effect = _FakeLangflowHTTPError(500, "server error")
        sdk = _make_sdk_mock(client)
        result = _upsert_single(
            client,
            sdk,
            tmp_path / "f.json",
            _FLOW_ID,
            self._flow_create_mock(),
            dry_run=False,
            flow_name="T",
            base_url="http://test",
        )
        assert result.status == "error"
        assert result.error is not None
        assert result.ok is False

    def test_upsert_called_with_correct_flow_id(self, tmp_path):
        from lfx.cli.push import _upsert_single

        client = _make_client_mock(create=True)
        sdk = _make_sdk_mock(client)
        fc = self._flow_create_mock()
        _upsert_single(
            client, sdk, tmp_path / "f.json", _FLOW_ID, fc, dry_run=False, flow_name="T", base_url="http://test"
        )
        client.upsert_flow.assert_called_once_with(_FLOW_ID, fc)


# ---------------------------------------------------------------------------
# _find_or_create_project
# ---------------------------------------------------------------------------


class TestFindOrCreateProject:
    def test_found_project_returns_id(self):
        from lfx.cli.push import _find_or_create_project

        client = MagicMock()
        client.list_projects.return_value = [_fake_project(name="MyProj")]
        sdk = _make_sdk_mock(client)
        result = _find_or_create_project(client, sdk, "MyProj", dry_run=False)
        assert result == _PROJECT_ID
        client.create_project.assert_not_called()

    def test_not_found_creates_and_returns_id(self):
        from lfx.cli.push import _find_or_create_project

        client = MagicMock()
        client.list_projects.return_value = []
        client.create_project.return_value = _fake_project(name="NewProj")
        sdk = _make_sdk_mock(client)
        result = _find_or_create_project(client, sdk, "NewProj", dry_run=False)
        assert result == _PROJECT_ID
        client.create_project.assert_called_once()

    def test_dry_run_returns_none_without_creating(self):
        from lfx.cli.push import _find_or_create_project

        client = MagicMock()
        client.list_projects.return_value = []
        sdk = _make_sdk_mock(client)
        result = _find_or_create_project(client, sdk, "Ghost", dry_run=True)
        assert result is None
        client.create_project.assert_not_called()

    def test_dry_run_existing_project_returns_id(self):
        from lfx.cli.push import _find_or_create_project

        client = MagicMock()
        client.list_projects.return_value = [_fake_project(name="Found")]
        sdk = _make_sdk_mock(client)
        result = _find_or_create_project(client, sdk, "Found", dry_run=True)
        assert result == _PROJECT_ID


# ---------------------------------------------------------------------------
# push_command — integration (mocked SDK)
# ---------------------------------------------------------------------------


class TestPushCommand:
    def test_single_file_create(self, tmp_path):
        """Single flow JSON → upsert called once → created."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(create=True)
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], sdk_mock=sdk)
        client.upsert_flow.assert_called_once()
        flow_id_arg = client.upsert_flow.call_args[0][0]
        assert flow_id_arg == _FLOW_ID

    def test_single_file_update(self, tmp_path):
        """Second push → update (200)."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(create=False)
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], sdk_mock=sdk)
        client.upsert_flow.assert_called_once()

    def test_directory_pushes_all_json_files(self, tmp_path):
        """--dir pushes every *.json in the directory."""
        d = tmp_path / "flows"
        d.mkdir()
        (d / "a.json").write_text(json.dumps(_FLOW_DICT), encoding="utf-8")
        (d / "b.json").write_text(json.dumps(_FLOW_DICT_2), encoding="utf-8")
        (d / "readme.txt").write_text("ignore", encoding="utf-8")

        client = _make_client_mock(create=True)
        client.upsert_flow.side_effect = [
            (_fake_flow(_FLOW_ID), True),
            (_fake_flow(_FLOW_ID_2, "Second Flow"), True),
        ]
        sdk = _make_sdk_mock(client)
        _run_push([], dir_path=str(d), sdk_mock=sdk)
        assert client.upsert_flow.call_count == 2

    def test_dry_run_makes_no_upsert_calls(self, tmp_path):
        """Dry-run: upsert_flow is never called."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock()
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], dry_run=True, sdk_mock=sdk)
        client.upsert_flow.assert_not_called()

    def test_dry_run_creates_client_but_not_upsert(self, tmp_path):
        """In dry-run mode the SDK Client is constructed (for project lookups).

        upsert_flow is never called.
        """
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock()
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], dry_run=True, sdk_mock=sdk)
        sdk.Client.assert_called_once()
        client.upsert_flow.assert_not_called()

    def test_no_flow_files_exits(self):
        """No paths and no --dir → Exit(1)."""
        with pytest.raises(typer.Exit):
            _run_push([])

    def test_flow_missing_id_exits(self, tmp_path):
        """JSON without 'id' field → Exit(1)."""
        p = tmp_path / "no_id.json"
        p.write_text(json.dumps({"name": "Orphan", "data": {}}), encoding="utf-8")
        with pytest.raises(typer.Exit):
            _run_push([str(p)])

    def test_http_error_exits_with_code_1(self, tmp_path):
        """HTTP failure on any flow → Exit(1) after all flows attempted."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock()
        client.upsert_flow.side_effect = _FakeLangflowHTTPError(500, "oops")
        sdk = _make_sdk_mock(client)
        with pytest.raises(typer.Exit) as exc_info:
            _run_push([str(p)], sdk_mock=sdk)
        assert exc_info.value.exit_code == 1

    def test_with_project_name_resolves_folder_id(self, tmp_path):
        """--project triggers lookup; resolved folder_id passed to FlowCreate."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(create=True)
        client.list_projects.return_value = [_fake_project(name="My Proj")]
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], project="My Proj", sdk_mock=sdk)
        client.list_projects.assert_called_once()
        fc_kwargs = sdk.FlowCreate.call_args.kwargs
        assert fc_kwargs["folder_id"] == _PROJECT_ID

    def test_with_project_name_creates_if_not_found(self, tmp_path):
        """--project creates the remote project when it doesn't exist."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(create=True)
        client.list_projects.return_value = []
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], project="New Proj", sdk_mock=sdk)
        client.create_project.assert_called_once()

    def test_with_project_id_skips_lookup(self, tmp_path):
        """--project-id bypasses list_projects entirely."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(create=True)
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], project_id=str(_PROJECT_ID), sdk_mock=sdk)
        client.list_projects.assert_not_called()
        fc_kwargs = sdk.FlowCreate.call_args.kwargs
        assert fc_kwargs["folder_id"] == _PROJECT_ID

    def test_normalize_calls_sdk_normalize_flow(self, tmp_path):
        """--normalize invokes sdk.normalize_flow before upsert."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(create=True)
        sdk = _make_sdk_mock(client)
        sdk.normalize_flow.return_value = _FLOW_DICT
        _run_push([str(p)], normalize=True, sdk_mock=sdk)
        sdk.normalize_flow.assert_called_once()

    def test_no_normalize_skips_sdk_normalize(self, tmp_path):
        """With normalize=False the SDK normalize_flow is never called."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(create=True)
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], normalize=False, sdk_mock=sdk)
        sdk.normalize_flow.assert_not_called()

    def test_partial_error_still_attempts_all_files(self, tmp_path):
        """An error on one flow does not abort the remaining pushes."""
        p1 = _write_flow(tmp_path, "ok.json")
        p2 = _write_flow(tmp_path, "bad.json", _FLOW_DICT_2)
        client = _make_client_mock()
        client.upsert_flow.side_effect = [
            (_fake_flow(), True),
            _FakeLangflowHTTPError(500, "server down"),
        ]
        sdk = _make_sdk_mock(client)
        with pytest.raises(typer.Exit) as exc_info:
            _run_push([str(p1), str(p2)], sdk_mock=sdk)
        assert exc_info.value.exit_code == 1
        assert client.upsert_flow.call_count == 2  # both files were attempted

    def test_client_constructed_with_resolved_url_and_key(self, tmp_path):
        """SDK Client is constructed with the inline URL and API key."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock()
        sdk = _make_sdk_mock(client)
        _run_push([str(p)], sdk_mock=sdk)
        sdk.Client.assert_called_once_with(base_url=_BASE_URL, api_key=_API_KEY)

    def test_environments_file_resolves_url(self, tmp_path):
        """Environment is resolved from a TOML config file (no --target)."""
        p = _write_flow(tmp_path, "flow.json")
        env_file = tmp_path / "langflow-environments.toml"
        env_file.write_text(
            f'[environments.ci]\nurl = "{_BASE_URL}"\n',
            encoding="utf-8",
        )
        from lfx.cli.push import push_command

        client = _make_client_mock(create=True)
        sdk = _make_sdk_mock(client)
        with patch("lfx.cli.push.load_sdk", return_value=sdk):
            push_command(
                flow_paths=[str(p)],
                env="ci",
                dir_path=None,
                project=None,
                project_id=None,
                environments_file=str(env_file),
                target=None,
                api_key=None,
                dry_run=False,
                normalize=False,
                strip_secrets=False,
            )
        sdk.Client.assert_called_once_with(base_url=_BASE_URL, api_key=None)

    def test_missing_environments_file_exits(self, tmp_path):
        """A non-existent --environments-file → ConfigError → Exit(1)."""
        p = _write_flow(tmp_path, "flow.json")
        from lfx.cli.push import push_command

        sdk = _make_sdk_mock()
        with patch("lfx.cli.push.load_sdk", return_value=sdk), pytest.raises(typer.Exit):
            push_command(
                flow_paths=[str(p)],
                env="missing",
                dir_path=None,
                project=None,
                project_id=None,
                environments_file=str(tmp_path / "missing.yaml"),
                target=None,
                api_key=None,
                dry_run=False,
                normalize=False,
                strip_secrets=False,
            )
