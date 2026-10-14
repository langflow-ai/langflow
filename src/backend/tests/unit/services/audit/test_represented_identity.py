"""Only the exact trusted credential may assert bounded audit-only identity."""

from __future__ import annotations

import base64
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.audit_reads import AuditActorRead
from langflow.api.v1.audits import AuditFeedActor
from langflow.services.audit import represented as represented_module
from langflow.services.audit.attribution import AuditActor
from langflow.services.audit.details import AuditContractError
from langflow.services.audit.represented import (
    ISSUER_HEADER,
    SUBJECT_HEADER,
    bind_represented_identity,
    current_represented_identity,
    decode_identity_value,
)
from langflow.services.audit.vocabulary import AuditActorType
from langflow.services.audit.writer import stage_audit_event
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.deps import get_settings_service
from lfx.services.settings.groups.observability import ObservabilitySettings
from pydantic import ValidationError
from starlette.requests import Request

from .conftest import project_patch_draft


def encoded(value: str) -> str:
    return "v1." + base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


@pytest.mark.parametrize("value", ["auth0|Alice", "用户-Ålice", " CaseSensitive ", "s" * 512])
def test_identity_decoding_preserves_exact_unicode(value):
    assert decode_identity_value(encoded(value), 512) == value


@pytest.mark.parametrize("character_limit", [512, 2048])
def test_largest_utf8_values_fit_the_wire_limit(character_limit):
    # Each owl uses four UTF-8 bytes: this exercises the largest wire value
    # allowed by each real field's character limit.
    value = "🦉" * character_limit
    assert decode_identity_value(encoded(value), character_limit) == value


@pytest.mark.parametrize("character_limit", [512, 2048])
def test_oversized_wire_values_are_rejected_before_decoding(monkeypatch, character_limit):
    wire_value = encoded("🦉" * 2049)

    def unexpected_decode(*_args, **_kwargs):
        message = "Oversized headers must not reach the decoder"
        raise AssertionError(message)

    monkeypatch.setattr(represented_module.base64, "b64decode", unexpected_decode)
    with pytest.raises(HTTPException) as raised:
        decode_identity_value(wire_value, character_limit)
    assert raised.value.status_code == 400


@pytest.mark.parametrize(
    "value",
    [
        "",
        "plain",
        "v2.YQ",
        "v1.YQ=",
        "v1.***",
        "v1._w",
        encoded(" "),
        encoded("a\nb"),
        encoded("a\x7fb"),
        encoded("a\u2028b"),
        encoded("s" * 513),
    ],
)
def test_malformed_context_is_rejected_without_echoing_values(value):
    with pytest.raises(HTTPException) as raised:
        decode_identity_value(value, 512)
    assert raised.value.status_code == 400
    assert raised.value.detail == "Invalid represented audit identity"


def test_equivalent_base64_spellings_have_the_same_identity():
    assert decode_identity_value("v1.YQ", 512) == decode_identity_value("v1.YR", 512) == "a"


@pytest.mark.parametrize("method", ["api_key", "jwt", "auto_login", "external"])
def test_only_a_database_api_key_on_the_exact_allowlist_is_trusted(monkeypatch, method):
    trusted, other = uuid4(), uuid4()
    monkeypatch.setattr(get_settings_service().settings, "audit_trusted_api_key_ids", [trusted])
    request = Request(
        {
            "type": "http",
            "headers": [
                (ISSUER_HEADER.lower().encode(), encoded("issuer").encode()),
                (SUBJECT_HEADER.lower().encode(), encoded("subject").encode()),
            ],
        }
    )
    for key_id in (None, other, trusted):
        set_current_auth_context(AuthCredentialContext(method=method, api_key_id=key_id))
        try:
            if method == "api_key" and key_id == trusted:
                bind_represented_identity(request)
                assert current_represented_identity.get().subject == "subject"
            else:
                with pytest.raises(HTTPException) as raised:
                    bind_represented_identity(request)
                assert raised.value.status_code == 403
                assert current_represented_identity.get() is None
        finally:
            clear_current_auth_context()
            current_represented_identity.set(None)


def test_allowlist_configuration_validates_and_deduplicates_record_ids():
    first, second = uuid4(), uuid4()
    settings = ObservabilitySettings(audit_trusted_api_key_ids=f"{first}, {second},{first}")
    assert settings.audit_trusted_api_key_ids == [first, second]
    with pytest.raises(ValidationError):
        ObservabilitySettings(audit_trusted_api_key_ids="not-a-key-record-uuid")


def test_acting_and_represented_identity_are_independent():
    fields = {"user_id": uuid4(), "actor_type": AuditActorType.API_KEY, "actor_id": uuid4()}
    actor = AuditActor(**fields, represented_issuer="issuer", represented_subject="subject")
    assert (actor.acting_issuer, actor.acting_subject) == (None, None)
    actor = AuditActor(**fields, acting_issuer="actor-issuer", acting_subject="actor-subject")
    assert (actor.represented_issuer, actor.represented_subject) == (None, None)
    actor = AuditActor(
        **fields,
        acting_issuer="actor-issuer",
        acting_subject="actor-subject",
        represented_issuer="other-issuer",
        represented_subject="other-subject",
    )
    assert (actor.acting_issuer, actor.acting_subject) == ("actor-issuer", "actor-subject")
    assert (actor.represented_issuer, actor.represented_subject) == ("other-issuer", "other-subject")


@pytest.mark.parametrize("prefix", ["acting", "represented"])
def test_each_identity_pair_is_validated_independently(prefix):
    fields = {"user_id": uuid4(), "actor_type": AuditActorType.API_KEY, "actor_id": uuid4()}
    with pytest.raises(AuditContractError):
        AuditActor(**fields, **{f"{prefix}_subject": "subject"})
    with pytest.raises(AuditContractError):
        AuditActor(**fields, **{f"{prefix}_issuer": "issuer", f"{prefix}_subject": "s" * 513})


async def test_writer_persists_distinct_identity_pairs(audit_session, audit_enabled):  # noqa: ARG001
    actor = AuditActor(
        user_id=uuid4(),
        actor_type=AuditActorType.USER,
        actor_id=uuid4(),
        acting_issuer="actor-issuer",
        acting_subject="actor",
        represented_issuer="end-user-issuer",
        represented_subject="end-user",
    )
    event = await stage_audit_event(audit_session, project_patch_draft(actor=actor))
    await audit_session.commit()
    await audit_session.refresh(event)
    assert (event.acting_issuer, event.acting_subject) == ("actor-issuer", "actor")
    assert (event.represented_issuer, event.represented_subject) == ("end-user-issuer", "end-user")


@pytest.mark.parametrize("schema", [AuditActorRead, AuditFeedActor])
def test_acting_identity_remains_a_supported_api_field(schema):
    properties = schema.model_json_schema()["properties"]
    for name in ("acting_issuer", "acting_subject"):
        assert name in properties
        assert not properties[name].get("deprecated", False)
