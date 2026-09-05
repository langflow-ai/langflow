"""Recorded-fixture contract tests for the four user-identity actions."""

from __future__ import annotations

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx.schema.data import Data
from lfx_slack import (
    SlackCanvasComponent,
    SlackReadThreadComponent,
    SlackSearchComponent,
    SlackSendAsUserComponent,
)


@pytest.fixture
def user_resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver(identity="user_delegated", tokens=["xoxp-user-token"])  # pragma: allowlist secret
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


@pytest.mark.usefixtures("user_resolver")
async def test_search_sends_the_declared_parameters_and_parses_matches(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("search_messages"))
    component = build_component(
        SlackSearchComponent,
        query="  in:#general deploy  ",
        count=25,
        sort="timestamp",
        sort_dir="asc",
        cursor="page-2",
    )

    matches = await component.build_matches()

    assert transport.last.method == "search.messages"
    params = transport.last.params
    assert params["query"] == "in:#general deploy"
    assert params["count"] == 25
    assert params["sort"] == "timestamp"
    assert params["sort_dir"] == "asc"
    assert params["cursor"] == "page-2"
    assert transport.last.authorization == "Bearer xoxp-user-token"
    assert [m.data["text"] for m in matches] == ["deploy is green", "deploy rolled back"]
    assert all(isinstance(m, Data) for m in matches)


@pytest.mark.usefixtures("user_resolver")
async def test_search_surfaces_pagination_without_a_second_api_call(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("search_messages"))
    component = build_component(SlackSearchComponent, query="deploy")

    matches = await component.build_matches()
    pagination = await component.build_pagination()

    assert len(matches) == 2
    assert len(transport.calls) == 1, "the second output must reuse the memoized response"
    assert pagination.data["next_cursor"] == "dXNlcjpVMDYxTkZUVDI="
    assert pagination.data["total_count"] == 2


@pytest.mark.usefixtures("user_resolver", "transport")
async def test_search_rejects_an_out_of_range_page_size() -> None:
    component = build_component(SlackSearchComponent, query="deploy", count=250)

    with pytest.raises(ValueError, match="between 1 and 100"):
        await component.build_matches()


@pytest.mark.usefixtures("user_resolver")
async def test_read_thread_requests_the_parent_and_reports_more_pages(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("conversations_replies"))
    component = build_component(
        SlackReadThreadComponent,
        channel="C0SLACKDEMO",
        ts="1700000000.000100",
        limit=15,
        oldest="1699999999.000000",
    )

    messages = await component.build_messages()
    pagination = await component.build_pagination()

    assert transport.last.method == "conversations.replies"
    params = transport.last.params
    assert params["channel"] == "C0SLACKDEMO"
    assert params["ts"] == "1700000000.000100"
    assert params["limit"] == 15
    assert params["oldest"] == "1699999999.000000"
    assert "latest" not in params
    assert [m.data["text"] for m in messages] == ["who owns the release?", "I do"]
    assert pagination.data == {"has_more": True, "next_cursor": "bmV4dC1wYWdlLWN1cnNvcg=="}


@pytest.mark.usefixtures("user_resolver", "transport")
async def test_read_thread_requires_a_channel_and_timestamp() -> None:
    with pytest.raises(ValueError, match="Channel ID is required"):
        await build_component(SlackReadThreadComponent, channel="", ts="1.0").build_messages()
    with pytest.raises(ValueError, match="Thread timestamp is required"):
        await build_component(SlackReadThreadComponent, channel="C0", ts="  ").build_messages()


@pytest.mark.usefixtures("user_resolver")
async def test_send_as_user_posts_with_the_user_token(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("chat_postmessage"))
    component = build_component(
        SlackSendAsUserComponent,
        channel="C0SLACKDEMO",
        text="release is out",
        thread_ts="1700000000.000100",
        blocks=[Data(data={"type": "section", "text": {"type": "mrkdwn", "text": "hi"}})],
        unfurl_links=False,
    )

    message = await component.build_message()

    assert transport.last.method == "chat.postMessage"
    params = transport.last.params
    assert params["channel"] == "C0SLACKDEMO"
    assert params["text"] == "release is out"
    assert params["thread_ts"] == "1700000000.000100"
    assert params["unfurl_links"] is False
    assert transport.last.authorization == "Bearer xoxp-user-token"
    assert message.data["ts"] == "1700000200.000400"
    assert message.data["message"]["text"] == "release is out"


@pytest.mark.usefixtures("user_resolver", "transport")
async def test_send_as_user_rejects_text_slack_would_truncate() -> None:
    component = build_component(SlackSendAsUserComponent, channel="C0SLACKDEMO", text="x" * 40_001)

    with pytest.raises(ValueError, match="Slack truncates above 40000"):
        await component.build_message()


@pytest.mark.usefixtures("user_resolver")
async def test_canvas_sends_markdown_document_content(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("canvases_create"))
    component = build_component(
        SlackCanvasComponent,
        title="Release notes",
        markdown="# Release\n\nAll green.",
        channel_id="C0SLACKDEMO",
    )

    canvas = await component.build_canvas()

    assert transport.last.method == "canvases.create"
    params = transport.last.params
    assert params["document_content"] == {"type": "markdown", "markdown": "# Release\n\nAll green."}
    assert params["title"] == "Release notes"
    assert params["channel_id"] == "C0SLACKDEMO"
    assert canvas.data["canvas_id"] == "F0SLACKDOC1"


@pytest.mark.usefixtures("user_resolver", "transport")
async def test_canvas_rejects_markdown_above_the_slack_limit() -> None:
    component = build_component(SlackCanvasComponent, markdown="x" * (1024 * 1024 + 1))

    with pytest.raises(ValueError, match="Slack accepts up to 1048576"):
        await component.build_canvas()
