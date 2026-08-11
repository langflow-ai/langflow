"""Tests for serving-plane end-user identity resolution and session scoping.

Covers the isolation contract: an identified request yields its distinct scope
key, an anonymous request yields no key and does not persist, and a spoofed
header is ignored unless trust is explicitly opted into.
"""

import pytest
from lfx.workflow.end_user_identity import (
    ANONYMOUS,
    ANONYMOUS_SESSION_PREFIX,
    EndUserIdentity,
    EndUserIdentityRequiredError,
    resolve_end_user_identity,
    scope_session_for_identity,
)

HEADER = "X-End-User-Id"
FLOW_ID = "flow-123"


def _headers(**pairs: str):
    """Return a case-insensitive ``get`` over a fixed header set."""
    lower = {k.lower(): v for k, v in pairs.items()}
    return lambda name: lower.get(name.lower())


def _resolve(headers, *, header_name=HEADER, trust=True, require=False):
    return resolve_end_user_identity(
        header_name=header_name,
        trust_proxy_headers=trust,
        require_identity=require,
        get_header=headers,
    )


# --- identified ----------------------------------------------------------------


def test_identified_request_scopes_to_header_value():
    identity = _resolve(_headers(**{HEADER: "user-abc"}))
    assert identity == EndUserIdentity(id="user-abc")
    assert not identity.is_anonymous


def test_two_users_get_distinct_identities():
    alice = _resolve(_headers(**{HEADER: "alice"}))
    bob = _resolve(_headers(**{HEADER: "bob"}))
    assert alice.id != bob.id


def test_header_value_is_trimmed():
    identity = _resolve(_headers(**{HEADER: "  user-abc  "}))
    assert identity.id == "user-abc"


def test_header_lookup_is_case_insensitive():
    identity = _resolve(_headers(**{"x-end-user-id": "user-abc"}))
    assert identity.id == "user-abc"


# --- anonymous -----------------------------------------------------------------


def test_missing_header_is_anonymous():
    identity = _resolve(_headers())
    assert identity is ANONYMOUS
    assert identity.is_anonymous


def test_empty_header_is_anonymous():
    assert _resolve(_headers(**{HEADER: ""})).is_anonymous


def test_whitespace_only_header_is_anonymous():
    assert _resolve(_headers(**{HEADER: "   "})).is_anonymous


def test_feature_off_is_anonymous_even_with_header_present():
    # Header name unset ⇒ feature off ⇒ fully anonymous, header ignored.
    identity = _resolve(_headers(**{HEADER: "user-abc"}), header_name=None)
    assert identity.is_anonymous


# --- spoofing / trust gate -----------------------------------------------------


def test_spoofed_header_ignored_when_trust_disabled():
    # A client-supplied header must not leak into scoping when trust is off.
    identity = _resolve(_headers(**{HEADER: "victim-user"}), trust=False)
    assert identity.is_anonymous
    assert identity.id != "victim-user"


def test_identified_and_anonymous_never_share_a_scope_key():
    identified = _resolve(_headers(**{HEADER: "alice"}))
    anon = _resolve(_headers())
    assert identified.id is not None
    assert anon.id is None


# --- required ------------------------------------------------------------------


def test_required_rejects_missing_identity():
    with pytest.raises(EndUserIdentityRequiredError):
        _resolve(_headers(), require=True)


def test_required_rejects_empty_identity():
    with pytest.raises(EndUserIdentityRequiredError):
        _resolve(_headers(**{HEADER: "  "}), require=True)


def test_required_allows_present_identity():
    identity = _resolve(_headers(**{HEADER: "user-abc"}), require=True)
    assert identity.id == "user-abc"


def test_required_with_trust_disabled_rejects_every_request():
    # required + no trust is a fail-closed misconfiguration: nothing can be
    # identified, so every request is rejected rather than silently allowed.
    with pytest.raises(EndUserIdentityRequiredError):
        _resolve(_headers(**{HEADER: "user-abc"}), trust=False, require=True)


