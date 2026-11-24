"""Unit tests for lfx status -- status_command and helpers.

All tests run entirely in-process; no real Langflow instance or SDK required.
The SDK is replaced via patch so only the status logic (file collection, hash
comparison, table rendering, exit-code rules) is exercised.
"""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

import io
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

_FLOW_DICT: dict = {
    "id": str(_FLOW_ID),
    "name": "My Test Flow",
    "data": {"nodes": [], "edges": []},
}

_FLOW_DICT_2: dict = {
    "id": str(_FLOW_ID_2),
    "name": "Second Flow",
    "data": {"nodes": [{"id": "n1"}], "edges": []},
}


# ---------------------------------------------------------------------------
# Fake exception class — avoids importing langflow_sdk in isolation mode
# ---------------------------------------------------------------------------


class _FakeLangflowNotFoundError(Exception):
    """Stand-in for langflow_sdk.exceptions.LangflowNotFoundError in unit tests."""


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _write_flow(tmp_path: Path, name: str, flow: dict | None = None) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(flow if flow is not None else _FLOW_DICT), encoding="utf-8")
    return p


def _fake_env_config(url: str = _BASE_URL, api_key: str = _API_KEY, name: str = "test-env") -> MagicMock:
    """Return a MagicMock that looks like an lfx EnvConfig."""
    cfg = MagicMock()
    cfg.url = url
    cfg.api_key = api_key
    cfg.name = name
    return cfg


def _fake_remote_flow(flow_id: UUID = _FLOW_ID, flow_dict: dict | None = None) -> MagicMock:
    """Return a MagicMock that looks like a langflow_sdk Flow model."""
    remote = MagicMock()
    remote.id = flow_id
    remote.name = (flow_dict or _FLOW_DICT).get("name", "Remote Flow")
    remote.updated_at = None
    # model_dump returns a copy of the dict so hash comparison works correctly
    remote.model_dump.return_value = dict(flow_dict or _FLOW_DICT)
    return remote


def _identity_normalize(flow: dict) -> dict:
    """Identity normalize_flow function for tests."""
    return flow


def _json_flow_to_json(flow: dict) -> str:
    """Deterministic flow_to_json function for tests."""
    return json.dumps(flow, sort_keys=True)


def _make_client_mock(
    *,
    remote_flow: MagicMock | None = None,
    get_flow_side_effect: BaseException | None = None,
    list_flows_result: list | None = None,
) -> MagicMock:
    """Return a mock SDK client."""
    client = MagicMock()
    if get_flow_side_effect is not None:
        client.get_flow.side_effect = get_flow_side_effect
    else:
        client.get_flow.return_value = remote_flow if remote_flow is not None else _fake_remote_flow()
    client.list_flows.return_value = list_flows_result if list_flows_result is not None else []
    return client


def _make_sdk_triple(
    client_mock: MagicMock | None = None,
) -> tuple[object, object, MagicMock, type[Exception]]:
    """Return the mocked _load_sdk() payload for status_command tests."""
    if client_mock is None:
        client_mock = _make_client_mock()
    client_cls = MagicMock(return_value=client_mock)
    return _identity_normalize, _json_flow_to_json, client_cls, _FakeLangflowNotFoundError


class _CloseAwareClient:
    """Minimal client that raises if used after close()."""

    def __init__(self, remote_flow: MagicMock, list_flows_result: list | None = None) -> None:
        self._remote_flow = remote_flow
        self._list_flows_result = list_flows_result if list_flows_result is not None else []
        self.closed = False
        self.get_flow_calls: list[UUID] = []
        self.list_flows_calls: list[dict] = []

    def get_flow(self, flow_id: UUID) -> MagicMock:
        if self.closed:
            msg = "client already closed"
            raise RuntimeError(msg)
        self.get_flow_calls.append(flow_id)
        return self._remote_flow

    def list_flows(self, **kwargs) -> list:
        if self.closed:
            msg = "client already closed"
            raise RuntimeError(msg)
        self.list_flows_calls.append(kwargs)
        return self._list_flows_result

    def close(self) -> None:
        self.closed = True


