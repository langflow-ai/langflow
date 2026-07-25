"""Webhook SSE subscribe-before-POST coverage (two clients / two event loops)."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from typing import TYPE_CHECKING, Any

import pytest
from httpx import AsyncClient

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID


def _run_on_private_loop(
    coro_factory: Callable[[], Any],
    *,
    name: str,
) -> tuple[threading.Thread, dict[str, Any]]:
    """Run an async callable on a dedicated thread + event loop."""
    box: dict[str, Any] = {}

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            box["result"] = loop.run_until_complete(coro_factory())
        except BaseException as exc:
            box["error"] = exc
        finally:
            with contextlib.suppress(Exception):
                loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    thread = threading.Thread(target=_runner, name=name, daemon=True)
    thread.start()
    return thread, box


def webhook_http_subscribe_before_post(
    *,
    base_url: str,
    api_key: str,
    flow_id: UUID,
    endpoint_name: str,
    payload: dict[str, Any],
    sse_cookies: dict[str, str] | None = None,
) -> list[str]:
    """Real HTTP subscribe-before-POST using two clients on two event loops.

    Prefer cookie auth on the SSE GET (read-only session). API-key auth on SSE
    updates ``last_used_at`` inside a request-scoped session that stays open for
    the whole stream; on SQLite that write lock deadlocks the webhook POST.
    """
    frames: list[str] = []
    frames_lock = threading.Lock()
    connected = threading.Event()
    ended = threading.Event()

    if sse_cookies:
        sse_url = f"{base_url}/api/v1/webhook-events/{flow_id}"
        sse_headers = {"Accept": "text/event-stream"}
    else:
        sse_url = f"{base_url}/api/v1/webhook-events/{flow_id}?x-api-key={api_key}"
        sse_headers = {"Accept": "text/event-stream"}
        sse_cookies = {}
    post_url = f"{base_url}/api/v1/webhook/{endpoint_name}"

    async def _listen() -> None:
        async with (
            AsyncClient(timeout=60.0, cookies=sse_cookies) as http,
            http.stream("GET", sse_url, headers=sse_headers) as response,
        ):
            assert response.status_code == 200, await response.aread()
            async for line in response.aiter_lines():
                with frames_lock:
                    frames.append(line)
                lowered = line.lower().strip()
                if lowered == "event: connected" or lowered.startswith("event: connected"):
                    connected.set()
                if lowered == "event: end" or lowered.startswith("event: end"):
                    ended.set()
                    return
                if lowered == "event: error" or lowered.startswith("event: error"):
                    ended.set()
                    return

    async def _post_after_connected() -> int:
        if not await asyncio.to_thread(connected.wait, 15.0):
            pytest.fail("SSE client did not receive event: connected within 15s")
        async with AsyncClient(timeout=60.0) as http:
            post = await http.post(
                post_url,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
            )
        assert post.status_code == 202, post.text
        return post.status_code

    listen_thread, listen_box = _run_on_private_loop(_listen, name="perf-webhook-sse")
    post_thread, post_box = _run_on_private_loop(_post_after_connected, name="perf-webhook-post")
    try:
        post_thread.join(timeout=90.0)
        if post_thread.is_alive():
            pytest.fail("webhook POST client did not finish within 90s")
        if "error" in post_box:
            raise post_box["error"]
        if not ended.wait(30.0):
            with frames_lock:
                snapshot = list(frames)
            pytest.fail(f"SSE client did not receive event: end within 30s; frames={snapshot!r}")
        return list(frames)
    finally:
        listen_thread.join(timeout=5.0)
        if "error" in listen_box and "error" not in post_box:
            raise listen_box["error"]
