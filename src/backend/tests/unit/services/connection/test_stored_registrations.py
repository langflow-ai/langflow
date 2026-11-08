"""Registrations saved in Settings > Connections reach the OAuth settings at startup."""

from __future__ import annotations

import json

import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.connection.oauth import stored_registrations
from langflow.services.connection.oauth.config import OAuthSettings
from langflow.services.connection.oauth.stored_registrations import (
    ENVIRONMENT_COPY_ENV,
    REGISTRATIONS_ENV,
    STORED_REGISTRATION_PREFIX,
    delete_registration,
    load_stored_oauth_registrations,
    read_saved_registrations,
    registration_status,
    removed_since_startup,
    save_registration,
)
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope
from langflow.services.variable.constants import CREDENTIAL_TYPE
from lfx.utils.env_var_security import safe_getenv
from sqlmodel import select


@pytest.fixture(autouse=True)
def _isolated_registrations(monkeypatch):
    # Saving applies registrations to this process's environment; undo that after each test.
    for name in (REGISTRATIONS_ENV, ENVIRONMENT_COPY_ENV):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.setattr(stored_registrations, "_STARTED_WITH", {})


def _environment(monkeypatch, value: str) -> None:
    """Set the server environment as a new process sees it, before any merge."""
    monkeypatch.setenv(REGISTRATIONS_ENV, value)
    monkeypatch.delenv(ENVIRONMENT_COPY_ENV, raising=False)


def _registration(client_id: str) -> dict:
    return {
        "provider": "google",
        "profile": "user",
        "owner": "customer",
        "context": "self_managed",
        "client_type": "confidential",
        "client_id": client_id,
        "client_secret": "secret",
        "redirect_uri": "http://localhost:7860/api/v1/connections/oauth/google/callback",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }


async def _save(user_id, registration_id: str, value: dict) -> None:
    async with session_scope() as session:
        session.add(
            Variable(
                name=f"{STORED_REGISTRATION_PREFIX}{registration_id}",
                value=auth_utils.encrypt_api_key(json.dumps(value)),
                type=CREDENTIAL_TYPE,
                default_fields=[],
                user_id=user_id,
            )
        )


async def test_superuser_registration_is_added_and_environment_wins(active_super_user, monkeypatch):
    _environment(monkeypatch, json.dumps({"google-env": _registration("from-env")}))
    await _save(active_super_user.id, "google-ui", _registration("from-ui"))
    await _save(active_super_user.id, "google-env", _registration("ui-must-not-win"))

    await load_stored_oauth_registrations()

    configured = json.loads(OAuthSettings().registrations.get_secret_value())
    assert configured["google-ui"]["client_id"] == "from-ui"
    assert configured["google-env"]["client_id"] == "from-env"
    assert OAuthSettings().registration_ids() == ["google-env", "google-ui"]


def test_environment_copy_cannot_be_read_by_flow_environment_fallback(monkeypatch):
    _environment(monkeypatch, json.dumps({"google-env": _registration("from-env")}))

    stored_registrations.apply_saved_registrations({})

    assert safe_getenv(ENVIRONMENT_COPY_ENV) is None


async def test_regular_user_variable_is_ignored(active_user, monkeypatch):
    _environment(monkeypatch, "{}")
    await _save(active_user.id, "google-user", _registration("not-an-admin"))

    await load_stored_oauth_registrations()

    assert OAuthSettings().registration_ids() == []


@pytest.mark.parametrize(
    "name",
    [
        "langflow_oauth_registration__google-ui",
        "LANGFLOWxOAUTHxREGISTRATIONxxgoogle-ui",
        f"{STORED_REGISTRATION_PREFIX}INVALID",
        STORED_REGISTRATION_PREFIX,
        f"{STORED_REGISTRATION_PREFIX}{'a' * 121}",
    ],
)
async def test_only_exact_valid_registration_variable_names_are_loaded(active_super_user, monkeypatch, name):
    _environment(monkeypatch, "{}")
    async with session_scope() as session:
        session.add(
            Variable(
                name=name,
                value=auth_utils.encrypt_api_key(json.dumps(_registration("not-a-registration"))),
                type=CREDENTIAL_TYPE,
                default_fields=[],
                user_id=active_super_user.id,
            )
        )

    await load_stored_oauth_registrations()

    assert OAuthSettings().registration_ids() == []