def _run_status(
    flow_paths: list[str],
    *,
    dir_path: str | None = None,
    env: str | None = None,
    environments_file: str | None = None,
    show_remote_only: bool = False,
    sdk_triple: tuple | None = None,
    env_cfg: MagicMock | None = None,
) -> None:
    """Invoke status_command with fully mocked SDK and config resolution.

    The status command now expects _load_sdk() to provide the not-found exception
    alongside the serialization helpers and client class.
    """
    from lfx.cli.status import status_command

    triple = sdk_triple if sdk_triple is not None else _make_sdk_triple()
    cfg = env_cfg if env_cfg is not None else _fake_env_config()

    with (
        patch("lfx.cli.status._load_sdk", return_value=triple),
        patch("lfx.config.resolve_environment", return_value=cfg),
    ):
        status_command(
            dir_path=dir_path,
            flow_paths=flow_paths,
            env=env,
            environments_file=environments_file,
            target=_BASE_URL,
            api_key=_API_KEY,
            show_remote_only=show_remote_only,
        )


# ---------------------------------------------------------------------------
# FlowStatus dataclass
# ---------------------------------------------------------------------------


class TestFlowStatus:
    def test_required_fields(self):
        from lfx.cli.status import FlowStatus

        s = FlowStatus(name="MyFlow", status="synced")
        assert s.name == "MyFlow"
        assert s.status == "synced"

    def test_path_defaults_to_none(self):
        from lfx.cli.status import FlowStatus

        s = FlowStatus(name="F", status="new")
        assert s.path is None

    def test_flow_id_defaults_to_none(self):
        from lfx.cli.status import FlowStatus

        s = FlowStatus(name="F", status="new")
        assert s.flow_id is None

    def test_detail_defaults_to_empty_string(self):
        from lfx.cli.status import FlowStatus

        s = FlowStatus(name="F", status="error")
        assert s.detail == ""

    def test_all_fields_assignable(self, tmp_path):
        from pathlib import Path

        from lfx.cli.status import FlowStatus

        p = Path(tmp_path / "flow.json")
        s = FlowStatus(name="X", status="ahead", path=p, flow_id=_FLOW_ID, detail="local change")
        assert s.path == p
        assert s.flow_id == _FLOW_ID
        assert s.detail == "local change"

    def test_status_constants_exist(self):
        import lfx.cli.status as m

        assert m._STATUS_SYNCED == "synced"
        assert m._STATUS_AHEAD == "ahead"
        assert m._STATUS_NEW == "new"
        assert m._STATUS_REMOTE_ONLY == "remote-only"
        assert m._STATUS_NO_ID == "no-id"
        assert m._STATUS_ERROR == "error"


# ---------------------------------------------------------------------------
# _flow_hash
# ---------------------------------------------------------------------------


class TestFlowHash:
    def test_returns_12_char_string(self):
        from lfx.cli.status import _flow_hash

        result = _flow_hash(_FLOW_DICT, _identity_normalize, _json_flow_to_json)
        assert isinstance(result, str)
        assert len(result) == 12

    def test_deterministic_for_same_input(self):
        from lfx.cli.status import _flow_hash

        h1 = _flow_hash(_FLOW_DICT, _identity_normalize, _json_flow_to_json)
        h2 = _flow_hash(_FLOW_DICT, _identity_normalize, _json_flow_to_json)
        assert h1 == h2

    def test_different_for_different_input(self):
        from lfx.cli.status import _flow_hash

        h1 = _flow_hash(_FLOW_DICT, _identity_normalize, _json_flow_to_json)
        h2 = _flow_hash(_FLOW_DICT_2, _identity_normalize, _json_flow_to_json)
        assert h1 != h2

    def test_normalize_fn_is_called(self):
        from lfx.cli.status import _flow_hash

        normalize_mock = MagicMock(return_value=_FLOW_DICT)
        _flow_hash(_FLOW_DICT, normalize_mock, _json_flow_to_json)
        normalize_mock.assert_called_once_with(_FLOW_DICT)

    def test_flow_to_json_fn_is_called(self):
        from lfx.cli.status import _flow_hash

        to_json_mock = MagicMock(return_value=json.dumps(_FLOW_DICT))
        _flow_hash(_FLOW_DICT, _identity_normalize, to_json_mock)
        to_json_mock.assert_called_once_with(_FLOW_DICT)

    def test_hash_is_hexadecimal(self):
        from lfx.cli.status import _flow_hash

        result = _flow_hash(_FLOW_DICT, _identity_normalize, _json_flow_to_json)
        int(result, 16)  # raises ValueError if not hex


