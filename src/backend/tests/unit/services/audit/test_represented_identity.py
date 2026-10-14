"""Only the exact trusted credential may assert bounded audit-only identity."""

from __future__ import annotations

import base64
from uuid import uuid4

import pytest
from fastapi import HTTPException
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
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.deps import get_settings_service
from lfx.services.settings.groups.observability import ObservabilitySettings
from pydantic import ValidationError
from starlette.requests import Request


def encoded(value: str) -> str:
    return "v1." + base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


@pytest.mark.parametrize("value", ["auth0|Alice", "用户-Ålice", " CaseSensitive ", "s" * 512])
def test_identity_decoding_preserves_exact_unicode(value):
    assert decode_identity_value(encoded(value), 512) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "plain",
        "v2.YQ",
        "v1.YQ=",
        "v1.YR",
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


def test_represented_actor_populates_legacy_aliases_and_refuses_conflicts():
    fields = {"user_id": uuid4(), "actor_type": AuditActorType.API_KEY, "actor_id": uuid4()}
    actor = AuditActor(**fields, represented_issuer="issuer", represented_subject="subject")
    assert (actor.acting_issuer, actor.acting_subject) == ("issuer", "subject")
    with pytest.raises(AuditContractError):
        AuditActor(
            **fields,
            represented_issuer="issuer",
            represented_subject="subject",
            acting_issuer="other",
            acting_subject="subject",
        )
