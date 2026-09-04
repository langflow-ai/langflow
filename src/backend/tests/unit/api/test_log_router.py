from collections.abc import Callable

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from langflow.api.log_router import log_router
from langflow.services.auth.utils import get_current_active_superuser, get_current_active_user
from lfx.log.logger import log_buffer


@pytest.fixture(autouse=True)
def buffered_logs():
    original_max = log_buffer.max
    original_buffer = list(log_buffer.buffer)
    log_buffer.max = 10
    with log_buffer.get_write_lock():
        log_buffer.buffer.clear()
        log_buffer.buffer.append((1234, "victim job_id leaked-from-debug-logs"))
    yield
    log_buffer.max = original_max
    with log_buffer.get_write_lock():
        log_buffer.buffer.clear()
        log_buffer.buffer.extend(original_buffer)


def _client_with_log_auth(
    *,
    active_user_dependency: Callable,
    superuser_dependency: Callable,
) -> TestClient:
    app = FastAPI()
    app.include_router(log_router)
    app.dependency_overrides[get_current_active_user] = active_user_dependency
    app.dependency_overrides[get_current_active_superuser] = superuser_dependency
    return TestClient(app)


def test_logs_reject_active_non_superuser() -> None:
    def allow_active_user():
        return object()

    def reject_superuser():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )

    client = _client_with_log_auth(
        active_user_dependency=allow_active_user,
        superuser_dependency=reject_superuser,
    )

    response = client.get("/logs?lines_before=1")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "leaked-from-debug-logs" not in response.text


def test_logs_allow_superuser() -> None:
    def reject_active_user():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="unexpected dependency")

    def allow_superuser():
        return object()

    client = _client_with_log_auth(
        active_user_dependency=reject_active_user,
        superuser_dependency=allow_superuser,
    )

    response = client.get("/logs?lines_before=1")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"1234": "victim job_id leaked-from-debug-logs"}


def test_logs_stream_rejects_active_non_superuser() -> None:
    def allow_active_user():
        return object()

    def reject_superuser():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )

    client = _client_with_log_auth(
        active_user_dependency=allow_active_user,
        superuser_dependency=reject_superuser,
    )

    response = client.get("/logs-stream")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "leaked-from-debug-logs" not in response.text


def test_logs_stream_allows_superuser() -> None:
    def reject_active_user():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="unexpected dependency")

    def allow_superuser():
        return object()

    client = _client_with_log_auth(
        active_user_dependency=reject_active_user,
        superuser_dependency=allow_superuser,
    )

    # /logs-stream returns an infinite SSE generator that TestClient cannot safely
    # consume, so we assert the superuser clears the auth gate (no 403) by reaching
    # the handler with the buffer disabled, which returns 501 before any streaming.
    log_buffer.max = 0  # enabled() is `max > 0`; the autouse fixture restores it
    response = client.get("/logs-stream")

    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert response.status_code != status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("path", ["/logs", "/logs-stream"])
def test_log_routes_require_superuser_dependency(path: str) -> None:
    route = next(route for route in log_router.routes if isinstance(route, APIRoute) and route.path == path)
    dependency_calls = [dependency.call for dependency in route.dependant.dependencies]

    assert get_current_active_superuser in dependency_calls
    assert get_current_active_user not in dependency_calls