# ---------------------------------------------------------------------------
# _collect_files
# ---------------------------------------------------------------------------


class TestCollectFiles:
    def test_dir_path_returns_json_files(self, tmp_path):
        from lfx.cli.status import _collect_files

        d = tmp_path / "flows"
        d.mkdir()
        (d / "a.json").write_text("{}", encoding="utf-8")
        (d / "b.json").write_text("{}", encoding="utf-8")
        (d / "notes.txt").write_text("ignore", encoding="utf-8")
        result = _collect_files(str(d), [])
        assert len(result) == 2
        assert all(p.suffix == ".json" for p in result)

    def test_dir_path_returns_sorted_files(self, tmp_path):
        from lfx.cli.status import _collect_files

        d = tmp_path / "flows"
        d.mkdir()
        (d / "z.json").write_text("{}", encoding="utf-8")
        (d / "a.json").write_text("{}", encoding="utf-8")
        result = _collect_files(str(d), [])
        assert result[0].name == "a.json"
        assert result[1].name == "z.json"

    def test_flow_paths_returned_as_paths(self, tmp_path):
        from pathlib import Path

        from lfx.cli.status import _collect_files

        p1 = _write_flow(tmp_path, "x.json")
        p2 = _write_flow(tmp_path, "y.json", _FLOW_DICT_2)
        result = _collect_files(None, [str(p1), str(p2)])
        assert Path(str(p1)) in result
        assert Path(str(p2)) in result

    def test_empty_args_uses_flows_cwd_when_exists(self, tmp_path, monkeypatch):
        from lfx.cli.status import _collect_files

        flows_dir = tmp_path / "flows"
        flows_dir.mkdir()
        (flows_dir / "test.json").write_text("{}", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = _collect_files(None, [])
        assert len(result) == 1
        assert result[0].name == "test.json"

    def test_empty_args_no_flows_dir_returns_empty(self, tmp_path, monkeypatch):
        from lfx.cli.status import _collect_files

        monkeypatch.chdir(tmp_path)
        result = _collect_files(None, [])
        assert result == []

    def test_nonexistent_dir_exits_1(self, tmp_path):
        from lfx.cli.status import _collect_files

        with pytest.raises(typer.Exit) as exc_info:
            _collect_files(str(tmp_path / "does_not_exist"), [])
        assert exc_info.value.exit_code == 1

    def test_dir_path_takes_priority_over_flow_paths(self, tmp_path):
        from lfx.cli.status import _collect_files

        d = tmp_path / "flows"
        d.mkdir()
        (d / "dir_flow.json").write_text("{}", encoding="utf-8")
        extra = _write_flow(tmp_path, "extra.json")
        # When dir_path is provided, flow_paths is ignored per code path (elif)
        result = _collect_files(str(d), [str(extra)])
        names = [p.name for p in result]
        assert "dir_flow.json" in names

    def test_empty_dir_returns_empty_list(self, tmp_path):
        from lfx.cli.status import _collect_files

        d = tmp_path / "empty"
        d.mkdir()
        result = _collect_files(str(d), [])
        assert result == []


# ---------------------------------------------------------------------------
# _render_table
# ---------------------------------------------------------------------------


class TestRenderTable:
    @staticmethod
    def _capture_render(statuses, env_label):
        """Render the table to a string buffer and return the plain-text output."""
        from lfx.cli.status import _render_table
        from rich.console import Console

        buf = io.StringIO()
        fake_console = Console(file=buf, width=200, no_color=True)
        with patch("lfx.cli.status.console", fake_console):
            _render_table(statuses, env_label)
        return buf.getvalue()

    def test_empty_list_does_not_crash(self):
        from lfx.cli.status import _render_table

        _render_table([], "test-env")

    def test_synced_status_contains_flow_name_and_label(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="MyFlow", status="synced", path=tmp_path / "f.json", flow_id=_FLOW_ID)]
        output = self._capture_render(statuses, "test-env")
        assert "MyFlow" in output
        assert "synced" in output.lower()

    def test_ahead_status_contains_label(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="AheadFlow", status="ahead", path=tmp_path / "f.json", flow_id=_FLOW_ID)]
        output = self._capture_render(statuses, "test-env")
        assert "AheadFlow" in output
        assert "ahead" in output.lower()

    def test_new_status_contains_label(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="NewFlow", status="new", path=tmp_path / "f.json", flow_id=_FLOW_ID)]
        output = self._capture_render(statuses, "test-env")
        assert "NewFlow" in output
        assert "new" in output.lower()

    def test_remote_only_status_contains_label(self):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="RemoteFlow", status="remote-only", flow_id=_FLOW_ID)]
        output = self._capture_render(statuses, "test-env")
        assert "RemoteFlow" in output
        assert "remote only" in output.lower()

    def test_no_id_status_contains_detail(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [
            FlowStatus(
                name="OrphanFlow",
                status="no-id",
                path=tmp_path / "f.json",
                detail="run lfx export first",
            )
        ]
        output = self._capture_render(statuses, "test-env")
        assert "OrphanFlow" in output
        assert "no id" in output.lower()
        assert "run lfx export first" in output

    def test_error_status_contains_detail(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="BadFlow", status="error", path=tmp_path / "f.json", detail="parse error")]
        output = self._capture_render(statuses, "test-env")
        assert "BadFlow" in output
        assert "error" in output.lower()
        assert "parse error" in output

    def test_all_statuses_together_contains_all_names(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [
            FlowStatus(name="Synced", status="synced", path=tmp_path / "s.json", flow_id=_FLOW_ID),
            FlowStatus(name="Ahead", status="ahead", path=tmp_path / "a.json", flow_id=_FLOW_ID_2),
            FlowStatus(name="New", status="new", path=tmp_path / "n.json"),
            FlowStatus(name="Remote", status="remote-only", flow_id=_FLOW_ID),
            FlowStatus(name="NoId", status="no-id", path=tmp_path / "noid.json"),
            FlowStatus(name="Err", status="error", path=tmp_path / "e.json", detail="oops"),
        ]
        output = self._capture_render(statuses, "production")
        for s in statuses:
            assert s.name in output

    def test_env_label_appears_in_title(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="F", status="synced", path=tmp_path / "f.json", flow_id=_FLOW_ID)]
        output = self._capture_render(statuses, "my-staging")
        assert "my-staging" in output

    def test_status_with_no_path_shows_dash(self):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="Ghost", status="remote-only", flow_id=_FLOW_ID)]
        output = self._capture_render(statuses, "env")
        assert "Ghost" in output

    def test_status_with_no_flow_id_shows_dash(self, tmp_path):
        from lfx.cli.status import FlowStatus

        statuses = [FlowStatus(name="NoIdFlow", status="no-id", path=tmp_path / "f.json")]
        output = self._capture_render(statuses, "env")
        assert "NoIdFlow" in output


