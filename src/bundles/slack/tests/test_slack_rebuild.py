"""A rebuilt Slack vertex must talk to Slack again, not replay its first response.

``run_action`` memoizes the Web API response so a component with two outputs
(Messages plus Pagination) costs one call against Slack's per-method rate tier.
The graph, however, reuses one component instance across builds: a vertex inside
a cycle has ``output.cache`` forced to ``False`` so its outputs recompute every
iteration (``Graph._set_cache_to_vertices_in_cycle``), and ``Vertex.build`` keeps
the same ``custom_component``. Without a per-build reset a Slack write action in
a Loop would post once and then report that first response for every later
iteration -- N green statuses, one message in the channel.

``Component._build_results`` calls ``_pre_run_setup`` once per build, so that is
where the memo is dropped. These tests drive both the framework hook and the
public build methods.
"""

from __future__ import annotations

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx_slack import SlackPostAsAppComponent, SlackReadThreadComponent


@pytest.fixture
def bot_resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver(identity="bot", tokens=["xoxb-bot-token"])  # pragma: allowlist secret
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


@pytest.fixture
def user_resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver(identity="user_delegated", tokens=["xoxp-user-token"])  # pragma: allowlist secret
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


@pytest.mark.usefixtures("bot_resolver")
async def test_a_rebuilt_write_action_posts_again(transport: SlackTransport) -> None:
    """The Loop case: the same instance is built twice and must post twice."""
    first = load_fixture("chat_postmessage")
    second = {**first, "ts": "1700000300.000500"}
    transport.enqueue(first).enqueue(second)
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")

    component._pre_run_setup_if_needed()
    first_message = await component.build_message()
    component._pre_run_setup_if_needed()
    second_message = await component.build_message()

    assert len(transport.calls) == 2, "a rebuilt vertex must issue a second Slack request"
    assert first_message.data["ts"] == "1700000200.000400"
    assert second_message.data["ts"] == "1700000300.000500"


@pytest.mark.usefixtures("bot_resolver")
async def test_the_framework_build_path_clears_the_memo(transport: SlackTransport) -> None:
    """Same thing through ``_build_results``, with a cycle vertex's cache setting."""
    transport.enqueue(load_fixture("chat_postmessage")).enqueue(load_fixture("chat_postmessage"))
    component = build_component(SlackPostAsAppComponent, channel="C0SLACKDEMO", text="hi")
    component._vertex.outgoing_edges = []
    for output in component._outputs_map.values():
        # Exactly what Graph._set_cache_to_vertices_in_cycle does to a cycle vertex.
        output.cache = False

    await component._build_results()
    await component._build_results()

    assert len(transport.calls) == 2


@pytest.mark.usefixtures("user_resolver")
async def test_the_memo_still_spans_the_outputs_of_one_build(transport: SlackTransport) -> None:
    """The reset must not cost a second call for a two-output component."""
    transport.enqueue(load_fixture("conversations_replies"))
    component = build_component(SlackReadThreadComponent, channel="C0SLACKDEMO", ts="1700000000.000100")

    component._pre_run_setup_if_needed()
    messages = await component.build_messages()
    pagination = await component.build_pagination()

    assert len(transport.calls) == 1, "both outputs of one build share the response"
    assert len(messages) == 2
    assert pagination.data["has_more"] is True
