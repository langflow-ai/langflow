"""Unit tests for owner-scoped storage naming shared by the remote KB backends."""

from __future__ import annotations

from uuid import uuid4

import pytest
from lfx.base.knowledge_bases.backends.naming import (
    STORAGE_ROUTING_KEYS,
    StorageRoutingNotAllowedError,
    ensure_storage_routing_allowed,
    owner_scoped_collection_name,
    resolve_storage_name,
)


def _resolve(*, owner_id, override=None, kb_name="docs") -> str:
    return resolve_storage_name(
        kb_name=kb_name,
        owner_id=owner_id,
        override=override,
        override_key="collection_name",
        backend="ChromaCloudBackend",
        storage="collection",
    )


def test_owner_scoped_name_separates_owner_and_name_boundaries() -> None:
    # Length prefixes keep ("ab", "c") and ("a", "bc")-style splits apart.
    owner = uuid4()
    assert owner_scoped_collection_name(owner, "docs") != owner_scoped_collection_name(owner, "docs ")
    assert owner_scoped_collection_name(owner, "docs") != owner_scoped_collection_name(uuid4(), "docs")


def test_resolve_without_override_is_owner_scoped() -> None:
    owner = uuid4()
    assert _resolve(owner_id=owner) == owner_scoped_collection_name(owner, "docs")


def test_resolve_without_override_or_owner_fails_closed() -> None:
    with pytest.raises(ValueError, match="valid user_id to isolate its collection"):
        _resolve(owner_id=None)


def test_resolve_honors_an_ordinary_override_without_an_owner() -> None:
    assert _resolve(owner_id=None, override="external") == "external"


@pytest.mark.parametrize("case", [str.lower, str.upper])
def test_resolve_rejects_another_owners_scoped_name_in_any_case(case) -> None:
    victim = owner_scoped_collection_name(uuid4(), "docs")
    with pytest.raises(ValueError, match="reserved for owner-scoped"):
        _resolve(owner_id=uuid4(), override=case(victim))


def test_resolve_allows_the_knowledge_bases_own_scoped_name() -> None:
    owner = uuid4()
    own = owner_scoped_collection_name(owner, "docs")
    assert _resolve(owner_id=owner, override=own) == own


@pytest.mark.parametrize("key", STORAGE_ROUTING_KEYS)
def test_storage_routing_keys_require_a_superuser(key: str) -> None:
    with pytest.raises(StorageRoutingNotAllowedError, match=key):
        ensure_storage_routing_allowed({"mode": "cloud", key: "docs"}, is_superuser=False)
    ensure_storage_routing_allowed({"mode": "cloud", key: "docs"}, is_superuser=True)


@pytest.mark.parametrize(
    "backend_config",
    [
        {},
        {"index_name": "", "collection_name": None},
        {"url_variable": "OPENSEARCH_URL", "vector_field": "vector_field"},
        None,
        "not-a-dict",
    ],
)
def test_empty_or_unrelated_config_is_allowed_for_regular_users(backend_config) -> None:
    ensure_storage_routing_allowed(backend_config, is_superuser=False)