# ---------------------------------------------------------------------------
# status_command — synced (exits 0)
# ---------------------------------------------------------------------------


class TestStatusCommandSynced:
    def test_synced_flow_exits_0(self, tmp_path):
        """When local and remote hashes match, exits 0 (no Exit raised by typer)."""
        p = _write_flow(tmp_path, "flow.json")
        remote = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)
        # Should complete without raising Exit(1)
        _run_status([str(p)], sdk_triple=triple)

    def test_synced_multiple_flows_exits_0(self, tmp_path):
        """All synced flows → no Exit raised (exit 0)."""
        p1 = _write_flow(tmp_path, "a.json", _FLOW_DICT)
        p2 = _write_flow(tmp_path, "b.json", _FLOW_DICT_2)

        remote1 = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)
        remote2 = _fake_remote_flow(_FLOW_ID_2, _FLOW_DICT_2)
        client = _make_client_mock()
        client.get_flow.side_effect = [remote1, remote2]
        triple = _make_sdk_triple(client)
        _run_status([str(p1), str(p2)], sdk_triple=triple)

    def test_synced_calls_get_flow_with_correct_id(self, tmp_path):
        """get_flow is called with the UUID from the flow file."""
        p = _write_flow(tmp_path, "flow.json")
        remote = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)
        _run_status([str(p)], sdk_triple=triple)
        client.get_flow.assert_called_once_with(_FLOW_ID)

    def test_client_constructed_with_env_url_and_key(self, tmp_path):
        """SDK Client is created with the resolved env URL and API key."""
        p = _write_flow(tmp_path, "flow.json")
        remote = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        normalize_fn, to_json_fn, client_cls, not_found_error = _make_sdk_triple(client)
        cfg = _fake_env_config(url="http://custom.test", api_key="my-key")  # pragma: allowlist secret

        with (
            patch("lfx.cli.status._load_sdk", return_value=(normalize_fn, to_json_fn, client_cls, not_found_error)),
            patch("lfx.config.resolve_environment", return_value=cfg),
        ):
            from lfx.cli.status import status_command

            status_command(
                dir_path=None,
                flow_paths=[str(p)],
                env=None,
                environments_file=None,
                target="http://custom.test",
                api_key="my-key",  # pragma: allowlist secret
                show_remote_only=False,
            )
        client_cls.assert_called_once_with(base_url="http://custom.test", api_key="my-key")  # pragma: allowlist secret

    def test_client_is_closed_after_requests_finish(self, tmp_path):
        """The client stays usable during status checks and is closed at the end."""
        p = _write_flow(tmp_path, "flow.json")
        remote = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _CloseAwareClient(remote)
        triple = _identity_normalize, _json_flow_to_json, MagicMock(return_value=client), _FakeLangflowNotFoundError

        _run_status([str(p)], sdk_triple=triple)

        assert client.get_flow_calls == [_FLOW_ID]
        assert client.closed is True


