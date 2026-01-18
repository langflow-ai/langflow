"""Tests for MCP progress-aware timeouts."""

import asyncio

import pytest
from lfx.base.mcp.util import MCPProgressTimeoutController, MCPToolTimeoutConfig, call_tool_with_timeouts


class FakeSession:
    def __init__(
        self,
        behavior: str,
        *,
        total_duration: float = 0.2,
        progress_interval: float = 0.05,
        force_token: str | None = None,
    ) -> None:
        self.behavior = behavior
        self.total_duration = total_duration
        self.progress_interval = progress_interval
        self.force_token = force_token

    async def call_tool(self, _tool_name: str, arguments=None, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        token = self._extract_progress_token(arguments, kwargs)
        if self.force_token is not None:
            token = self.force_token

        if self.behavior == "no_progress":
            await asyncio.sleep(self.total_duration)
            return {"ok": True}

        if self.behavior == "periodic_progress":
            start = asyncio.get_running_loop().time()
            progress_value = 0.0
            while asyncio.get_running_loop().time() - start < self.total_duration:
                await asyncio.sleep(self.progress_interval)
                progress_value += 1.0
                if progress_callback:
                    await progress_callback({"progressToken": token, "progress": progress_value})
            return {"ok": True}

        if self.behavior == "continuous_progress":
            progress_value = 0.0
            try:
                while True:
                    await asyncio.sleep(self.progress_interval)
                    progress_value += 1.0
                    if progress_callback:
                        await progress_callback({"progressToken": token, "progress": progress_value})
            except asyncio.CancelledError:
                return {"cancelled": True}

        msg = f"Unknown behavior: {self.behavior}"
        raise ValueError(msg)

    @staticmethod
    def _extract_progress_token(arguments: dict | None, kwargs: dict) -> str | None:
        if isinstance(arguments, dict):
            meta = arguments.get("_meta")
            if isinstance(meta, dict) and meta.get("progressToken"):
                return meta.get("progressToken")
        meta = kwargs.get("_meta") or kwargs.get("meta") or kwargs.get("metadata") or kwargs.get("request_meta")
        if isinstance(meta, dict):
            return meta.get("progressToken")
        return kwargs.get("progress_token")


class NoKwargsSession:
    def __init__(self, sleep_seconds: float = 0.0) -> None:
        self.sleep_seconds = sleep_seconds
        self.last_arguments = None

    async def call_tool(self, _tool_name: str, arguments: dict):
        self.last_arguments = arguments
        if self.sleep_seconds:
            await asyncio.sleep(self.sleep_seconds)
        return {"ok": True}


@pytest.mark.asyncio
async def test_no_progress_triggers_inactivity_timeout():
    session = FakeSession("no_progress", total_duration=1.2)
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.5,
        max_total_timeout_seconds=2.0,
    )

    with pytest.raises(asyncio.TimeoutError):
        await call_tool_with_timeouts(session, "tool", {}, config)


@pytest.mark.asyncio
async def test_periodic_progress_refreshes_deadline():
    session = FakeSession("periodic_progress", total_duration=1.2, progress_interval=0.2)
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.6,
        max_total_timeout_seconds=3.0,
    )

    result = await call_tool_with_timeouts(session, "tool", {}, config)
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_continuous_progress_hits_max_total_timeout():
    session = FakeSession("continuous_progress", progress_interval=0.1)
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.5,
        max_total_timeout_seconds=0.8,
    )

    with pytest.raises(asyncio.TimeoutError):
        await call_tool_with_timeouts(session, "tool", {}, config)


@pytest.mark.asyncio
async def test_late_progress_after_completion_is_ignored():
    controller = MCPProgressTimeoutController(
        MCPToolTimeoutConfig(
            refresh_timeout_on_progress=True,
            inactivity_timeout_seconds=0.2,
            max_total_timeout_seconds=0.5,
            progress_refresh_interval_seconds=0.05,
        )
    )
    token = controller.progress_token
    assert token is not None

    await asyncio.sleep(0.06)
    accepted = await controller.handle_progress({"progressToken": token, "progress": 1})
    assert accepted is True

    controller.mark_complete()
    accepted = await controller.handle_progress({"progressToken": token, "progress": 2})
    assert accepted is False


@pytest.mark.asyncio
async def test_unknown_progress_token_is_ignored():
    controller = MCPProgressTimeoutController(
        MCPToolTimeoutConfig(
            refresh_timeout_on_progress=True,
            inactivity_timeout_seconds=0.2,
            max_total_timeout_seconds=0.5,
        )
    )

    accepted = await controller.handle_progress({"progressToken": "unknown", "progress": 1})
    assert accepted is False


@pytest.mark.asyncio
async def test_fallback_injects_progress_token_when_kwargs_unsupported():
    session = NoKwargsSession()
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.3,
        max_total_timeout_seconds=1.0,
    )

    result = await call_tool_with_timeouts(session, "tool", {}, config)
    assert result == {"ok": True}
    assert isinstance(session.last_arguments, dict)
    assert session.last_arguments.get("_meta", {}).get("progressToken")


@pytest.mark.asyncio
async def test_token_delivery_failure_triggers_inactivity_timeout():
    session = NoKwargsSession(sleep_seconds=1.2)
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.5,
        max_total_timeout_seconds=2.0,
    )

    start = asyncio.get_running_loop().time()
    with pytest.raises(asyncio.TimeoutError):
        await call_tool_with_timeouts(session, "tool", {"_meta": "not-dict"}, config)
    elapsed = asyncio.get_running_loop().time() - start
    assert session.last_arguments == {"_meta": "not-dict"}
    assert elapsed >= config.inactivity_timeout_seconds * 0.9
    assert elapsed < config.max_total_timeout_seconds
