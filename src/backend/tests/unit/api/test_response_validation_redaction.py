"""A 500 from a response-model mismatch never echoes the value that failed to serialize.

When a route returns something its ``response_model`` rejects, FastAPI raises
``ResponseValidationError``. It had no handler of its own, so it reached the
catch-all in ``create_app()``, which answers ``{"message": str(exc)}``. That
string lists every pydantic error with its ``input`` -- the server-side value
that failed, or for a missing field the whole object -- followed by the
endpoint's file, line and function. A mismatch on a route that handles secrets
put them in the 500 body, and from there into proxy logs, browser devtools and
error trackers. This is the server-side counterpart of LE-2462 O1.

The probe routes are added to the real app through ``create_app()``'s
plugin-route hook, so each request crosses the production middleware and
exception handlers.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI, status
from fastapi.exceptions import ResponseValidationError
from httpx import ASGITransport, AsyncClient
from langflow import main as langflow_main
from langflow.services.database.models.variable.model import VariableRead
from langflow.services.deps import get_telemetry_service
from langflow.services.telemetry.schema import ExceptionPayload
from langflow.services.variable.constants import CREDENTIAL_TYPE
from pydantic import BaseModel

CANARY = "lf-canary-5b7e2d9c41fa"  # pragma: allowlist secret
GENERIC_BODY = {"message": "Internal server error: the response failed validation"}

VARIABLE_PROBE = "/__probe__/variable-missing-id"
COUNT_PROBE = "/__probe__/count-not-int"
RUNTIME_ERROR_PROBE = "/__probe__/runtime-error"


class CountRead(BaseModel):
    count: int


async def variable_missing_id() -> dict[str, Any]:
    # VariableRead nulls a Credential's value once validation succeeds. A failure
    # hands pydantic the raw object instead, credential included, as the input of
    # the missing-field error.
    return {"name": "OPENAI_API_KEY", "type": CREDENTIAL_TYPE, "value": CANARY}


async def count_not_int() -> dict[str, Any]:
    return {"count": CANARY}


async def runtime_error() -> None:
    msg = "probe failure"
    raise RuntimeError(msg)


@pytest.fixture(autouse=True)
def probe_app(monkeypatch) -> dict[str, FastAPI]:
    """Register the probes while create_app() builds the app, and keep a handle on that app.

    Autouse, so the hook is patched before the ``client`` fixture calls create_app().
    """
    captured: dict[str, FastAPI] = {}
    load_plugin_routes = langflow_main.load_plugin_routes

    def load_plugin_routes_and_probes(app: FastAPI) -> None:
        load_plugin_routes(app)
        app.add_api_route(VARIABLE_PROBE, variable_missing_id, response_model=VariableRead)
        app.add_api_route(COUNT_PROBE, count_not_int, response_model=CountRead)
        app.add_api_route(RUNTIME_ERROR_PROBE, runtime_error)
        captured["app"] = app

    monkeypatch.setattr(langflow_main, "load_plugin_routes", load_plugin_routes_and_probes)
    return captured


@pytest.fixture
async def app_client(probe_app: dict[str, FastAPI], client: AsyncClient) -> AsyncIterator[AsyncClient]:  # noqa: ARG001
    """A client on the ``client`` fixture's app that returns a 500 instead of raising it.

    The ``client`` transport re-raises any exception that escapes the app, and the
    catch-all re-raises after answering, so only this client shows the body a caller
    receives from that path.
    """
    transport = ASGITransport(app=probe_app["app"], raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as raw_client:
        yield raw_client


@pytest.mark.parametrize("path", [VARIABLE_PROBE, COUNT_PROBE], ids=["missing-field", "wrong-type"])
async def test_response_validation_500_does_not_echo_the_failing_value(app_client: AsyncClient, path: str):
    response = await app_client.get(path)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert CANARY not in response.text
    # No pydantic errors, no input, and no endpoint file, line or function.
    assert response.json() == GENERIC_BODY


async def test_response_validation_is_handled_rather_than_escaping_the_app(app_client: AsyncClient, client):  # noqa: ARG001
    # The ``client`` transport raises whatever escapes the app. A handled error
    # comes back as a response, through the middleware stack like any other.
    response = await client.get(VARIABLE_PROBE)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == GENERIC_BODY


async def test_response_validation_logs_the_full_errors_server_side(app_client: AsyncClient, monkeypatch):
    real_logger = langflow_main.logger
    logged: list[tuple[str, dict[str, Any]]] = []

    class RecordingLogger:
        async def aerror(self, event: str, *args: Any, **kwargs: Any) -> None:
            logged.append((event, kwargs))
            await real_logger.aerror(event, *args, **kwargs)

        def __getattr__(self, name: str) -> Any:
            return getattr(real_logger, name)

    monkeypatch.setattr(langflow_main, "logger", RecordingLogger())

    await app_client.get(VARIABLE_PROBE)

    assert len(logged) == 1
    event, kwargs = logged[0]
    # The full error rides on exc_info, which the console and log file render and OTel
    # log export never carries. The message can be exported, so it holds no values.
    assert isinstance(kwargs["exc_info"], ResponseValidationError)
    assert CANARY in str(kwargs["exc_info"])
    assert CANARY not in event


async def test_response_validation_telemetry_names_locations_not_values(app_client: AsyncClient, monkeypatch):
    # Telemetry leaves the server (DO_NOT_TRACK only stops the send), so the event
    # carries the error types, their locations and the route, not str(exc).
    queued: list[Any] = []

    async def record(event: Any) -> None:
        queued.append(event)

    monkeypatch.setattr(get_telemetry_service(), "_queue_event", record)

    await app_client.get(VARIABLE_PROBE)

    payloads = [event[1] for event in queued if isinstance(event[1], ExceptionPayload)]
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload.exception_type == "ResponseValidationError"
    assert payload.exception_context == "handler"
    assert CANARY not in payload.exception_message
    assert "'missing'" in payload.exception_message
    assert "('response', 'id')" in payload.exception_message
    assert f"GET {VARIABLE_PROBE}" in payload.exception_message
    # The endpoint's source file is a server path; the probe is defined in this file.
    assert __file__ not in payload.exception_message


async def test_other_unhandled_errors_keep_their_500_shape(app_client: AsyncClient):
    # Scope check: only ResponseValidationError has a handler of its own.
    response = await app_client.get(RUNTIME_ERROR_PROBE)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"message": "probe failure"}
