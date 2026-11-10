"""Outbound product telemetry must not carry free-form errors or username hashes."""

import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.telemetry.context import get_current_telemetry_user_id, telemetry_user_context
from langflow.services.telemetry.schema import (
    ComponentPayload,
    DeploymentPayload,
    EmailPayload,
    ExceptionPayload,
    PlaygroundPayload,
    RunPayload,
)
from langflow.services.telemetry.service import TelemetryService
from lfx.services.telemetry.identity import get_hashed_user_id, get_installation_user_id

ERROR_TEXT = "synthetic-private-input; SQL: UPDATE files SET name=?; parameters: synthetic@example.test"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "path", "safe_fields"),
    [
        (
            ExceptionPayload(
                exception_type="ValueError",
                exception_message=ERROR_TEXT,
                exception_context="handler",
                stack_trace_hash="abc123",
            ),
            "exception",
            {"exceptionType": "ValueError", "stackTraceHash": "abc123"},
        ),
        (
            RunPayload(run_seconds=2, run_success=False, run_error_message=ERROR_TEXT),
            "run",
            {"runSuccess": False, "runSeconds": 2},
        ),
        (
            ComponentPayload(
                component_name="Test",
                component_id="test",
                component_seconds=2,
                component_success=False,
                component_error_message=ERROR_TEXT,
            ),
            "component",
            {"componentSuccess": False, "componentSeconds": 2},
        ),
        (
            PlaygroundPayload(playground_seconds=2, playground_success=False, playground_error_message=ERROR_TEXT),
            "playground",
            {"playgroundSuccess": False},
        ),
        (
            DeploymentPayload(
                deployment_action="deployment.create",
                deployment_provider="test",
                deployment_seconds=2,
                deployment_success=False,
                deployment_error_message=ERROR_TEXT,
            ),
            "deployment",
            {"deploymentSuccess": False},
        ),
    ],
)
@pytest.mark.parametrize("identity_scheme", ["anonymous", "legacy", "current"])
async def test_outbound_errors_are_removed_without_mutating_local_payload(
    tmp_path, payload, path, safe_fields, identity_scheme
):
    settings = SimpleNamespace(
        settings=SimpleNamespace(
            config_dir=str(tmp_path),
            segment_api_url="https://segment.example.test/v1/track",
            segment_write_key="test-key",
            do_not_track=False,
            prometheus_enabled=False,
        )
    )
    service = TelemetryService(settings)
    requests = []

    def capture(request):
        requests.append(request)
        return httpx.Response(200)

    before = payload.model_dump()
    user_id = {
        "anonymous": None,
        "legacy": get_hashed_user_id("synthetic@example.test"),
        "current": get_installation_user_id(uuid4(), service.anonymous_id),
    }[identity_scheme]
    async with httpx.AsyncClient(transport=httpx.MockTransport(capture)) as client:
        service.client = client
        await service.send_telemetry_data(payload, path, user_id)

    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert ERROR_TEXT not in requests[0].content.decode()
    assert not any(key.endswith("ErrorMessage") or key == "exceptionMessage" for key in body["properties"])
    for key, value in safe_fields.items():
        assert body["properties"][key] == value
    assert body["properties"]["productTitle"] == "Langflow"
    assert body["userId"] == (user_id if identity_scheme == "current" else get_hashed_user_id(service.anonymous_id))
    after = payload.model_dump()
    before.pop("client_type")
    after.pop("client_type")
    assert after == before


@pytest.mark.asyncio
async def test_email_event_is_not_linked_to_installation_or_user(tmp_path):
    settings = SimpleNamespace(
        settings=SimpleNamespace(
            config_dir=str(tmp_path),
            segment_api_url="https://segment.example.test/v1/track",
            segment_write_key="test-key",
            do_not_track=False,
            prometheus_enabled=False,
        )
    )
    service = TelemetryService(settings)
    requests = []

    def capture(request):
        requests.append(request)
        return httpx.Response(200)

    user_id = get_installation_user_id(uuid4(), service.anonymous_id)
    async with httpx.AsyncClient(transport=httpx.MockTransport(capture)) as client:
        service.client = client
        await service.send_telemetry_data(EmailPayload(email="registered@example.com"), "email", user_id)
        await service.send_telemetry_data(EmailPayload(email="registered@example.com"), "email", user_id)

    bodies = [json.loads(request.content) for request in requests]
    assert len(bodies) == 2
    assert bodies[0]["anonymousId"] != bodies[1]["anonymousId"]
    for body in bodies:
        assert body["properties"]["email"] == "registered@example.com"
        assert body["userId"] == get_hashed_user_id(body["anonymousId"])
        assert body["userId"] != user_id
        assert body["anonymousId"] != service.anonymous_id
        assert body["properties"]["instanceId"] == body["anonymousId"]
        assert body["properties"]["subscriptionId"] == body["anonymousId"]
        UUID(body["anonymousId"])
    outbound = b"".join(request.content for request in requests).decode()
    assert service.anonymous_id not in outbound
    assert user_id not in outbound


def test_identity_uses_database_uuid_and_is_scoped_to_installation(monkeypatch):
    user = SimpleNamespace(id=uuid4(), username="synthetic@example.test")
    service = SimpleNamespace(anonymous_id=str(uuid4()))
    monkeypatch.setattr(auth_utils, "get_telemetry_service", lambda: service)
    with telemetry_user_context(None):
        auth_utils.set_authenticated_telemetry_user(user)
        first = get_current_telemetry_user_id()
        assert first is not None
        assert user.username not in first
        assert str(user.id) not in first
        assert first != get_hashed_user_id(user.username)
        assert first != get_hashed_user_id(f"{service.anonymous_id}:{get_hashed_user_id(user.username)}")
        user.username = "renamed@example.test"
        auth_utils.set_authenticated_telemetry_user(user)
        assert get_current_telemetry_user_id() == first
        user.id = uuid4()
        auth_utils.set_authenticated_telemetry_user(user)
        assert get_current_telemetry_user_id() != first
        second = get_current_telemetry_user_id()
        service.anonymous_id = str(uuid4())
        auth_utils.set_authenticated_telemetry_user(user)
        assert get_current_telemetry_user_id() != second


@pytest.mark.parametrize("user_id", [None, "not-a-uuid"])
def test_missing_or_invalid_database_identity_uses_installation_fallback(user_id):
    with telemetry_user_context(None):
        auth_utils.set_authenticated_telemetry_user(SimpleNamespace(id=user_id, username="synthetic@example.test"))
        assert get_current_telemetry_user_id() is None


def test_tracking_disabled_does_not_attribute_users(monkeypatch):
    monkeypatch.setattr(auth_utils, "get_telemetry_service", lambda: SimpleNamespace(anonymous_id=""))
    with telemetry_user_context(None):
        auth_utils.set_authenticated_telemetry_user(SimpleNamespace(id=uuid4(), username="synthetic@example.test"))
        assert get_current_telemetry_user_id() is None


def test_legacy_username_hash_is_not_restored_from_background_job():
    with telemetry_user_context(get_hashed_user_id("synthetic@example.test")):
        assert get_current_telemetry_user_id() is None
