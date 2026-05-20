"""Docs chatbot proxy: logs each question to Postgres, streams response from Langflow.
Secrets (LANGFLOW_API_KEY, DATABASE_URL) live only in the environment where this runs.

Env:
  LANGFLOW_BASE_URL   e.g. https://your-langflow.com (or http://necrotic-mutox.space:7860)
  LANGFLOW_API_KEY    Langflow API key (Bearer)
  FLOW_ID             Flow ID or endpoint name
  DATABASE_URL        Postgres URL (e.g. postgresql://user:pass@host:25060/defaultdb?sslmode=require)
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

import httpx
from database import init_db, log_query
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Docs Chatbot Proxy", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

LANGFLOW_BASE_URL = (os.environ.get("LANGFLOW_BASE_URL") or "").rstrip("/")
LANGFLOW_API_KEY = os.environ.get("LANGFLOW_API_KEY") or ""
FLOW_ID = os.environ.get("FLOW_ID") or ""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    if not FLOW_ID:
        raise HTTPException(500, "FLOW_ID is not set")
    if not LANGFLOW_API_KEY:
        raise HTTPException(500, "LANGFLOW_API_KEY is not set")
    if not LANGFLOW_BASE_URL:
        raise HTTPException(500, "LANGFLOW_BASE_URL is not set")

    session_id = req.session_id or str(uuid.uuid4())

    body = {
        "input_request": {
            "input_value": req.message,
            "input_type": "chat",
            "output_type": "chat",
            "session_id": session_id,
        },
        "context": None,
    }

    async def stream() -> AsyncGenerator[bytes, None]:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    async with client.stream(
                        "POST",
                        f"{LANGFLOW_BASE_URL}/api/v1/run/{FLOW_ID}",
                        params={"stream": "true"},
                        json=body,
                        headers={"x-api-key": LANGFLOW_API_KEY, "Content-Type": "application/json"},
                    ) as resp:
                        if resp.status_code != 200:
                            err_body = (await resp.aread()).decode("utf-8", errors="replace")
                            # Send error as an event so frontend can show it (don't raise after response started)
                            yield (
                                json.dumps(
                                    {"event": "error", "data": {"error": f"Langflow {resp.status_code}: {err_body}"}}
                                )
                                + "\n\n"
                            ).encode("utf-8")
                            return
                        async for chunk in resp.aiter_bytes():
                            if chunk:
                                yield chunk
                except httpx.HTTPError as e:
                    yield (
                        json.dumps({"event": "error", "data": {"error": f"Langflow request failed: {e!s}"}}) + "\n\n"
                    ).encode("utf-8")
        finally:
            # Log after streaming so we don't add latency before the first token
            try:
                log_query(req.message, session_id=session_id, flow_id=FLOW_ID, metadata={"source": "docs-chatbot"})
            except Exception:
                pass

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
