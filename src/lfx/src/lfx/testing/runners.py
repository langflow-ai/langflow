"""Flow runner classes and internal helpers for local and remote execution."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

from lfx.testing.result import FlowResult, _build_result, _build_result_from_sdk_response

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_tweaks(flow_dict: dict[str, Any], tweaks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return a *deep copy* of *flow_dict* with template field values patched.

    *tweaks* maps a node identifier -- one of the node's ``id``, ``data.type``,
    or ``display_name`` -- to a ``{field_name: new_value}`` dict.  All nodes
    whose identifier matches a tweak key are updated.
    """
    flow = copy.deepcopy(flow_dict)
    nodes = flow.get("data", {}).get("nodes", [])
    for node in nodes:
        node_data: dict = node.get("data") or {}
        node_id: str = node.get("id", "")
        node_type: str = node_data.get("type", "")
        node_obj: dict = node_data.get("node") or {}
        display_name: str = node_obj.get("display_name", "")
        template: dict = node_obj.get("template") or {}

        for tweak_key, field_overrides in tweaks.items():
            if tweak_key not in (node_id, node_type, display_name):
                continue
            for fname, fvalue in field_overrides.items():
                if fname not in template:
                    continue
                if isinstance(template[fname], dict):
                    template[fname]["value"] = fvalue
                else:
                    template[fname] = fvalue
    return flow


def _load_dotenv(env_file: str | Path) -> None:
    """Load environment variables from *env_file* using python-dotenv."""
    from dotenv import load_dotenv

    load_dotenv(str(env_file), override=True)


def _resolve_flow_args(
    flow: str | Path | dict[str, Any],
    tweaks: dict[str, dict[str, Any]] | None,
    base_dir: Path,
) -> tuple[Path | None, str | None]:
    """Return ``(script_path, flow_json)`` suitable for passing to ``run_flow()``.

    When *tweaks* are requested for a JSON flow, the file is loaded, patched,
    and returned as an inline JSON string so that ``run_flow()`` picks up the
    overrides without modifying any file on disk.
    """
    if isinstance(flow, dict):
        patched = _apply_tweaks(flow, tweaks) if tweaks else flow
        return None, json.dumps(patched)

    flow_path = Path(flow)
    if not flow_path.is_absolute():
        flow_path = base_dir / flow_path

    if tweaks and flow_path.suffix.lower() == ".json":
        try:
            raw_dict = json.loads(flow_path.read_text(encoding="utf-8"))
            return None, json.dumps(_apply_tweaks(raw_dict, tweaks))
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).debug(
                "Failed to apply tweaks to %s; using unmodified flow", flow_path, exc_info=True
            )

    return flow_path, None


# ---------------------------------------------------------------------------
# Async core execution
# ---------------------------------------------------------------------------


async def _run_async(
    *,
    script_path: Path | None,
    flow_json: str | None,
    input_value: str | None,
    check_variables: bool,
    global_variables: dict[str, str] | None,
    session_id: str | None,
    user_id: str | None,
    timing: bool,
    timeout: float | None,
) -> dict[str, Any]:
    """Invoke ``run_flow()`` with an optional timeout; always returns a dict."""
    from lfx.run.base import RunError, run_flow

    async def _inner() -> dict:
        return await run_flow(
            script_path=script_path,
            flow_json=flow_json,
            input_value=input_value,
            check_variables=check_variables,
            global_variables=global_variables,
            session_id=session_id,
            user_id=user_id,
            timing=timing,
        )

    try:
        if timeout is not None:
            return await asyncio.wait_for(_inner(), timeout=timeout)
        return await _inner()
    except asyncio.TimeoutError:
        return {
            "success": False,
            "type": "error",
            "exception_type": "TimeoutError",
            "exception_message": f"Flow execution timed out after {timeout:.1f}s",
        }
    except RunError as exc:
        orig = exc.original_exception
        return {
            "success": False,
            "type": "error",
            "exception_type": type(orig).__name__ if orig else "RunError",
            "exception_message": str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "type": "error",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }


