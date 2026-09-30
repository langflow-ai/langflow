"""Contract for the shared message-owner / effective-user-id resolvers.

Both the message write path (``Component._store_message``) and the read path
(``_safe_graph_user_id``) resolve the owner through ``resolve_message_owner_id`` so
the stored ``message.user_id`` and the retrieval predicate always agree. These tests
pin that shared resolution — the serving-plane precedence (end user over executing
user), the stable-uuid5 derivation for a non-UUID id, and the PlaceholderGraph
``"None"`` guard — with plain attribute holders (no Graph construction needed).
"""

from types import SimpleNamespace
from uuid import UUID, uuid4

from lfx.memory.flow_context import (
    derive_message_owner_uuid,
    resolve_effective_user_id,
    resolve_message_owner_id,
)


def _graph(*, user_id=None, end_user_id=None):
    return SimpleNamespace(user_id=user_id, end_user_id=end_user_id)


def test_message_owner_is_executing_user_when_no_end_user():
    # Editor plane / feature off: only the executing user id is present.
    sid = uuid4()
    assert resolve_message_owner_id(_graph(user_id=sid)) == sid
    assert resolve_effective_user_id(_graph(user_id=sid)) == sid


def test_message_owner_prefers_uuid_end_user():
    # Serving plane, identified: the (UUID-shaped) end-user id wins over the SID.
    sid, uid = uuid4(), uuid4()
    g = _graph(user_id=sid, end_user_id=str(uid))
    assert resolve_message_owner_id(g) == uid
    assert resolve_effective_user_id(g) == str(uid)


def test_non_uuid_end_user_is_derived_to_stable_uuid():
    # message.user_id is UUID-typed: a non-UUID end-user id is mapped to a STABLE uuid5
    # (not the SID) so per-user rows stay separated. The raw resolver still returns the
    # opaque string for non-DB uses (e.g. file namespaces).
    sid = uuid4()
    g = _graph(user_id=sid, end_user_id="alice")
    owner = resolve_message_owner_id(g)
    assert isinstance(owner, UUID)
    assert owner != sid  # the end user, not the service account
    assert owner == derive_message_owner_uuid("alice")  # deterministic
    assert resolve_effective_user_id(g) == "alice"


def test_derivation_is_deterministic_and_per_user():
    # Same id -> same UUID (cross-pod query key); different ids -> different UUIDs.
    assert derive_message_owner_uuid("alice") == derive_message_owner_uuid("alice")
    assert derive_message_owner_uuid("alice") != derive_message_owner_uuid("bob")
    # A UUID-shaped id is used directly, not re-derived.
    real = uuid4()
    assert derive_message_owner_uuid(str(real)) == real


def test_placeholder_none_is_treated_as_no_owner():
    # PlaceholderGraph stringifies a missing user as "None"; it must read as no owner,
    # not a user literally named "None", so retrieval stays unscoped rather than
    # over-filtering to zero rows.
    assert resolve_message_owner_id(_graph(user_id="None")) is None
    assert resolve_effective_user_id(_graph(user_id="None")) is None
    assert resolve_message_owner_id(_graph(user_id="null", end_user_id="None")) is None


def test_missing_attributes_return_none():
    # An object with neither attribute (defensive: not every graph-like carries them).
    assert resolve_message_owner_id(SimpleNamespace()) is None
    assert resolve_effective_user_id(SimpleNamespace()) is None