async def test_invalid_environment_leaves_it_untouched(active_super_user, monkeypatch):
    _environment(monkeypatch, "not json")
    await _save(active_super_user.id, "google-ui", _registration("from-ui"))

    await load_stored_oauth_registrations()

    assert OAuthSettings().registrations.get_secret_value() == "not json"


async def test_status_says_what_waits_for_a_restart(active_super_user, monkeypatch):
    _environment(monkeypatch, json.dumps({"google-env": _registration("from-env")}))
    await _save(active_super_user.id, "google-ui", _registration("from-ui"))
    await _save(active_super_user.id, "google-env", _registration("ui-must-not-win"))
    await load_stored_oauth_registrations()

    async with session_scope() as session:
        saved = await read_saved_registrations(session)
    assert registration_status("google-ui", saved["google-ui"]) == "active"
    assert registration_status("google-env", saved["google-env"]) == "overridden"
    assert removed_since_startup(saved) == {}

    # Processes that started with the old set keep it until they restart.
    async with session_scope() as session:
        await save_registration(
            session, user_id=active_super_user.id, registration_id="google-new", registration=_registration("new")
        )
        await save_registration(
            session, user_id=active_super_user.id, registration_id="google-env", registration=_registration("other")
        )
        await delete_registration(session, "google-ui")
        saved = await read_saved_registrations(session)
    assert registration_status("google-new", saved["google-new"]) == "pending"
    assert registration_status("google-env", saved["google-env"]) == "overridden"
    assert list(removed_since_startup(saved)) == ["google-ui"]


SAVED_URL = "api/v1/connections/oauth/registrations/saved"


async def test_superuser_saves_lists_and_removes_without_exposing_secrets(client, logged_in_headers_super_user):
    response = await client.put(
        f"{SAVED_URL}/google-ui", json={"registration": _registration("from-ui")}, headers=logged_in_headers_super_user
    )
    assert response.status_code == 204

    listed = (await client.get(SAVED_URL, headers=logged_in_headers_super_user)).json()["registrations"]
    assert [entry["id"] for entry in listed] == ["google-ui"]
    assert listed[0]["registration"]["client_id"] == "from-ui"
    assert "client_secret" not in listed[0]["registration"]
    assert listed[0]["has_secret"] is True
    assert listed[0]["saved_by"] == "activeuser"
    # In use here at once; processes started before the save wait for a restart.
    assert listed[0]["status"] == "pending"
    assert OAuthSettings().registration_ids() == ["google-ui"]

    async def statuses():
        listed = (await client.get(SAVED_URL, headers=logged_in_headers_super_user)).json()["registrations"]
        return [(entry["id"], entry["status"]) for entry in listed]

    await load_stored_oauth_registrations()  # A restart.
    assert await statuses() == [("google-ui", "active")]

    response = await client.delete(f"{SAVED_URL}/google-ui", headers=logged_in_headers_super_user)
    assert response.status_code == 204
    # Gone here at once, and listed until a restart because processes started with it still use it.
    assert OAuthSettings().registration_ids() == []
    assert await statuses() == [("google-ui", "removed")]

    await load_stored_oauth_registrations()
    assert await statuses() == []


async def test_another_superuser_replaces_the_registration_and_keeps_its_secret(active_super_user):
    async with session_scope() as session:
        other = User(username="second-admin", password="unused", is_active=True, is_superuser=True)  # noqa: S106
        session.add(other)
        await session.flush()
        await save_registration(
            session, user_id=active_super_user.id, registration_id="google-ui", registration=_registration("first")
        )
        update = {key: value for key, value in _registration("second").items() if key != "client_secret"}
        await save_registration(session, user_id=other.id, registration_id="google-ui", registration=update)

        saved = await read_saved_registrations(session)
        name = f"{STORED_REGISTRATION_PREFIX}google-ui"
        rows = (await session.exec(select(Variable).where(Variable.name == name))).all()
        await session.delete(other)

    assert saved["google-ui"].value["client_id"] == "second"
    assert saved["google-ui"].value["client_secret"] == _registration("first")["client_secret"]
    assert saved["google-ui"].saved_by == "second-admin"
    assert len(rows) == 1


