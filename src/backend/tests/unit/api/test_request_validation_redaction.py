"""A 422 names the field that failed; it never echoes the value submitted for it.

FastAPI's default handler returns every pydantic error with ``input`` -- the raw
value that failed -- and a ``ctx`` that can quote it. QA (LE-2462, O1) showed a
422 reflecting token material from POST /api/v1/connections and Credential
values from POST /api/v1/variables/. The caller gains nothing it did not send,
but 422 bodies land in proxy logs, browser devtools and error trackers.

The same values reached the server log: FastAPI opens the session dependency
before it validates the body, then throws the validation error into it, and
session_scope logged whatever was thrown.
"""

import io
import logging
from typing import Annotated, Literal

import pytest
from fastapi import FastAPI, Header, Query, WebSocket, status
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from langflow.api.utils.core import DbSession
from langflow.api.validation_errors import redact_validation_errors, request_validation_exception_handler
from langflow.services.variable.constants import CREDENTIAL_TYPE
from lfx.services.deps import session_scope
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictStr, ValidationError, field_validator
from structlog import PrintLogger, make_filtering_bound_logger, wrap_logger
from structlog.dev import ConsoleRenderer, plain_traceback

CANARY = "lf-canary-9d1f4e7a2c8b"  # pragma: allowlist secret
NUMERIC_CANARY = 5550123987
SENTINEL = "session-scope-control-5c1e"


def _assert_redacted(response, canary: object, *, loc: list, error_type: str) -> None:
    """The body keeps loc/msg/type for every error and quotes the canary nowhere."""
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert str(canary) not in response.text
    detail = response.json()["detail"]
    assert detail, "a 422 must still say what failed"
    for error in detail:
        assert {"loc", "msg", "type"} <= error.keys()
        assert "input" not in error
    assert any(error["loc"] == loc and error["type"] == error_type for error in detail), detail


# Mirrors ConnectionCreate / ConnectionCredentialWrite from the INT-4 connection
# API (#14921, fix/int-4-connection-api), which is not on this branch yet. Same
# config (extra="forbid") and the same credential field types, so the three QA
# shapes produce the errors they produce on the real route.
class _ConnectionCredentialWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: SecretStr = Field(min_length=1)
    refresh_token: SecretStr | None = None
    token_type: StrictStr = Field(default="Bearer", min_length=1, max_length=32)


class _ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_key: StrictStr = Field(max_length=120)
    name: StrictStr = Field(max_length=64)
    display_name: StrictStr = Field(min_length=1, max_length=255)
    credentials: _ConnectionCredentialWrite | None = None


_VALID_CONNECTION = {"provider_key": "google", "name": "work-gmail", "display_name": "Work Gmail"}


@pytest.fixture
async def connection_client():
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

    @app.post("/api/v1/connections")
    async def create_connection(connection: _ConnectionCreate) -> dict:
        return {"provider_key": connection.provider_key}

    @app.get("/api/v1/connections")
    async def list_connections(
        limit: Annotated[int, Query()] = 50,
        x_api_key: Annotated[str | None, Header(max_length=64)] = None,
    ) -> list:
        return [limit, x_api_key]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


@pytest.mark.parametrize(
    ("body", "canary", "loc", "error_type"),
    [
        pytest.param(
            {**_VALID_CONNECTION, "credentials": {"access_token": NUMERIC_CANARY}},
            NUMERIC_CANARY,
            ["body", "credentials", "access_token"],
            "string_type",
            id="wrong-type-access-token-number",
        ),
        pytest.param(
            {**_VALID_CONNECTION, "credentials": {"access_token": {"token": CANARY}}},
            CANARY,
            ["body", "credentials", "access_token"],
            "string_type",
            id="wrong-type-access-token-object",
        ),
        pytest.param(
            {**_VALID_CONNECTION, "credentials": {"access_token": "valid-token-value", "client_secret": CANARY}},
            CANARY,
            ["body", "credentials", "client_secret"],
            "extra_forbidden",
            id="unknown-key-inside-credentials",
        ),
        pytest.param(
            {**_VALID_CONNECTION, "api_key": CANARY},
            CANARY,
            ["body", "api_key"],
            "extra_forbidden",
            id="unknown-top-level-key",
        ),
        pytest.param(
            # A *valid* token is echoed too: a missing field's input is the whole body.
            {"credentials": {"access_token": CANARY}},
            CANARY,
            ["body", "provider_key"],
            "missing",
            id="valid-token-beside-missing-field",
        ),
    ],
)
async def test_connection_422_does_not_echo_credential_material(connection_client, body, canary, loc, error_type):
    response = await connection_client.post("/api/v1/connections", json=body)

    _assert_redacted(response, canary, loc=loc, error_type=error_type)


