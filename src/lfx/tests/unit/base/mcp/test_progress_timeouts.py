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
        _ = arguments
        progress_callback = kwargs.get("progress_callback")
        token = self._extract_progress_token(kwargs)
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
            while True:
                await asyncio.sleep(self.progress_interval)
                progress_value += 1.0
                if progress_callback:
                    await progress_callback({"progressToken": token, "progress": progress_value})

        msg = f"Unknown behavior: {self.behavior}"
        raise ValueError(msg)

    @staticmethod
    def _extract_progress_token(kwargs: dict) -> str | None:
        meta = kwargs.get("_meta") or kwargs.get("meta") or kwargs.get("metadata") or kwargs.get("request_meta")
        if isinstance(meta, dict):
            return meta.get("progressToken")
        return kwargs.get("progress_token")


@pytest.mark.asyncio
async def test_no_progress_triggers_inactivity_timeout():
    session = FakeSession("no_progress", total_duration=0.5)
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.2,
        max_total_timeout_seconds=1.0,
    )

    with pytest.raises(asyncio.TimeoutError):
        await call_tool_with_timeouts(session, "tool", {}, config)


@pytest.mark.asyncio
async def test_periodic_progress_refreshes_deadline():
    session = FakeSession("periodic_progress", total_duration=0.3, progress_interval=0.05)
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.2,
        max_total_timeout_seconds=1.0,
    )

    result = await call_tool_with_timeouts(session, "tool", {}, config)
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_continuous_progress_hits_max_total_timeout():
    session = FakeSession("continuous_progress", progress_interval=0.05)
    config = MCPToolTimeoutConfig(
        refresh_timeout_on_progress=True,
        inactivity_timeout_seconds=0.2,
        max_total_timeout_seconds=0.3,
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
        )
    )
    token = controller.progress_token
    assert token is not None

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
