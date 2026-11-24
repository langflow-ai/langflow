"""pytest plugin providing flow_runner fixtures for local Langflow flow execution.

The plugin is auto-discovered via the ``pytest11`` entry-point, so no
``conftest.py`` changes are needed.  Configure defaults via CLI options or
environment variables::

    pytest --lfx-env-file .env --lfx-timeout 60 tests/

Per-test overrides via markers::

    @pytest.mark.lfx_env_file(".env.test")
    @pytest.mark.lfx_timeout(30)
    def test_my_flow(flow_runner):
        result = flow_runner("flows/greeting.json", input_value="Hello")
        assert result.status == "success"
        assert "hello" in result.text.lower()

Tweaks (component-level field overrides, keyed by node id/type/display_name)::

    def test_with_tweaks(flow_runner):
        result = flow_runner(
            "flows/rag.json",
            input_value="What is Langflow?",
            tweaks={"OpenAI": {"model_name": "gpt-4o-mini", "temperature": 0.0}},
        )
        assert result.status == "success"

Async tests::

    async def test_async(async_flow_runner):
        result = await async_flow_runner("flows/greeting.json", input_value="Hi")
        assert result.status == "success"
"""

from __future__ import annotations

# -- plugin.py (pytest hooks & fixtures) -------------------------------------
from lfx.testing.plugin import (
    _SKIP_NO_REMOTE,
    _get_marker_arg,
    _resolve_async_remote_client,
    _resolve_remote_client,
    _resolve_runner_config,
    async_flow_runner,
    flow_runner,
    pytest_addoption,
    pytest_configure,
)

# -- result.py ---------------------------------------------------------------
from lfx.testing.result import FlowResult, _build_result, _build_result_from_sdk_response

# -- runners.py --------------------------------------------------------------
from lfx.testing.runners import (
    AsyncLocalFlowRunner,
    AsyncRemoteFlowRunner,
    LocalFlowRunner,
    RemoteFlowRunner,
    _apply_tweaks,
    _load_dotenv,
    _resolve_flow_args,
    _run_async,
    _run_sync,
)

__all__ = [
    "_SKIP_NO_REMOTE",
    "AsyncLocalFlowRunner",
    "AsyncRemoteFlowRunner",
    "FlowResult",
    "LocalFlowRunner",
    "RemoteFlowRunner",
    "_apply_tweaks",
    "_build_result",
    "_build_result_from_sdk_response",
    "_get_marker_arg",
    "_load_dotenv",
    "_resolve_async_remote_client",
    "_resolve_flow_args",
    "_resolve_remote_client",
    "_resolve_runner_config",
    "_run_async",
    "_run_sync",
    "async_flow_runner",
    "flow_runner",
    "pytest_addoption",
    "pytest_configure",
]