@pytest.mark.parametrize(
    ("params", "headers", "loc", "error_type"),
    [
        pytest.param({"limit": CANARY}, {}, ["query", "limit"], "int_parsing", id="query-param"),
        pytest.param({}, {"x-api-key": CANARY * 4}, ["header", "x-api-key"], "string_too_long", id="header"),
    ],
)
async def test_parameter_422_does_not_echo_the_value(connection_client, params, headers, loc, error_type):
    response = await connection_client.get("/api/v1/connections", params=params, headers=headers)

    _assert_redacted(response, CANARY, loc=loc, error_type=error_type)


async def test_malformed_json_body_is_still_a_422(connection_client):
    # FastAPI builds this entry itself: an int position in loc and a str in ctx["error"].
    truncated = f'{{"credentials": {{"access_token": "{CANARY}"'.encode()

    response = await connection_client.post(
        "/api/v1/connections", content=truncated, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert CANARY not in response.text
    [error] = response.json()["detail"]
    assert error == {"type": "json_invalid", "loc": ["body", len(truncated)], "msg": "JSON decode error"}


async def test_connection_422_keeps_schema_constraints_in_ctx(connection_client):
    response = await connection_client.post("/api/v1/connections", json={**_VALID_CONNECTION, "display_name": ""})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {
        "detail": [
            {
                "type": "string_too_short",
                "loc": ["body", "display_name"],
                "msg": "String should have at least 1 character",
                "ctx": {"min_length": 1},
            }
        ]
    }


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize(
    ("body", "loc", "error_type"),
    [
        pytest.param(
            {"value": CANARY, "type": CREDENTIAL_TYPE, "default_fields": []},
            ["body", "name"],
            "missing",
            id="credential-value-beside-missing-name",
        ),
        pytest.param(
            {"name": "OPENAI_API_KEY", "value": {"secret": CANARY}, "type": CREDENTIAL_TYPE, "default_fields": []},
            ["body", "value"],
            "string_type",
            id="credential-in-wrong-typed-value",
        ),
    ],
)
async def test_variables_422_does_not_echo_credential_value(
    client: AsyncClient, logged_in_headers, body, loc, error_type
):
    """Goes through create_app(), so it also proves the handler is registered on the real app."""
    response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)

    _assert_redacted(response, CANARY, loc=loc, error_type=error_type)


@pytest.fixture
def session_scope_log(monkeypatch) -> io.StringIO:
    """Everything session_scope logs at ERROR, rendered with the traceback.

    The module's own logger is a lazy structlog proxy that freezes its level and
    sink on first use, so what capsys or caplog see depends on which test ran
    first. A real logger with its own sink reads the same in every worker.
    """
    sink = io.StringIO()
    error_logger = wrap_logger(
        PrintLogger(file=sink),
        processors=[ConsoleRenderer(colors=False, exception_formatter=plain_traceback)],
        wrapper_class=make_filtering_bound_logger(logging.ERROR),
    )
    monkeypatch.setattr("lfx.services.deps.logger", error_logger)
    return sink


async def _assert_session_scope_errors_are_captured(log: io.StringIO) -> None:
    """Positive control: without it, "the canary is not in the log" passes on a sink nothing writes to."""
    with pytest.raises(RuntimeError, match=SENTINEL):
        async with session_scope():
            raise RuntimeError(SENTINEL)
    assert "An error occurred during the session scope." in log.getvalue()
    assert SENTINEL in log.getvalue()


async def test_failed_body_validation_is_not_logged_by_the_session_scope(client: AsyncClient, session_scope_log):
    await _assert_session_scope_errors_are_captured(session_scope_log)

    # A sign-up with a mistyped username field: a missing field's input is the whole body.
    response = await client.post("api/v1/users/", json={"password": CANARY})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response.text
    assert CANARY not in session_scope_log.getvalue()


