"""Unit tests for lfx.testing — the flow_runner pytest plugin.

All tests mock ``_run_sync`` / ``_run_async`` so no real Langflow instance is needed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from lfx.testing import (
    AsyncLocalFlowRunner,
    FlowResult,
    LocalFlowRunner,
    _apply_tweaks,
    _build_result,
    _get_marker_arg,
    _resolve_flow_args,
    _resolve_runner_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUCCESS_RAW: dict = {
    "success": True,
    "result": "Hello, world!",
    "messages": [{"role": "assistant", "content": "Hello, world!"}],
    "outputs": {"answer": "Hello, world!"},
    "logs": "",
    "timing": None,
}

_ERROR_RAW: dict = {
    "success": False,
    "type": "error",
    "exception_message": "Something went wrong",
    "messages": [],
    "outputs": {},
    "logs": "",
}


def _make_flow_dict(
    *,
    node_id: str = "node-a",
    node_type: str = "OpenAI",
    display_name: str = "OpenAI",
    fields: dict | None = None,
) -> dict:
    """Return a minimal flow dict with a single node containing *fields* in its template."""
    template: dict = {}
    for fname, fvalue in (fields or {}).items():
        template[fname] = {"value": fvalue, "type": "str"}
    return {
        "id": "flow-1",
        "name": "Test Flow",
        "data": {
            "nodes": [
                {
                    "id": node_id,
                    "data": {
                        "id": node_id,
                        "type": node_type,
                        "node": {
                            "display_name": display_name,
                            "template": template,
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


# ---------------------------------------------------------------------------
# FlowResult
# ---------------------------------------------------------------------------


class TestFlowResult:
    def test_ok_when_success(self):
        r = FlowResult(
            status="success",
            text="hi",
            messages=[],
            outputs={},
            logs="",
            error=None,
            timing=None,
            raw={},
        )
        assert r.ok is True

    def test_not_ok_when_error(self):
        r = FlowResult(
            status="error",
            text=None,
            messages=[],
            outputs={},
            logs="",
            error="boom",
            timing=None,
            raw={},
        )
        assert r.ok is False

    def test_repr_truncates_long_text(self):
        long_text = "x" * 100
        r = FlowResult(
            status="success",
            text=long_text,
            messages=[],
            outputs={},
            logs="",
            error=None,
            timing=None,
            raw={},
        )
        assert "…" in repr(r)

    def test_repr_short_text(self):
        r = FlowResult(
            status="success",
            text="hi",
            messages=[],
            outputs={},
            logs="",
            error=None,
            timing=None,
            raw={},
        )
        assert "…" not in repr(r)

    def test_repr_none_text(self):
        r = FlowResult(
            status="error",
            text=None,
            messages=[],
            outputs={},
            logs="",
            error="boom",
            timing=None,
            raw={},
        )
        assert "None" in repr(r)


# ---------------------------------------------------------------------------
# _build_result
# ---------------------------------------------------------------------------


class TestBuildResult:
    def test_success_from_success_true(self):
        r = _build_result(_SUCCESS_RAW)
        assert r.status == "success"
        assert r.ok is True

    def test_error_from_success_false(self):
        r = _build_result(_ERROR_RAW)
        assert r.status == "error"
        assert r.ok is False
        assert r.error == "Something went wrong"

    def test_error_from_type_error_key(self):
        raw = {"type": "error", "exception_message": "oops"}
        r = _build_result(raw)
        assert r.status == "error"

    def test_text_from_result_key(self):
        r = _build_result({"result": "answer"})
        assert r.text == "answer"

    def test_text_from_text_key(self):
        r = _build_result({"text": "answer"})
        assert r.text == "answer"

    def test_text_from_output_key(self):
        r = _build_result({"output": "answer"})
        assert r.text == "answer"

    def test_text_priority_result_over_text(self):
        r = _build_result({"result": "primary", "text": "secondary"})
        assert r.text == "primary"

    def test_text_non_string_serialised(self):
        r = _build_result({"result": {"key": "val"}})
        assert r.text == '{"key": "val"}'

    def test_messages_extracted(self):
        r = _build_result({"messages": [{"role": "user"}]})
        assert r.messages == [{"role": "user"}]

    def test_messages_defaults_to_empty_list(self):
        r = _build_result({})
        assert r.messages == []

    def test_messages_non_list_defaults_to_empty(self):
        r = _build_result({"messages": "bad"})
        assert r.messages == []

    def test_outputs_from_outputs_key(self):
        r = _build_result({"outputs": {"k": "v"}})
        assert r.outputs == {"k": "v"}

    def test_outputs_from_result_dict_fallback(self):
        r = _build_result({"result_dict": {"k": "v"}})
        assert r.outputs == {"k": "v"}

    def test_timing_propagated(self):
        r = _build_result({"timing": {"node1": 0.5}})
        assert r.timing == {"node1": 0.5}

    def test_timing_absent(self):
        r = _build_result({})
        assert r.timing is None

    def test_logs_propagated(self):
        r = _build_result({"logs": "some log"})
        assert r.logs == "some log"

    def test_error_fallback_unknown(self):
        r = _build_result({"success": False})
        assert r.error == "Unknown error"

    def test_raw_preserved(self):
        raw = {"success": True, "result": "x"}
        r = _build_result(raw)
        assert r.raw is raw


# ---------------------------------------------------------------------------
# _apply_tweaks
# ---------------------------------------------------------------------------


class TestApplyTweaks:
    def test_tweak_by_node_type(self):
        flow = _make_flow_dict(node_type="OpenAI", fields={"model_name": "gpt-4"})
        patched = _apply_tweaks(flow, {"OpenAI": {"model_name": "gpt-4o-mini"}})
        template = patched["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["model_name"]["value"] == "gpt-4o-mini"

    def test_tweak_by_node_id(self):
        flow = _make_flow_dict(node_id="abc-123", fields={"temperature": 0.7})
        patched = _apply_tweaks(flow, {"abc-123": {"temperature": 0.0}})
        template = patched["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["temperature"]["value"] == 0.0

    def test_tweak_by_display_name(self):
        flow = _make_flow_dict(display_name="My OpenAI", fields={"max_tokens": 100})
        patched = _apply_tweaks(flow, {"My OpenAI": {"max_tokens": 200}})
        template = patched["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["max_tokens"]["value"] == 200

    def test_unknown_tweak_key_ignored(self):
        flow = _make_flow_dict(fields={"temperature": 0.7})
        patched = _apply_tweaks(flow, {"NonExistentNode": {"temperature": 0.0}})
        template = patched["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["temperature"]["value"] == 0.7

    def test_unknown_field_ignored(self):
        flow = _make_flow_dict(node_type="OpenAI", fields={"model_name": "gpt-4"})
        patched = _apply_tweaks(flow, {"OpenAI": {"nonexistent_field": "value"}})
        template = patched["data"]["nodes"][0]["data"]["node"]["template"]
        assert "nonexistent_field" not in template

    def test_does_not_modify_original(self):
        flow = _make_flow_dict(node_type="OpenAI", fields={"model_name": "gpt-4"})
        _apply_tweaks(flow, {"OpenAI": {"model_name": "gpt-4o-mini"}})
        # Original should be unchanged
        template = flow["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["model_name"]["value"] == "gpt-4"

    def test_no_tweaks_returns_identical_structure(self):
        flow = _make_flow_dict(fields={"k": "v"})
        patched = _apply_tweaks(flow, {})
        assert patched["data"]["nodes"][0]["data"]["node"]["template"]["k"]["value"] == "v"


# ---------------------------------------------------------------------------
# _resolve_flow_args
# ---------------------------------------------------------------------------


class TestResolveFlowArgs:
    def test_dict_flow_no_tweaks(self):
        flow = {"data": {"nodes": [], "edges": []}}
        script_path, flow_json = _resolve_flow_args(flow, None, Path("/base"))
        assert script_path is None
        assert json.loads(flow_json) == flow  # type: ignore[arg-type]

    def test_dict_flow_with_tweaks(self):
        flow = _make_flow_dict(node_type="OpenAI", fields={"model_name": "gpt-4"})
        _, flow_json = _resolve_flow_args(flow, {"OpenAI": {"model_name": "gpt-4o-mini"}}, Path("/base"))
        parsed = json.loads(flow_json)  # type: ignore[arg-type]
        template = parsed["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["model_name"]["value"] == "gpt-4o-mini"

    def test_json_file_without_tweaks(self, tmp_path):
        flow = {"data": {"nodes": [], "edges": []}}
        p = tmp_path / "flow.json"
        p.write_text(json.dumps(flow))
        script_path, flow_json = _resolve_flow_args(p, None, tmp_path)
        assert script_path == p
        assert flow_json is None

    def test_json_file_with_tweaks_inlines(self, tmp_path):
        flow = _make_flow_dict(node_type="OpenAI", fields={"model_name": "gpt-4"})
        p = tmp_path / "flow.json"
        p.write_text(json.dumps(flow))
        script_path, flow_json = _resolve_flow_args(p, {"OpenAI": {"model_name": "gpt-4o-mini"}}, tmp_path)
        assert script_path is None
        parsed = json.loads(flow_json)  # type: ignore[arg-type]
        template = parsed["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["model_name"]["value"] == "gpt-4o-mini"

    def test_py_file_with_tweaks_uses_file_path(self, tmp_path):
        p = tmp_path / "flow.py"
        p.write_text("# python flow")
        script_path, flow_json = _resolve_flow_args(p, {"SomeNode": {"field": "value"}}, tmp_path)
        # .py files are never inlined; tweaks ignored for Python flows
        assert script_path == p
        assert flow_json is None

    def test_relative_path_resolved_against_base_dir(self, tmp_path):
        flow = {"data": {"nodes": [], "edges": []}}
        p = tmp_path / "flow.json"
        p.write_text(json.dumps(flow))
        script_path, _ = _resolve_flow_args("flow.json", None, tmp_path)
        assert script_path == tmp_path / "flow.json"


# ---------------------------------------------------------------------------
# LocalFlowRunner
# ---------------------------------------------------------------------------


class TestLocalFlowRunner:
    def test_success_result(self):
        with patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW) as mock_run:
            runner = LocalFlowRunner()
            result = runner({"data": {"nodes": [], "edges": []}}, input_value="hi")
        assert result.ok
        assert result.text == "Hello, world!"
        mock_run.assert_called_once()

    def test_error_result(self):
        with patch("lfx.testing.runners._run_sync", return_value=_ERROR_RAW):
            runner = LocalFlowRunner()
            result = runner({"data": {"nodes": [], "edges": []}})
        assert not result.ok
        assert result.error == "Something went wrong"

    def test_default_timeout_used_when_no_per_call_timeout(self):
        with patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW) as mock_run:
            runner = LocalFlowRunner(default_timeout=30.0)
            runner({"data": {"nodes": [], "edges": []}})
        assert mock_run.call_args.kwargs["timeout"] == 30.0

    def test_per_call_timeout_overrides_default(self):
        with patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW) as mock_run:
            runner = LocalFlowRunner(default_timeout=30.0)
            runner({"data": {"nodes": [], "edges": []}}, timeout=5.0)
        assert mock_run.call_args.kwargs["timeout"] == 5.0

    def test_env_file_loaded(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("MY_VAR=1\n")
        with (
            patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW),
            patch("lfx.testing.runners._load_dotenv") as mock_load,
        ):
            runner = LocalFlowRunner(default_env_file=str(env_file))
            runner({"data": {"nodes": [], "edges": []}})
        mock_load.assert_called_once_with(str(env_file))

    def test_per_call_env_file_overrides_default(self, tmp_path):
        default_env = tmp_path / "default.env"
        per_call_env = tmp_path / "per_call.env"
        default_env.write_text("A=1\n")
        per_call_env.write_text("B=2\n")
        with (
            patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW),
            patch("lfx.testing.runners._load_dotenv") as mock_load,
        ):
            runner = LocalFlowRunner(default_env_file=str(default_env))
            runner({"data": {"nodes": [], "edges": []}}, env_file=str(per_call_env))
        mock_load.assert_called_once_with(str(per_call_env))

    def test_no_env_file_no_load(self):
        with (
            patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW),
            patch("lfx.testing.runners._load_dotenv") as mock_load,
        ):
            runner = LocalFlowRunner()
            runner({"data": {"nodes": [], "edges": []}})
        mock_load.assert_not_called()

    def test_tweaks_applied(self):
        flow = _make_flow_dict(node_type="OpenAI", fields={"model_name": "gpt-4"})
        with patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW) as mock_run:
            runner = LocalFlowRunner()
            runner(flow, tweaks={"OpenAI": {"model_name": "gpt-4o-mini"}})
        # When tweaks are provided for a dict flow, flow_json is passed (not script_path)
        kwargs = mock_run.call_args.kwargs
        assert kwargs["flow_json"] is not None
        parsed = json.loads(kwargs["flow_json"])
        template = parsed["data"]["nodes"][0]["data"]["node"]["template"]
        assert template["model_name"]["value"] == "gpt-4o-mini"

    def test_base_dir_resolved(self, tmp_path):
        flow_file = tmp_path / "my_flow.json"
        flow_file.write_text(json.dumps({"data": {"nodes": [], "edges": []}}))
        with patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW) as mock_run:
            runner = LocalFlowRunner(base_dir=tmp_path)
            runner("my_flow.json")
        kwargs = mock_run.call_args.kwargs
        assert kwargs["script_path"] == tmp_path / "my_flow.json"


# ---------------------------------------------------------------------------
# AsyncLocalFlowRunner
# ---------------------------------------------------------------------------


class TestAsyncLocalFlowRunner:
    async def test_success_result(self):
        with patch("lfx.testing.runners._run_async", new_callable=AsyncMock, return_value=_SUCCESS_RAW):
            runner = AsyncLocalFlowRunner()
            result = await runner({"data": {"nodes": [], "edges": []}}, input_value="hi")
        assert result.ok
        assert result.text == "Hello, world!"

    async def test_error_result(self):
        with patch("lfx.testing.runners._run_async", new_callable=AsyncMock, return_value=_ERROR_RAW):
            runner = AsyncLocalFlowRunner()
            result = await runner({"data": {"nodes": [], "edges": []}})
        assert not result.ok
        assert result.error == "Something went wrong"

    async def test_default_timeout_used(self):
        with patch("lfx.testing.runners._run_async", new_callable=AsyncMock, return_value=_SUCCESS_RAW) as mock_run:
            runner = AsyncLocalFlowRunner(default_timeout=45.0)
            await runner({"data": {"nodes": [], "edges": []}})
        assert mock_run.call_args.kwargs["timeout"] == 45.0

    async def test_per_call_timeout_overrides_default(self):
        with patch("lfx.testing.runners._run_async", new_callable=AsyncMock, return_value=_SUCCESS_RAW) as mock_run:
            runner = AsyncLocalFlowRunner(default_timeout=45.0)
            await runner({"data": {"nodes": [], "edges": []}}, timeout=10.0)
        assert mock_run.call_args.kwargs["timeout"] == 10.0

    async def test_env_file_loaded(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("MY_VAR=1\n")
        with (
            patch("lfx.testing.runners._run_async", new_callable=AsyncMock, return_value=_SUCCESS_RAW),
            patch("lfx.testing.runners._load_dotenv") as mock_load,
        ):
            runner = AsyncLocalFlowRunner(default_env_file=str(env_file))
            await runner({"data": {"nodes": [], "edges": []}})
        mock_load.assert_called_once_with(str(env_file))


# ---------------------------------------------------------------------------
# _get_marker_arg
# ---------------------------------------------------------------------------


class TestGetMarkerArg:
    def test_returns_arg_when_marker_present(self):
        """Simulate a request node with a marker that has args."""
        marker = MagicMock()
        marker.args = ["/path/to/.env"]
        node = MagicMock()
        node.get_closest_marker.return_value = marker
        request = MagicMock()
        request.node = node

        result = _get_marker_arg(request, "lfx_env_file")
        assert result == "/path/to/.env"

    def test_returns_none_when_marker_absent(self):
        node = MagicMock()
        node.get_closest_marker.return_value = None
        request = MagicMock()
        request.node = node

        result = _get_marker_arg(request, "lfx_env_file")
        assert result is None

    def test_returns_none_when_marker_has_no_args(self):
        marker = MagicMock()
        marker.args = []
        node = MagicMock()
        node.get_closest_marker.return_value = marker
        request = MagicMock()
        request.node = node

        result = _get_marker_arg(request, "lfx_env_file")
        assert result is None


# ---------------------------------------------------------------------------
# _resolve_runner_config
# ---------------------------------------------------------------------------


class TestResolveRunnerConfig:
    def _make_request(
        self,
        *,
        env_file_marker: str | None = None,
        timeout_marker: float | None = None,
        cli_env_file: str | None = None,
        cli_timeout: float | None = None,
        cli_flow_dir: str | None = None,
    ) -> MagicMock:
        """Build a minimal mock pytest.FixtureRequest."""

        def get_closest_marker(name: str):
            if name == "lfx_env_file" and env_file_marker is not None:
                m = MagicMock()
                m.args = [env_file_marker]
                return m
            if name == "lfx_timeout" and timeout_marker is not None:
                m = MagicMock()
                m.args = [timeout_marker]
                return m
            return None

        node = MagicMock()
        node.get_closest_marker.side_effect = get_closest_marker

        def getoption(name, default=None):
            mapping = {
                "lfx_env_file": cli_env_file,
                "lfx_timeout": cli_timeout,
                "lfx_flow_dir": cli_flow_dir,
            }
            return mapping.get(name, default)

        config = MagicMock()
        config.getoption.side_effect = getoption

        request = MagicMock()
        request.node = node
        request.config = config
        return request

    def test_marker_takes_precedence_over_cli(self, monkeypatch):
        monkeypatch.delenv("LFX_ENV_FILE", raising=False)
        monkeypatch.delenv("LFX_TIMEOUT", raising=False)
        monkeypatch.delenv("LFX_FLOW_DIR", raising=False)
        req = self._make_request(
            env_file_marker=".env.marker",
            cli_env_file=".env.cli",
            timeout_marker=99.0,
            cli_timeout=30.0,
        )
        env_file, timeout, _ = _resolve_runner_config(req)
        assert env_file == ".env.marker"
        assert timeout == 99.0

    def test_cli_option_used_when_no_marker(self, monkeypatch):
        monkeypatch.delenv("LFX_ENV_FILE", raising=False)
        monkeypatch.delenv("LFX_TIMEOUT", raising=False)
        monkeypatch.delenv("LFX_FLOW_DIR", raising=False)
        req = self._make_request(cli_env_file=".env.cli", cli_timeout=15.0)
        env_file, timeout, _ = _resolve_runner_config(req)
        assert env_file == ".env.cli"
        assert timeout == 15.0

    def test_env_var_used_as_fallback(self, monkeypatch):
        monkeypatch.setenv("LFX_ENV_FILE", ".env.envvar")
        monkeypatch.setenv("LFX_TIMEOUT", "42")
        monkeypatch.delenv("LFX_FLOW_DIR", raising=False)
        req = self._make_request()
        env_file, timeout, _ = _resolve_runner_config(req)
        assert env_file == ".env.envvar"
        assert timeout == 42.0

    def test_all_none_when_nothing_configured(self, monkeypatch):
        monkeypatch.delenv("LFX_ENV_FILE", raising=False)
        monkeypatch.delenv("LFX_TIMEOUT", raising=False)
        monkeypatch.delenv("LFX_FLOW_DIR", raising=False)
        req = self._make_request()
        env_file, timeout, base_dir = _resolve_runner_config(req)
        assert env_file is None
        assert timeout is None
        assert base_dir is None

    def test_flow_dir_cli_option_resolved(self, monkeypatch, tmp_path):
        monkeypatch.delenv("LFX_ENV_FILE", raising=False)
        monkeypatch.delenv("LFX_TIMEOUT", raising=False)
        monkeypatch.delenv("LFX_FLOW_DIR", raising=False)
        req = self._make_request(cli_flow_dir=str(tmp_path))
        _, _, base_dir = _resolve_runner_config(req)
        assert base_dir == tmp_path

    def test_flow_dir_env_var_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("LFX_ENV_FILE", raising=False)
        monkeypatch.delenv("LFX_TIMEOUT", raising=False)
        monkeypatch.setenv("LFX_FLOW_DIR", str(tmp_path))
        req = self._make_request()
        _, _, base_dir = _resolve_runner_config(req)
        assert base_dir == tmp_path

    def test_invalid_timeout_env_var_ignored(self, monkeypatch):
        monkeypatch.delenv("LFX_ENV_FILE", raising=False)
        monkeypatch.setenv("LFX_TIMEOUT", "not-a-number")
        monkeypatch.delenv("LFX_FLOW_DIR", raising=False)
        req = self._make_request()
        _, timeout, _ = _resolve_runner_config(req)
        assert timeout is None


# ---------------------------------------------------------------------------
# pytest fixture integration — smoke test using the real fixtures
# ---------------------------------------------------------------------------


class TestFixtures:
    def test_flow_runner_fixture_returns_local_runner(self, flow_runner):
        assert isinstance(flow_runner, LocalFlowRunner)

    def test_async_flow_runner_fixture_returns_async_runner(self, async_flow_runner):
        assert isinstance(async_flow_runner, AsyncLocalFlowRunner)

    def test_flow_runner_fixture_runs_flow(self, flow_runner):
        with patch("lfx.testing.runners._run_sync", return_value=_SUCCESS_RAW):
            result = flow_runner({"data": {"nodes": [], "edges": []}}, input_value="hi")
        assert result.ok

    async def test_async_flow_runner_fixture_runs_flow(self, async_flow_runner):
        with patch("lfx.testing.runners._run_async", new_callable=AsyncMock, return_value=_SUCCESS_RAW):
            result = await async_flow_runner({"data": {"nodes": [], "edges": []}})
        assert result.ok