def test_feature_off_ignores_required():
    # Feature disabled wins over require_identity — no rejection when off.
    identity = _resolve(_headers(), header_name=None, require=True)
    assert identity.is_anonymous


# --- session scoping -----------------------------------------------------------


def test_identified_merges_end_user_into_session():
    scoped = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id="chat-1", default_session_id=FLOW_ID
    )
    assert scoped.session_id == "alice::chat-1"
    assert scoped.persist is True


def test_identified_without_session_uses_flow_default():
    scoped = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id=None, default_session_id=FLOW_ID
    )
    assert scoped.session_id == f"alice::{FLOW_ID}"


def test_two_users_same_session_id_do_not_collide():
    alice = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id="shared", default_session_id=FLOW_ID
    )
    bob = scope_session_for_identity(
        EndUserIdentity(id="bob"), requested_session_id="shared", default_session_id=FLOW_ID
    )
    assert alice.session_id != bob.session_id


def test_two_users_both_omitting_session_do_not_collide():
    # Both fall back to the flow id; the end-user prefix still isolates them.
    alice = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id=None, default_session_id=FLOW_ID
    )
    bob = scope_session_for_identity(EndUserIdentity(id="bob"), requested_session_id=None, default_session_id=FLOW_ID)
    assert alice.session_id != bob.session_id


def test_one_user_can_run_parallel_sessions():
    a = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id="thread-a", default_session_id=FLOW_ID
    )
    b = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id="thread-b", default_session_id=FLOW_ID
    )
    assert a.session_id != b.session_id
    assert a.session_id.startswith("alice::")
    assert b.session_id.startswith("alice::")


def test_identified_merge_is_idempotent_on_echoed_key():
    # The router echoes the effective session id; a well-behaved client reuses it.
    # Re-scoping the echoed key must return the same key, not nest another prefix.
    first = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id="chat-1", default_session_id=FLOW_ID
    )
    second = scope_session_for_identity(
        EndUserIdentity(id="alice"), requested_session_id=first.session_id, default_session_id=FLOW_ID
    )
    assert first.session_id == "alice::chat-1"
    assert second.session_id == first.session_id


def test_identified_cannot_unwrap_another_users_prefix():
    # Only the caller's own authenticated prefix is stripped; bob sending alice's
    # merged key lands in bob's namespace, not alice's.
    scoped = scope_session_for_identity(
        EndUserIdentity(id="bob"), requested_session_id="alice::chat-1", default_session_id=FLOW_ID
    )
    assert scoped.session_id == "bob::alice::chat-1"


def test_anonymous_gets_reserved_namespace_and_does_not_persist():
    scoped = scope_session_for_identity(ANONYMOUS, requested_session_id="chat-1", default_session_id=FLOW_ID)
    assert scoped.persist is False
    assert scoped.session_id.startswith(ANONYMOUS_SESSION_PREFIX)
    # The client-supplied session id must not survive into the scope key: it is a
    # read-scope key, and honoring it would let an anonymous caller execute in an
    # identified user's session.
    assert "chat-1" not in scoped.session_id


def test_anonymous_cannot_target_an_identified_scope():
    scoped = scope_session_for_identity(ANONYMOUS, requested_session_id="alice::chat-1", default_session_id=FLOW_ID)
    assert scoped.session_id != "alice::chat-1"
    assert "alice::chat-1" not in scoped.session_id
    assert scoped.persist is False


def test_two_anonymous_requests_never_share_a_scope():
    a = scope_session_for_identity(ANONYMOUS, requested_session_id="shared", default_session_id=FLOW_ID)
    b = scope_session_for_identity(ANONYMOUS, requested_session_id="shared", default_session_id=FLOW_ID)
    assert a.session_id != b.session_id


def test_anonymous_without_session_still_gets_reserved_namespace():
    scoped = scope_session_for_identity(ANONYMOUS, requested_session_id=None, default_session_id=FLOW_ID)
    assert scoped.session_id.startswith(ANONYMOUS_SESSION_PREFIX)
    assert scoped.persist is False
