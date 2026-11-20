"""A flow run uses a memory base it does not own only when a plane registers it, and only for an allowed action."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.memory_base import run_lookup

RUNNER = uuid.uuid4()
OWNER = uuid.uuid4()
FLOW = uuid.uuid4()
SHARED = SimpleNamespace(id=uuid.uuid4(), user_id=OWNER, name="chat-memory", flow_id=FLOW, kb_name="mb_kb")


class _Authz:
    """Allows ``knowledge_base:<id>`` (a memory base is authorized as a knowledge base) for the listed actions only."""

    def __init__(self, allowed: dict[uuid.UUID, set[str]], *, enabled: bool = True) -> None:
        self.allowed, self.enabled, self.asked = allowed, enabled, []

    async def is_enabled(self) -> bool:
        return self.enabled

    async def supports_cross_user_fetch(self) -> bool:
        return True

    async def batch_enforce(self, *, user_id, domain, requests, context=None) -> list[bool]:  # noqa: ARG002
        self.asked.append((user_id, requests))
        return [act in self.allowed.get(uuid.UUID(obj.split(":")[1]), set()) for obj, act in requests]


def _db(own=None, others=()):
    """A session whose first query (the runner's own row) answers ``own`` and whose second lists ``others``."""
    owner_result, others_result = MagicMock(), MagicMock()
    owner_result.first.return_value = own
    others_result.all.return_value = list(others)
    db = MagicMock()
    db.exec = AsyncMock(side_effect=[owner_result, others_result])
    return db


@pytest.fixture(autouse=True)
def _unregister():
    yield
    run_lookup._shared_mb_for_run_enabled = None


def _plane(authz):
    run_lookup.register_shared_mb_for_run(lambda: True)
    return patch("langflow.services.deps.get_authorization_service", return_value=authz)


async def _find(db, action: str = "read"):
    return await run_lookup.find_for_run(db, name="chat-memory", flow_id=FLOW, user_id=RUNNER, action=action)


async def test_the_runners_own_row_wins_and_nothing_else_is_asked() -> None:
    own = SimpleNamespace(id=uuid.uuid4(), user_id=RUNNER)
    db = _db(own=own)
    with patch("langflow.services.deps.get_authorization_service", side_effect=AssertionError("asked")):
        assert await _find(db) is own
    assert db.exec.await_count == 1


async def test_nothing_registered_finds_nothing_and_never_asks_authorization() -> None:
    db = _db()
    with patch("langflow.services.deps.get_authorization_service", side_effect=AssertionError("asked")):
        assert await _find(db) is None
    assert db.exec.await_count == 1  # the owner lookup only, no candidate scan


async def test_registered_but_switched_off_finds_nothing() -> None:
    run_lookup.register_shared_mb_for_run(lambda: False)
    db = _db(others=[SHARED])
    with patch("langflow.services.deps.get_authorization_service", side_effect=AssertionError("asked")):
        assert await _find(db) is None


async def test_a_share_that_allows_the_action_resolves_to_the_owners_row() -> None:
    authz = _Authz({SHARED.id: {"read"}})
    with _plane(authz):
        assert await _find(_db(others=[SHARED])) is SHARED
    assert authz.asked == [(RUNNER, [(f"knowledge_base:{SHARED.id}", "read")])]


async def test_a_read_share_does_not_open_a_write_action() -> None:
    with _plane(_Authz({SHARED.id: {"read"}})):
        assert await _find(_db(others=[SHARED]), action="ingest") is None


async def test_no_share_means_not_attached() -> None:
    with _plane(_Authz({})):
        assert await _find(_db(others=[SHARED])) is None


async def test_authorization_off_finds_nothing() -> None:
    with _plane(_Authz({SHARED.id: {"read"}}, enabled=False)):
        assert await _find(_db(others=[SHARED])) is None


async def test_two_allowed_candidates_are_refused() -> None:
    other = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), name="chat-memory", flow_id=FLOW)
    with (
        _plane(_Authz({SHARED.id: {"read"}, other.id: {"read"}})),
        pytest.raises(ValueError, match="Several memory bases"),
    ):
        await _find(_db(others=[SHARED, other]))


async def test_one_allowed_among_several_candidates_is_used() -> None:
    other = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), name="chat-memory", flow_id=FLOW)
    with _plane(_Authz({SHARED.id: {"read"}})):
        assert await _find(_db(others=[other, SHARED])) is SHARED


def _component():
    from lfx.components.files_and_knowledge.memory_retrieval import MemoryBaseComponent

    component = MemoryBaseComponent()
    component._user_id = str(RUNNER)
    return component


async def test_component_attach_lookup_returns_the_shared_row_and_its_owner() -> None:
    owner = SimpleNamespace(id=OWNER, username="deployer")
    with (
        _plane(_Authz({SHARED.id: {"read"}})),
        patch("langflow.services.database.models.user.crud.get_user_by_id", AsyncMock(return_value=owner)) as get_owner,
    ):
        mb, found_owner = await _component()._resolve_attached_mb(_db(others=[SHARED]), "chat-memory", FLOW, RUNNER)
    assert (mb, found_owner) == (SHARED, owner)
    assert get_owner.await_args.args[1] == OWNER  # storage and credentials follow the row's owner, not the runner


async def test_component_attach_lookup_without_a_plane_still_says_not_attached() -> None:
    with pytest.raises(ValueError, match="not attached to this flow"):
        await _component()._resolve_attached_mb(_db(others=[SHARED]), "chat-memory", FLOW, RUNNER)


async def test_component_policy_selection_follows_the_shared_rows_owner() -> None:
    component = _component()
    scope = MagicMock()
    scope.__aenter__ = AsyncMock(return_value=_db(others=[SHARED]))
    scope.__aexit__ = AsyncMock(return_value=False)
    with (
        _plane(_Authz({SHARED.id: {"read"}})),
        patch.object(component, "_get_runtime_or_frontend_node_attr", return_value=str(FLOW)),
        patch("lfx.components.files_and_knowledge.memory_retrieval.session_scope", return_value=scope),
        patch(
            "langflow.api.utils.kb_helpers.resolve_embedding_selection", AsyncMock(return_value=("OpenAI", "m"))
        ) as pick,
    ):
        assert await component._policy_embedding_selection("chat-memory") == ("OpenAI", "m")
    pick.assert_awaited_once_with(user_id=OWNER, kb_name="mb_kb")