def _run_sync(**kwargs: Any) -> dict[str, Any]:
    """Run ``_run_async`` synchronously, handling already-running event loops.

    When called from inside a running event loop (e.g. a ``pytest-asyncio``
    test that requests the sync ``flow_runner`` fixture), the coroutine is
    dispatched to a fresh thread with its own event loop so we don't deadlock.
    """
    coro = _run_async(**kwargs)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop -- safe to use asyncio.run() directly
        return asyncio.run(coro)

    # There is a running loop; run in an isolated thread to avoid deadlock
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        try:
            t = kwargs.get("timeout")
            return future.result(timeout=t)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "type": "error",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }


# ---------------------------------------------------------------------------
# Runner base helpers
# ---------------------------------------------------------------------------


def _import_remote_run_request():
    """Import and return the SDK ``RunRequest`` model with a helpful error."""
    try:
        from langflow_sdk.models import RunRequest  # type: ignore[import-untyped]
    except ImportError as exc:
        msg = "langflow-sdk is required for remote flow testing. Install: pip install langflow-sdk"
        raise ImportError(msg) from exc
    return RunRequest


def _build_remote_error_result(exc: Exception) -> FlowResult:
    """Return a standardized failed ``FlowResult`` for remote runner errors."""
    return FlowResult(
        status="error",
        text=None,
        messages=[],
        outputs={},
        logs="",
        error=str(exc),
        timing=None,
        raw={},
    )


class _BaseLocalFlowRunner:
    """Shared initialization and argument resolution for local flow runners."""

    def __init__(
        self,
        *,
        default_env_file: str | Path | None = None,
        default_timeout: float | None = None,
        base_dir: Path | None = None,
    ) -> None:
        self._default_env_file = default_env_file
        self._default_timeout = default_timeout
        self._base_dir = base_dir or Path.cwd()

    def _build_run_kwargs(
        self,
        flow: str | Path | dict[str, Any],
        input_value: str | None,
        *,
        tweaks: dict[str, dict[str, Any]] | None,
        global_variables: dict[str, str] | None,
        env_file: str | Path | None,
        timeout: float | None,
        check_variables: bool,
        session_id: str | None,
        user_id: str | None,
        timing: bool,
    ) -> dict[str, Any]:
        """Build keyword arguments shared by sync and async local execution."""
        if env_file or self._default_env_file:
            _load_dotenv(env_file or self._default_env_file)

        script_path, flow_json = _resolve_flow_args(flow, tweaks, self._base_dir)
        resolved_timeout = timeout if timeout is not None else self._default_timeout

        return {
            "script_path": script_path,
            "flow_json": flow_json,
            "input_value": input_value,
            "check_variables": check_variables,
            "global_variables": global_variables,
            "session_id": session_id,
            "user_id": user_id,
            "timing": timing,
            "timeout": resolved_timeout,
        }


