"""``ResolvedCredential.identity`` is additive and mirrors ``IntegrationIdentity``."""

from __future__ import annotations

import dataclasses
from typing import get_args, get_type_hints

from lfx.integrations.capabilities import IntegrationIdentity
from lfx.integrations.models import ResolvedCredential
from pydantic import SecretStr


def test_identity_literal_mirrors_the_capability_identity_vocabulary() -> None:
    """The spelled-out literal cannot drift from lfx.integrations.capabilities."""
    hints = get_type_hints(ResolvedCredential)
    annotation = hints["identity"]
    # ``X | None`` -> the Literal is the first argument.
    literal = get_args(annotation)[0]
    assert set(get_args(literal)) == set(get_args(IntegrationIdentity))


def test_identity_defaults_to_none_so_existing_resolvers_keep_working() -> None:
    credential = ResolvedCredential(access_token=SecretStr("token"), provider="slack", name="work")

    assert credential.identity is None
    field = next(f for f in dataclasses.fields(ResolvedCredential) if f.name == "identity")
    assert field.default is None


def test_identity_is_carried_and_shown_in_the_safe_repr() -> None:
    credential = ResolvedCredential(
        access_token=SecretStr("xoxb-not-a-real-token"),  # pragma: allowlist secret
        provider="slack",
        name="workspace",
        identity="bot",
    )

    rendered = repr(credential)
    assert credential.identity == "bot"
    assert "identity='bot'" in rendered
    assert "xoxb-not-a-real-token" not in rendered


def test_identity_accepts_every_capability_identity() -> None:
    for identity in get_args(IntegrationIdentity):
        credential = ResolvedCredential(access_token=SecretStr("token"), identity=identity)
        assert credential.identity == identity
