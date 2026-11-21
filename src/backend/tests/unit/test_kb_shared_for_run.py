"""A flow run may use a KB it does not own only when a plane registers it, and only for the action a share allows."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langflow.api.utils import knowledge_base_service as service
from lfx.components.files_and_knowledge.knowledge import MODE_INGEST, MODE_RETRIEVE, KnowledgeComponent

RUNNER = uuid.uuid4()
OWNER = uuid.uuid4()
SHARED = SimpleNamespace(id=uuid.uuid4(), user_id=OWNER, name="docs")


class _Authz:
    """Allows ``knowledge_base:<id>`` for the listed actions only."""

    def __init__(self, allowed: dict[uuid.UUID, set[str]], *, enabled: bool = True) -> None:
        self.allowed, self.enabled, self.asked = allowed, enabled, []

    async def is_enabled(self) -> bool:
        return self.enabled

    async def supports_cross_user_fetch(self) -> bool:
        return True

    async def enforce(self, *, user_id, domain, obj, act, context=None) -> bool:  # noqa: ARG002
        self.asked.append((user_id, obj, act))
        return act in self.allowed.get(uuid.UUID(obj.split(":")[1]), set())


@pytest.fixture(autouse=True)
def _unregister():
    yield
    service._shared_kb_for_run_enabled = None


def _plane(authz, candidates=(SHARED,)):
    service.register_shared_kb_for_run(lambda: True)
    return (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch.object(service, "list_by_name", AsyncMock(return_value=list(candidates))),
    )


async def test_nothing_registered_finds_nothing_and_never_asks_authorization() -> None:
    with patch("langflow.services.deps.get_authorization_service", side_effect=AssertionError("asked")):
        assert await service.get_shared_for_run(RUNNER, "docs", "read") is None


async def test_registered_but_switched_off_finds_nothing() -> None:
    service.register_shared_kb_for_run(lambda: False)
    with patch("langflow.services.deps.get_authorization_service", side_effect=AssertionError("asked")):
        assert await service.get_shared_for_run(RUNNER, "docs", "read") is None


async def test_a_share_that_allows_the_action_resolves_to_the_owners_row() -> None:
    authz = _Authz({SHARED.id: {"read"}})
    deps, listing = _plane(authz)
    with deps, listing:
        assert await service.get_shared_for_run(RUNNER, "docs", "read") is SHARED
    assert authz.asked == [(RUNNER, f"knowledge_base:{SHARED.id}", "read")]


async def test_a_read_share_does_not_open_ingestion() -> None:
    deps, listing = _plane(_Authz({SHARED.id: {"read"}}))
    with deps, listing:
        assert await service.get_shared_for_run(RUNNER, "docs", "ingest") is None


async def test_authorization_off_finds_nothing() -> None:
    deps, listing = _plane(_Authz({SHARED.id: {"read"}}, enabled=False))
    with deps, listing:
        assert await service.get_shared_for_run(RUNNER, "docs", "read") is None


async def test_two_allowed_candidates_are_refused() -> None:
    other = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), name="docs")
    deps, listing = _plane(_Authz({SHARED.id: {"read"}, other.id: {"read"}}), candidates=(SHARED, other))
    with deps, listing, pytest.raises(ValueError, match="Several knowledge bases"):
        await service.get_shared_for_run(RUNNER, "docs", "read")


async def test_the_runners_own_row_is_never_a_shared_candidate() -> None:
    own = SimpleNamespace(id=uuid.uuid4(), user_id=RUNNER, name="docs")
    authz = _Authz({own.id: {"read"}})
    deps, listing = _plane(authz, candidates=(own,))
    with deps, listing:
        assert await service.get_shared_for_run(RUNNER, "docs", "read") is None
    assert authz.asked == []


def _component(mode: str) -> KnowledgeComponent:
    component = KnowledgeComponent()
    component._user_id = str(RUNNER)
    component.knowledge_base = "docs"
    component.mode = mode
    return component


async def test_component_uses_its_own_row_and_skips_the_shared_lookup() -> None:
    own = SimpleNamespace(id=uuid.uuid4(), user_id=RUNNER, name="docs")
    with (
        patch.object(service, "get_by_user_and_name", AsyncMock(return_value=own)),
        patch.object(service, "get_shared_for_run", AsyncMock(side_effect=AssertionError("asked"))),
    ):
        assert await _component(MODE_RETRIEVE)._find_record() is own


@pytest.mark.parametrize(("mode", "action"), [(MODE_RETRIEVE, "read"), (MODE_INGEST, "ingest")])
async def test_component_falls_back_to_the_shared_row_for_its_mode(mode: str, action: str) -> None:
    shared = AsyncMock(return_value=SHARED)
    with (
        patch.object(service, "get_by_user_and_name", AsyncMock(return_value=None)),
        patch.object(service, "get_shared_for_run", shared),
    ):
        component = _component(mode)
        assert await component._find_record() is SHARED
    shared.assert_awaited_once_with(RUNNER, "docs", action)


async def test_component_without_any_row_has_no_storage_record() -> None:
    with (
        patch.object(service, "get_by_user_and_name", AsyncMock(return_value=None)),
        patch.object(service, "get_shared_for_run", AsyncMock(return_value=None)),
    ):
        assert await _component(MODE_RETRIEVE)._find_record() is None


async def test_reused_component_checks_current_permission_each_build() -> None:
    component = _component(MODE_RETRIEVE)
    shared = AsyncMock(side_effect=[SHARED, None])
    with (
        patch.object(service, "get_by_user_and_name", AsyncMock(return_value=None)),
        patch.object(service, "get_shared_for_run", shared),
    ):
        component._pre_run_setup()
        assert await component._find_record() is SHARED
        component._pre_run_setup()
        assert await component._find_record() is None
    assert shared.await_count == 2


@pytest.mark.parametrize("purpose", ["configure", "use"])
async def test_saved_retrieve_preflight_uses_raw_mode_for_read_only_share(purpose) -> None:
    from lfx.services.model_provider_policy import ModelProviderPolicyPurpose

    component = _component(MODE_INGEST)
    authz = _Authz({SHARED.id: {"read"}})
    deps, listing = _plane(authz)
    with (
        deps,
        listing,
        patch.object(service, "get_by_user_and_name", AsyncMock(return_value=None)),
        patch.object(service, "record_to_metadata_dict", return_value={"embedding_provider": "OpenAI"}),
        patch("lfx.services.model_provider_policy.aresolve_model_provider_policy", new_callable=AsyncMock) as policy,
    ):
        policy.return_value.require = lambda _provider: None
        await component.arequire_model_provider_policy(
            ModelProviderPolicyPurpose(purpose),
            user_id=str(RUNNER),
            parameters={"knowledge_base": "docs", "mode": "🔍 Retrieve"},
        )
    assert authz.asked == [(RUNNER, f"knowledge_base:{SHARED.id}", "read")]
    policy.assert_awaited_once_with(
        user_id=str(RUNNER), providers=["openai"], purpose=ModelProviderPolicyPurpose(purpose)
    )