class _BaseRemoteFlowRunner:
    """Shared request/error handling for sync and async remote runners."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def _build_run_request(
        self,
        *,
        input_value: str,
        input_type: str,
        output_type: str,
        tweaks: dict[str, Any] | None,
    ):
        """Create an SDK ``RunRequest`` for remote execution."""
        run_request_model = _import_remote_run_request()
        return run_request_model(
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
            tweaks=tweaks,
        )


# ---------------------------------------------------------------------------
# Callable classes
# ---------------------------------------------------------------------------


class LocalFlowRunner(_BaseLocalFlowRunner):
    """Sync callable returned by the :func:`flow_runner` fixture.

    Instantiate via the ``flow_runner`` pytest fixture -- do not construct
    directly in test code.  Call it like a function::

        def test_greeting(flow_runner):
            result = flow_runner("flows/greeting.json", input_value="Hello")
            assert result.status == "success"
            assert "hello" in result.text.lower()

    The first positional argument can be:

    * A path string or :class:`~pathlib.Path` to a ``.json`` or ``.py`` flow file.
    * A ``dict`` (already-parsed flow JSON).

    Relative paths are resolved against ``--lfx-flow-dir`` (default: ``cwd``).
    """

    def __call__(
        self,
        flow: str | Path | dict[str, Any],
        input_value: str | None = None,
        *,
        tweaks: dict[str, dict[str, Any]] | None = None,
        global_variables: dict[str, str] | None = None,
        env_file: str | Path | None = None,
        timeout: float | None = None,
        check_variables: bool = False,
        session_id: str | None = None,
        user_id: str | None = None,
        timing: bool = False,
    ) -> FlowResult:
        """Execute a flow synchronously and return a :class:`FlowResult`.

        Args:
            flow: Path (``.json``/``.py``) or parsed flow dict.
            input_value: Chat/text input string to pass into the flow.
            tweaks: Component-level overrides -- ``{node_id|type|name: {field: value}}``.
            global_variables: Key->value pairs injected into the graph context.
            env_file: ``.env`` file loaded before execution (overrides fixture default).
            timeout: Seconds before aborting; ``None`` means no limit.
            check_variables: Validate that global variables exist in the environment.
            session_id: Session ID for memory isolation between calls.
            user_id: User ID attached to the graph.
            timing: Include per-component timing in :attr:`FlowResult.timing`.
        """
        raw = _run_sync(
            **self._build_run_kwargs(
                flow,
                input_value,
                tweaks=tweaks,
                global_variables=global_variables,
                env_file=env_file,
                timeout=timeout,
                check_variables=check_variables,
                session_id=session_id,
                user_id=user_id,
                timing=timing,
            )
        )
        return _build_result(raw)


class AsyncLocalFlowRunner(_BaseLocalFlowRunner):
    """Async callable returned by the :func:`async_flow_runner` fixture.

    Use with ``await`` inside an ``async def`` test::

        async def test_greeting(async_flow_runner):
            result = await async_flow_runner("flows/greeting.json", input_value="Hello")
            assert result.status == "success"
    """

    async def __call__(
        self,
        flow: str | Path | dict[str, Any],
        input_value: str | None = None,
        *,
        tweaks: dict[str, dict[str, Any]] | None = None,
        global_variables: dict[str, str] | None = None,
        env_file: str | Path | None = None,
        timeout: float | None = None,
        check_variables: bool = False,
        session_id: str | None = None,
        user_id: str | None = None,
        timing: bool = False,
    ) -> FlowResult:
        """Execute a flow asynchronously and return a :class:`FlowResult`."""
        raw = await _run_async(
            **self._build_run_kwargs(
                flow,
                input_value,
                tweaks=tweaks,
                global_variables=global_variables,
                env_file=env_file,
                timeout=timeout,
                check_variables=check_variables,
                session_id=session_id,
                user_id=user_id,
                timing=timing,
            )
        )
        return _build_result(raw)


# ---------------------------------------------------------------------------
# Remote runners (requires langflow-sdk)
# ---------------------------------------------------------------------------


class RemoteFlowRunner(_BaseRemoteFlowRunner):
    """Sync callable that runs flows against a live Langflow instance.

    Returned by :func:`flow_runner` when ``--langflow-env`` or
    ``--langflow-url`` is passed to pytest.  Call it like a function::

        def test_greeting(flow_runner):
            result = flow_runner("greeting-endpoint", "Hello!")
            assert result.first_text_output() is not None

    The first argument is a flow endpoint name or UUID (not a local file
    path).  Keyword arguments that only apply to local execution (e.g.
    ``env_file``, ``global_variables``) are accepted but silently ignored
    so that test code is portable between local and remote modes.
    """

    def __call__(
        self,
        flow_id_or_endpoint: str,
        input_value: str = "",
        *,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> FlowResult:
        """Run *flow_id_or_endpoint* against the remote instance."""
        request = self._build_run_request(
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
            tweaks=tweaks,
        )

        try:
            response = self._client.run_flow(flow_id_or_endpoint, request)
        except Exception as exc:  # noqa: BLE001
            return _build_remote_error_result(exc)

        return _build_result_from_sdk_response(response)


class AsyncRemoteFlowRunner(_BaseRemoteFlowRunner):
    """Async callable that runs flows against a live Langflow instance.

    Returned by :func:`async_flow_runner` when ``--langflow-env`` or
    ``--langflow-url`` is passed to pytest.  Use with ``await``::

        async def test_greeting(async_flow_runner):
            result = await async_flow_runner("greeting-endpoint", "Hello!")
            assert result.first_text_output() is not None
    """

    async def __call__(
        self,
        flow_id_or_endpoint: str,
        input_value: str = "",
        *,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> FlowResult:
        """Run *flow_id_or_endpoint* asynchronously against the remote instance."""
        request = self._build_run_request(
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
            tweaks=tweaks,
        )

        try:
            response = await self._client.run_flow(flow_id_or_endpoint, request)
        except Exception as exc:  # noqa: BLE001
            return _build_remote_error_result(exc)

        return _build_result_from_sdk_response(response)
