"""Exercise polling deadlines through a real local HTTP connection."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from dataclasses import dataclass, field

import pytest
from lfx_bundles.socialscrape import socialscrape_common
from lfx_bundles.socialscrape.socialscrape_common import SocialScrapeAPIError, socialscrape_request

API_KEY = "test-placeholder"  # pragma: allowlist secret


@dataclass
class _PollingServer:
    url: str = ""
    streaming: asyncio.Event = field(default_factory=asyncio.Event)
    disconnected: asyncio.Event = field(default_factory=asyncio.Event)
    chunks_sent: int = 0


@pytest.fixture
async def polling_server(monkeypatch):
    state = _PollingServer()
    handlers = set()

    async def serve(reader, writer):
        task = asyncio.current_task()
        handlers.add(task)
        polling = False
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            polling = request.startswith(b"GET /v1/jobs/")
            data = {"text": "finished"} if polling else {"object": "job", "job_id": "job_test123"}
            body = json.dumps({"ok": True, "data": data}).encode()
            # Frequent chunks prevent the HTTP client's per-read timeout from firing.
            padding = 50 if polling else 0
            status = b"200 OK" if polling else b"202 Accepted"
            writer.write(
                b"HTTP/1.1 "
                + status
                + b"\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(body) + padding).encode()
                + b"\r\nConnection: close\r\n\r\n"
            )
            await writer.drain()
            for _ in range(padding):
                writer.write(b" ")
                await writer.drain()
                state.chunks_sent += 1
                state.streaming.set()
                await asyncio.sleep(0.05)
                if reader.at_eof():
                    state.disconnected.set()
                    return
            writer.write(body)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            if polling:
                state.disconnected.set()
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    state.url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    monkeypatch.setattr(socialscrape_common, "API_BASE_URL", state.url)
    monkeypatch.setattr(socialscrape_common, "JOB_POLL_SECONDS", 0.01)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    try:
        yield state
    finally:
        server.close()
        await server.wait_closed()
        remaining = list(handlers)
        for task in remaining:
            task.cancel()
        await asyncio.gather(*remaining, return_exceptions=True)


@pytest.mark.unit
async def test_polling_deadline_cancels_a_slow_response_body(polling_server, monkeypatch):
    monkeypatch.setattr(socialscrape_common, "JOB_WAIT_SECONDS", 0.5)

    with pytest.raises(SocialScrapeAPIError, match=r"still working.*job_test123"):
        await asyncio.wait_for(
            socialscrape_request("/v1/transcript", api_key=API_KEY, timeout=5),
            timeout=2,
        )

    assert polling_server.chunks_sent >= 2
    await asyncio.wait_for(polling_server.disconnected.wait(), timeout=1)


@pytest.mark.unit
async def test_caller_cancellation_closes_the_polling_connection(polling_server):
    request = asyncio.create_task(socialscrape_request("/v1/transcript", api_key=API_KEY, timeout=5))
    try:
        await asyncio.wait_for(polling_server.streaming.wait(), timeout=2)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request

        await asyncio.wait_for(polling_server.disconnected.wait(), timeout=1)
    finally:
        if not request.done():
            request.cancel()
        await asyncio.gather(request, return_exceptions=True)