# ---------------------------------------------------------------------------
# status_command — ahead (exits 1)
# ---------------------------------------------------------------------------


class TestStatusCommandAhead:
    def test_ahead_flow_exits_1(self, tmp_path):
        """Local hash differs from remote → exits 1."""
        p = _write_flow(tmp_path, "flow.json", _FLOW_DICT)
        # Remote has different data so hashes won't match
        remote_dict = dict(_FLOW_DICT)
        remote_dict["data"] = {"nodes": [{"id": "different"}], "edges": []}
        remote = _fake_remote_flow(_FLOW_ID, remote_dict)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_ahead_status_in_mixed_results_exits_1(self, tmp_path):
        """Even one 'ahead' flow among synced ones → exits 1."""
        p_synced = _write_flow(tmp_path, "synced.json", _FLOW_DICT)
        p_ahead = _write_flow(tmp_path, "ahead.json", _FLOW_DICT_2)

        remote_synced = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)
        remote_ahead_dict = dict(_FLOW_DICT_2)
        remote_ahead_dict["data"] = {"nodes": [{"id": "old"}], "edges": []}
        remote_ahead = _fake_remote_flow(_FLOW_ID_2, remote_ahead_dict)

        client = _make_client_mock()
        client.get_flow.side_effect = [remote_synced, remote_ahead]
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p_synced), str(p_ahead)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# status_command — new (exits 1)
# ---------------------------------------------------------------------------