@pytest.mark.usefixtures("client")
async def test_failed_websocket_validation_is_not_logged_by_the_session_scope(session_scope_log):
    await _assert_session_scope_errors_are_captured(session_scope_log)
    app = FastAPI()

    @app.websocket("/ws")
    async def probe(websocket: WebSocket, limit: int, session: DbSession):  # noqa: ARG001
        await websocket.accept()

    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "websocket.connect"}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "scheme": "ws",
        "path": "/ws",
        "raw_path": b"/ws",
        "query_string": f"limit={CANARY}".encode(),
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
        "subprotocols": [],
    }
    await app(scope, receive, send)

    assert [message["type"] for message in sent] == ["websocket.close"], sent
    assert CANARY not in session_scope_log.getvalue()


def _errors_for(model: type[BaseModel], data: dict) -> list[dict]:
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(data)
    return exc_info.value.errors()


class _TokenInterpolatingModel(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def _reject(cls, value: str) -> str:
        msg = f"token {value} is not recognised"
        raise ValueError(msg)


class _Cat(BaseModel):
    kind: Literal["cat"]


class _Dog(BaseModel):
    kind: Literal["dog"]


class _Pet(BaseModel):
    pet: Annotated[_Cat | _Dog, Field(discriminator="kind")]


def test_validator_message_that_quotes_the_value_is_scrubbed():
    [error] = redact_validation_errors(_errors_for(_TokenInterpolatingModel, {"token": CANARY}))

    assert error == {
        "type": "value_error",
        "loc": ("token",),
        "msg": "Value error, token [redacted] is not recognised",
    }


def test_short_submitted_values_stay_in_the_message():
    # Redacting a two-letter value would shred the validator's own wording; see MIN_REDACTED_LENGTH.
    [error] = redact_validation_errors(_errors_for(_TokenInterpolatingModel, {"token": "id"}))

    assert error["msg"] == "Value error, token id is not recognised"


def test_input_derived_ctx_is_dropped_and_schema_ctx_kept():
    [error] = redact_validation_errors(_errors_for(_Pet, {"pet": {"kind": CANARY}}))

    assert error["type"] == "union_tag_invalid"
    assert error["ctx"] == {"discriminator": "'kind'", "expected_tags": "'cat', 'dog'"}
    assert CANARY not in str(error)


def test_fixed_template_message_is_left_alone():
    # A missing field's input is the whole body, and "required" is both one of its
    # values and a substring of pydantic's wording. A fixed-template message cannot
    # quote input, so it comes back exactly as pydantic wrote it.
    errors = _errors_for(_ConnectionCreate, {"provider_key": "required", "display_name": "Work Gmail"})

    [error] = redact_validation_errors(errors)

    assert error == {"type": "missing", "loc": ("name",), "msg": "Field required"}


def test_unknown_ctx_key_on_builtin_error_is_dropped():
    errors = [
        {
            "type": "string_too_long",
            "loc": ("body", "token"),
            "msg": f"String should have at most 8 characters, got {CANARY}",
            "input": CANARY,
            "ctx": {"max_length": 8, "submitted": CANARY},
        }
    ]

    [error] = redact_validation_errors(errors)

    assert error == {
        "type": "string_too_long",
        "loc": ("body", "token"),
        "msg": "String should have at most 8 characters, got [redacted]",
        "ctx": {"max_length": 8},
    }


def test_custom_error_type_keeps_no_ctx():
    # Nothing says which keys of a custom error's ctx were filled from input.
    errors = [
        {
            "type": "custom_token_error",
            "loc": ("body", "token"),
            "msg": f"custom check rejected {CANARY}",
            "input": CANARY,
            "ctx": {"expected": CANARY, "max_length": 8},
        }
    ]

    [error] = redact_validation_errors(errors)

    assert error == {"type": "custom_token_error", "loc": ("body", "token"), "msg": "custom check rejected [redacted]"}


def test_malformed_entry_is_redacted_not_crashed():
    # A plugin can raise RequestValidationError by hand; a crash here would turn
    # the 422 into a 500 whose body is str(exc).
    [error] = redact_validation_errors([{"msg": f"bad {CANARY}", "input": [CANARY], "ctx": ["not", "a", "mapping"]}])

    assert error == {"type": None, "loc": (), "msg": "bad [redacted]"}


def test_redaction_does_not_mutate_the_original_errors():
    errors = _errors_for(_TokenInterpolatingModel, {"token": CANARY})
    snapshot = [dict(error) for error in errors]

    redact_validation_errors(errors)

    assert errors == snapshot
