"""Tests for the catch-all exception handler.

The handler must NOT echo unhandled exception messages back to the client —
those routinely embed filesystem paths, SQL fragments, internal hostnames,
and library versions, which are useful reconnaissance for an attacker.
HTTPException detail strings, on the other hand, are intentionally
caller-facing and should be preserved verbatim.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi import HTTPException
from langflow.main import default_exception_handler

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_LEAKY_PATH = "/var/lib/langflow/internal/flows.db"


@pytest.fixture(autouse=True)
def _silence_side_effects(monkeypatch):
    """Stub out the I/O the handler does so the unit test stays hermetic."""
    import langflow.main as main_module

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(main_module, "log_exception_to_telemetry", _noop)
    # Replace logger methods used by the handler.
    monkeypatch.setattr(main_module.logger, "aerror", _noop)


def _body(response) -> dict:
    return json.loads(bytes(response.body).decode())


@pytest.mark.asyncio
async def test_unhandled_exception_returns_generic_message_with_error_id():
    exc = RuntimeError(f"connection refused to {_LEAKY_PATH}")
    response = await default_exception_handler(None, exc)

    assert response.status_code == 500
    body = _body(response)
    assert body["message"] == "Internal server error"
    assert _HEX32.match(body["error_id"]), f"error_id should be a 32-char hex token, got {body['error_id']!r}"


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_leak_str_exc():
    """Regression guard: the previous handler returned ``str(exc)`` directly."""
    exc = RuntimeError(f"sqlalchemy: column users.foo missing at {_LEAKY_PATH}")
    response = await default_exception_handler(None, exc)

    body = _body(response)
    raw = json.dumps(body)
    # Neither the path, the SQL-ish fragment, nor the library hint may appear.
    assert _LEAKY_PATH not in raw
    assert "sqlalchemy" not in raw
    assert "column users.foo" not in raw


@pytest.mark.asyncio
async def test_each_call_produces_unique_error_id():
    exc = ValueError("boom")
    r1 = _body(await default_exception_handler(None, exc))
    r2 = _body(await default_exception_handler(None, exc))
    assert r1["error_id"] != r2["error_id"]


@pytest.mark.asyncio
async def test_http_exception_passes_detail_through_unchanged():
    exc = HTTPException(status_code=404, detail="Project not found")
    response = await default_exception_handler(None, exc)

    assert response.status_code == 404
    assert _body(response) == {"message": "Project not found"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 422])
async def test_http_exception_preserves_status_code(status_code):
    exc = HTTPException(status_code=status_code, detail="msg")
    response = await default_exception_handler(None, exc)
    assert response.status_code == status_code


@pytest.mark.asyncio
async def test_http_exception_with_dict_detail_is_stringified():
    """The legacy contract was ``str(exc.detail)``; preserve it for HTTPException."""
    exc = HTTPException(status_code=400, detail={"field": "bad"})
    response = await default_exception_handler(None, exc)
    body = _body(response)
    assert body["message"] == str({"field": "bad"})


@pytest.mark.asyncio
async def test_long_exception_chain_does_not_leak():
    """Chained exceptions can stash the original message in __context__."""
    try:
        try:
            msg = f"opening {_LEAKY_PATH}"
            raise FileNotFoundError(msg)
        except FileNotFoundError as inner:
            wrap_msg = "wrapper"
            raise RuntimeError(wrap_msg) from inner
    except RuntimeError as exc:
        response = await default_exception_handler(None, exc)

    raw = json.dumps(_body(response))
    assert _LEAKY_PATH not in raw
    assert "FileNotFoundError" not in raw