class TestStatusCommandNew:
    def test_not_found_on_remote_gives_new_status(self, tmp_path):
        """Remote raises LangflowNotFoundError → status 'new' → exits 1."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(get_flow_side_effect=_FakeLangflowNotFoundError("not found"))
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_not_found_does_not_call_model_dump(self, tmp_path):
        """When flow is new (not found), no model_dump call is made."""
        p = _write_flow(tmp_path, "flow.json")
        remote = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _make_client_mock(get_flow_side_effect=_FakeLangflowNotFoundError("not found"))
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit):
            _run_status([str(p)], sdk_triple=triple)
        remote.model_dump.assert_not_called()


# ---------------------------------------------------------------------------
# status_command — no-id (exits 1)
# ---------------------------------------------------------------------------


class TestStatusCommandNoId:
    def test_flow_without_id_gives_no_id_status(self, tmp_path):
        """Flow file with no 'id' field → status 'no-id' → exits 1."""
        p = tmp_path / "no_id.json"
        p.write_text(json.dumps({"name": "Orphan", "data": {}}), encoding="utf-8")
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_flow_with_null_id_gives_no_id_status(self, tmp_path):
        """Flow file with id=null → status 'no-id' → exits 1."""
        p = tmp_path / "null_id.json"
        p.write_text(json.dumps({"id": None, "name": "NullId"}), encoding="utf-8")
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_no_id_flow_does_not_call_get_flow(self, tmp_path):
        """get_flow is never called when a flow has no id."""
        p = tmp_path / "no_id.json"
        p.write_text(json.dumps({"name": "Orphan"}), encoding="utf-8")
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit):
            _run_status([str(p)], sdk_triple=triple)
        client.get_flow.assert_not_called()


# ---------------------------------------------------------------------------
# status_command — error cases (exits 1)
# ---------------------------------------------------------------------------


class TestStatusCommandErrors:
    def test_invalid_json_gives_error_status(self, tmp_path):
        """Malformed JSON → status 'error' → exits 1."""
        p = tmp_path / "bad.json"
        p.write_text("this is not json{{", encoding="utf-8")
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_invalid_uuid_in_id_gives_error_status(self, tmp_path):
        """Flow with a non-UUID 'id' value → status 'error' → exits 1."""
        p = tmp_path / "bad_uuid.json"
        p.write_text(json.dumps({"id": "not-a-valid-uuid", "name": "BadId"}), encoding="utf-8")
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_generic_client_get_flow_exception_gives_error_status(self, tmp_path):
        """Unexpected exception from client.get_flow → status 'error' → exits 1."""
        p = _write_flow(tmp_path, "flow.json")
        client = _make_client_mock(get_flow_side_effect=RuntimeError("network timeout"))
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_error_on_one_flow_still_processes_others(self, tmp_path):
        """An error on flow 1 doesn't abort processing of flow 2."""
        p_bad = tmp_path / "bad.json"
        p_bad.write_text("{{invalid", encoding="utf-8")
        p_good = _write_flow(tmp_path, "good.json")
        remote = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p_bad), str(p_good)], sdk_triple=triple)
        # Exits 1 due to the error flow; the good flow was also processed
        assert exc_info.value.exit_code == 1
        client.get_flow.assert_called_once()

    def test_missing_file_in_flow_paths_gives_error_status(self, tmp_path):
        """A path that doesn't exist → error status → exits 1."""
        nonexistent = tmp_path / "ghost.json"
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(nonexistent)], sdk_triple=triple)
        assert exc_info.value.exit_code == 1

    def test_invalid_json_does_not_call_get_flow(self, tmp_path):
        """get_flow is never called when JSON parsing fails."""
        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit):
            _run_status([str(p)], sdk_triple=triple)
        client.get_flow.assert_not_called()


