"""Controlled loopback inference/extraction service. Not a model/provider benchmark."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from aiohttp import web


@dataclass
class InferenceService:
    url: str = ""
    active: int = 0
    peak: int = 0
    requests: int = 0
    events: list = field(default_factory=list)

    async def infer(self, request: web.Request) -> web.Response:
        data = await request.json()
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.requests += 1
        self.events.append((data["id"], "http_start", time.perf_counter()))
        try:
            # Service latency is controlled to isolate scheduling, not a claim
            # about provider throughput or model quality.
            await asyncio.sleep(data["delay"])
            text = data["text"]
            text = " ".join(text.lower().split()) if data["operation"] == "extract" else f"{text}|{data['id']}"
            return web.json_response({"text": text})
        finally:
            self.active -= 1
            self.events.append((data["id"], "http_end", time.perf_counter()))


@asynccontextmanager
async def inference_service():
    state = InferenceService()
    app = web.Application()
    app.router.add_post("/infer", state.infer)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # noqa: SLF001 - ephemeral local fixture port
    state.url = f"http://127.0.0.1:{port}/infer"
    try:
        yield state
    finally:
        await runner.cleanup()