async def test_invalid_registration_is_refused_with_the_validation_message(client, logged_in_headers_super_user):
    response = await client.put(
        f"{SAVED_URL}/google-ui",
        json={"registration": {**_registration("x"), "redirect_uri": "ftp://example.com/callback"}},
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == 422
    assert "redirect" in response.json()["detail"].lower()


async def test_regular_user_cannot_use_the_saved_registration_routes(client, logged_in_headers):
    assert (await client.get(SAVED_URL, headers=logged_in_headers)).status_code == 403
    response = await client.put(
        f"{SAVED_URL}/google-ui", json={"registration": _registration("x")}, headers=logged_in_headers
    )
    assert response.status_code == 403
    assert (await client.delete(f"{SAVED_URL}/google-ui", headers=logged_in_headers)).status_code == 403


@pytest.mark.parametrize("rotated_field", ["client_secret", "signing_secret"])
async def test_rotating_one_slack_secret_preserves_the_other(active_super_user, rotated_field):
    registration = {
        **_registration("slack-app"),
        "provider": "slack",
        "profile": "bot",
        "redirect_uri": "http://localhost:7860/api/v1/connections/oauth/slack/callback",
        "scopes": ["chat:write"],
        "signing_secret": "signing-secret",
    }
    update = {key: value for key, value in registration.items() if key not in stored_registrations.SECRET_FIELDS}
    update[rotated_field] = "rotated-secret"

    async with session_scope() as session:
        await save_registration(
            session, user_id=active_super_user.id, registration_id="slack-ui", registration=registration
        )
        await save_registration(session, user_id=active_super_user.id, registration_id="slack-ui", registration=update)
        saved = await read_saved_registrations(session)

    for field in ("client_secret", "signing_secret"):
        assert saved["slack-ui"].value[field] == ("rotated-secret" if field == rotated_field else registration[field])


async def test_explicit_null_removes_a_saved_signing_secret(active_super_user):
    registration = {
        **_registration("slack-app"),
        "provider": "slack",
        "profile": "bot",
        "redirect_uri": "http://localhost:7860/api/v1/connections/oauth/slack/callback",
        "scopes": ["chat:write"],
        "signing_secret": "signing-secret",
    }
    update = {key: value for key, value in registration.items() if key not in stored_registrations.SECRET_FIELDS}
    update["signing_secret"] = None

    async with session_scope() as session:
        await save_registration(
            session, user_id=active_super_user.id, registration_id="slack-ui", registration=registration
        )
        await save_registration(session, user_id=active_super_user.id, registration_id="slack-ui", registration=update)
        saved = await read_saved_registrations(session)

    assert saved["slack-ui"].value["signing_secret"] is None
    assert saved["slack-ui"].value["client_secret"] == registration["client_secret"]


@pytest.mark.parametrize(
    ("original_field", "new_field"), [("client_secret", "private_key"), ("private_key", "client_secret")]
)
async def test_switching_microsoft_authentication_does_not_keep_the_old_secret(
    active_super_user, original_field, new_field
):
    registration = {
        **_registration("microsoft-app"),
        "provider": "microsoft",
        "redirect_uri": "http://localhost:7860/api/v1/connections/oauth/microsoft/callback",
        "tenant": "00000000-0000-0000-0000-000000000000",
        "certificate_thumbprint": "a" * 64,
        "scopes": ["offline_access"],
    }
    registration.pop("client_secret")
    registration[original_field] = "original-secret"
    update = {key: value for key, value in registration.items() if key not in stored_registrations.SECRET_FIELDS}
    update[new_field] = "replacement-secret"

    async with session_scope() as session:
        await save_registration(
            session, user_id=active_super_user.id, registration_id="microsoft-ui", registration=registration
        )
        await save_registration(
            session, user_id=active_super_user.id, registration_id="microsoft-ui", registration=update
        )
        saved = await read_saved_registrations(session)

    assert saved["microsoft-ui"].value[new_field] == "replacement-secret"
    assert original_field not in saved["microsoft-ui"].value