# ---------------------------------------------------------------------------
# status_command — no local files
# ---------------------------------------------------------------------------


class TestStatusCommandNoLocalFiles:
    def test_empty_dir_no_paths_exits_0_with_warning(self, tmp_path):
        """No flow files found and show_remote_only=False → exits 0 (via typer.Exit(0))."""
        d = tmp_path / "empty"
        d.mkdir()
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([], dir_path=str(d), sdk_triple=triple, show_remote_only=False)
        assert exc_info.value.exit_code == 0

    def test_empty_dir_no_paths_does_not_call_get_flow(self, tmp_path):
        """When no files found, get_flow is never invoked."""
        d = tmp_path / "empty"
        d.mkdir()
        client = _make_client_mock()
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit):
            _run_status([], dir_path=str(d), sdk_triple=triple, show_remote_only=False)
        client.get_flow.assert_not_called()

    def test_no_files_with_show_remote_only_continues(self, tmp_path):
        """show_remote_only=True with no local files → proceeds to list_flows."""
        d = tmp_path / "empty"
        d.mkdir()
        remote = MagicMock()
        remote.id = _FLOW_ID
        remote.name = "RemoteFlow"
        client = _make_client_mock(list_flows_result=[remote])
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([], dir_path=str(d), sdk_triple=triple, show_remote_only=True)
        # remote-only entries are not synced → exits 1
        assert exc_info.value.exit_code == 1
        client.list_flows.assert_called_once()


# ---------------------------------------------------------------------------
# status_command — remote-only
# ---------------------------------------------------------------------------


class TestStatusCommandRemoteOnly:
    def test_show_remote_only_calls_list_flows(self, tmp_path):
        """show_remote_only=True → client.list_flows(get_all=True) is called."""
        p = _write_flow(tmp_path, "flow.json")
        remote_local = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _make_client_mock(remote_flow=remote_local, list_flows_result=[])
        triple = _make_sdk_triple(client)

        _run_status([str(p)], sdk_triple=triple, show_remote_only=True)
        client.list_flows.assert_called_once_with(get_all=True)

    def test_without_show_remote_only_does_not_call_list_flows(self, tmp_path):
        """show_remote_only=False → list_flows is never called."""
        p = _write_flow(tmp_path, "flow.json")
        remote = _fake_remote_flow(flow_dict=_FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)

        _run_status([str(p)], sdk_triple=triple, show_remote_only=False)
        client.list_flows.assert_not_called()

    def test_remote_only_flows_excluded_if_seen_locally(self, tmp_path):
        """Flows already tracked locally are not added as remote-only entries."""
        p = _write_flow(tmp_path, "flow.json", _FLOW_DICT)
        remote_local = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)
        # list_flows returns the same flow that's tracked locally
        list_entry = MagicMock()
        list_entry.id = _FLOW_ID
        list_entry.name = "My Test Flow"
        client = _make_client_mock(remote_flow=remote_local, list_flows_result=[list_entry])
        triple = _make_sdk_triple(client)

        # All synced, no remote-only → exits 0 (no Exit raised)
        _run_status([str(p)], sdk_triple=triple, show_remote_only=True)

    def test_remote_only_untracked_flow_appended(self, tmp_path):
        """Flows on remote that have no local file appear as remote-only → exits 1."""
        p = _write_flow(tmp_path, "flow.json", _FLOW_DICT)
        remote_local = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)

        # A second remote flow that has no local counterpart
        remote_extra = MagicMock()
        remote_extra.id = _FLOW_ID_2
        remote_extra.name = "Remote Only Flow"

        local_entry = MagicMock()
        local_entry.id = _FLOW_ID
        local_entry.name = "My Test Flow"

        client = _make_client_mock(remote_flow=remote_local, list_flows_result=[local_entry, remote_extra])
        triple = _make_sdk_triple(client)

        with pytest.raises(typer.Exit) as exc_info:
            _run_status([str(p)], sdk_triple=triple, show_remote_only=True)
        assert exc_info.value.exit_code == 1

    def test_list_flows_exception_prints_warning_and_continues(self, tmp_path):
        """If list_flows raises, a warning is printed but the command continues."""
        p = _write_flow(tmp_path, "flow.json", _FLOW_DICT)
        remote_local = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)
        client = _make_client_mock(remote_flow=remote_local)
        client.list_flows.side_effect = RuntimeError("list_flows failed")
        triple = _make_sdk_triple(client)

        # Should not raise an unexpected exception — synced flow still exits 0
        _run_status([str(p)], sdk_triple=triple, show_remote_only=True)


