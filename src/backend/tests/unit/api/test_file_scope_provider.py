"""The server may stamp extra file scopes on a run's graph, and only through a registered provider."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api import warm_graph
from langflow.api.utils.flow_utils import (
    build_and_cache_graph_from_data,
    build_graph_from_data,
    get_authorized_extra_file_scopes,
    register_file_scope_provider,
)

pytestmark = pytest.mark.no_blockbuster

_MINIMAL_FLOW = {"nodes": [], "edges": []}


@pytest.fixture(autouse=True)
def _no_provider_left_behind():
    register_file_scope_provider(None)
    yield
    register_file_scope_provider(None)


async def test_no_provider_means_no_extra_scopes() -> None:
    assert await get_authorized_extra_file_scopes(uuid4(), str(uuid4())) == frozenset()


async def test_provider_answer_is_stamped_for_this_flow_and_user() -> None:
    seen = []

    async def provider(flow_id, user_id):
        seen.append((str(flow_id), str(user_id)))
        return {" user-owner ", "", "user-owner"}

    register_file_scope_provider(provider)
    flow_id, user_id = uuid4(), uuid4()

    assert await get_authorized_extra_file_scopes(flow_id, user_id) == frozenset({"user-owner"})
    assert seen == [(str(flow_id), str(user_id))]


@pytest.mark.parametrize("answer", [None, 5, "user-owner", object()])
async def test_a_malformed_provider_answer_grants_nothing(answer) -> None:
    async def provider(_flow_id, _user_id):
        return answer

    register_file_scope_provider(provider)

    assert await get_authorized_extra_file_scopes(uuid4(), str(uuid4())) == frozenset()


@pytest.mark.parametrize("bad", ["../bad", "..", ".", "a/b", "a\\b", "a\x00b", "user-", "user-../x", "user-a/b"])
async def test_one_invalid_member_voids_the_whole_answer(bad) -> None:
    async def provider(_flow_id, _user_id):
        return {"user-owner", bad}

    register_file_scope_provider(provider)

    assert await get_authorized_extra_file_scopes(uuid4(), str(uuid4())) == frozenset()


async def test_a_failing_provider_fails_closed() -> None:
    async def provider(_flow_id, _user_id):
        msg = "boom"
        raise RuntimeError(msg)

    register_file_scope_provider(provider)

    assert await get_authorized_extra_file_scopes(uuid4(), str(uuid4())) == frozenset()


async def test_no_user_means_the_provider_is_not_asked() -> None:
    async def provider(_flow_id, _user_id):
        msg = "must not be called without a run user"
        raise AssertionError(msg)

    register_file_scope_provider(provider)

    assert await get_authorized_extra_file_scopes(uuid4(), None) == frozenset()


async def test_build_graph_from_data_stamps_the_graph_before_components_read_files() -> None:
    async def provider(_flow_id, _user_id):
        return {"user-owner"}

    register_file_scope_provider(provider)

    graph = await build_graph_from_data(uuid4(), _MINIMAL_FLOW, flow_name="flow", user_id=str(uuid4()))

    assert graph.authorized_extra_file_scopes == frozenset({"user-owner"})


async def test_build_graph_from_data_without_a_provider_stamps_nothing() -> None:
    graph = await build_graph_from_data(uuid4(), _MINIMAL_FLOW, flow_name="flow", user_id=str(uuid4()))

    assert graph.authorized_extra_file_scopes == frozenset()


async def test_the_playground_cache_seam_stamps_too() -> None:
    class _ChatServiceStub:
        async def set_cache(self, key, value) -> None: ...

    async def provider(_flow_id, _user_id):
        return {"user-owner"}

    register_file_scope_provider(provider)

    graph = await build_and_cache_graph_from_data(uuid4(), _ChatServiceStub(), _MINIMAL_FLOW, user_id=str(uuid4()))

    assert graph.authorized_extra_file_scopes == frozenset({"user-owner"})


class _WarmTemplate:
    """The part of a warm template ``warm_deepcopy`` touches; it mimics ``Graph.copy_for_run``'s stamp rule."""

    def __init__(self) -> None:
        self.vertices: list = []
        self.user_id = None
        self.session_id = None
        self.has_session_id_vertices: list[str] = []
        self.authorized_extra_file_scopes = frozenset({"user-stale"})

    def get_vertex(self, _vertex_id: str):
        return None

    def copy_for_run(self, *, user_id, before_instantiate=None, authorized_extra_file_scopes=None):  # noqa: ARG002
        copied = deepcopy(self)
        copied.user_id = user_id
        copied.authorized_extra_file_scopes = frozenset(authorized_extra_file_scopes or ())
        return copied


@pytest.mark.parametrize("registered", [True, False])
async def test_a_warm_copy_gets_this_runs_scopes_and_never_the_templates(
    monkeypatch: pytest.MonkeyPatch,
    registered: bool,  # noqa: FBT001
) -> None:
    from langflow.services import deps
    from langflow.services.warm_registry import service as registry_service

    template = _WarmTemplate()
    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: True)
    monkeypatch.setattr(deps, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(
        registry_service, "get_warm_registry", lambda: SimpleNamespace(get=lambda _id: (template, "v1"))
    )
    asked = []

    async def provider(flow_id, user_id):
        asked.append((flow_id, user_id))
        return {"user-owner"}

    if registered:
        register_file_scope_provider(provider)

    graph = await warm_graph.warm_deepcopy("flow-id", expected_version="v1", user_id="runner", session_id="s")

    assert graph is not None
    assert graph.authorized_extra_file_scopes == (frozenset({"user-owner"}) if registered else frozenset())
    assert asked == ([("flow-id", "runner")] if registered else [])
    assert template.authorized_extra_file_scopes == frozenset({"user-stale"})