# ---------------------------------------------------------------------------
# status_command — config error
# ---------------------------------------------------------------------------


class TestStatusCommandConfigError:
    def test_config_error_exits_1(self, tmp_path):
        """ConfigError from resolve_environment → exits 1."""
        from lfx.cli.status import status_command
        from lfx.config import ConfigError

        p = _write_flow(tmp_path, "flow.json")
        triple = _make_sdk_triple()

        with (
            patch("lfx.cli.status._load_sdk", return_value=triple),
            patch("lfx.config.resolve_environment", side_effect=ConfigError("bad config")),
            pytest.raises(typer.Exit) as exc_info,
        ):
            status_command(
                dir_path=None,
                flow_paths=[str(p)],
                env="nonexistent",
                environments_file=str(tmp_path / "missing.toml"),
                target=None,
                api_key=None,
                show_remote_only=False,
            )
        assert exc_info.value.exit_code == 1

    def test_missing_environments_file_exits_1(self, tmp_path):
        """A non-existent --environments-file passed through config → exits 1."""
        from lfx.cli.status import status_command

        p = _write_flow(tmp_path, "flow.json")
        triple = _make_sdk_triple()

        with (
            patch("lfx.cli.status._load_sdk", return_value=triple),
            pytest.raises(typer.Exit) as exc_info,
        ):
            status_command(
                dir_path=None,
                flow_paths=[str(p)],
                env="ci",
                environments_file=str(tmp_path / "does_not_exist.toml"),
                target=None,
                api_key=None,
                show_remote_only=False,
            )
        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# status_command — all synced → exits 0
# ---------------------------------------------------------------------------


class TestStatusCommandAllSynced:
    def test_all_synced_no_exit_raised(self, tmp_path):
        """When every local flow matches remote, status_command returns normally (exit 0)."""
        p = _write_flow(tmp_path, "flow.json", _FLOW_DICT)
        remote = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)

        # Must NOT raise typer.Exit
        _run_status([str(p)], sdk_triple=triple)

    def test_all_synced_does_not_raise_exit_1(self, tmp_path):
        """Confirm that Exit(1) is specifically not raised for all-synced scenario."""
        p = _write_flow(tmp_path, "flow.json", _FLOW_DICT)
        remote = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)

        try:
            _run_status([str(p)], sdk_triple=triple)
        except typer.Exit as exc:
            pytest.fail(f"Expected no Exit for all-synced but got Exit({exc.exit_code})")

    def test_dir_with_all_synced_files_exits_0(self, tmp_path):
        """--dir with all synced flows → no Exit raised."""
        d = tmp_path / "flows"
        d.mkdir()
        (d / "flow1.json").write_text(json.dumps(_FLOW_DICT), encoding="utf-8")

        remote = _fake_remote_flow(_FLOW_ID, _FLOW_DICT)
        client = _make_client_mock(remote_flow=remote)
        triple = _make_sdk_triple(client)

        _run_status([], dir_path=str(d), sdk_triple=triple)
