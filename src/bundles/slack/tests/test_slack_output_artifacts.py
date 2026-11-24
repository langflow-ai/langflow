"""List outputs expose their records and pagination in the canvas inspector."""

from __future__ import annotations

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx_slack import SlackListChannelMembersComponent, SlackReadThreadComponent, SlackSearchComponent


@pytest.mark.parametrize("pagination_first", [False, True])
@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    ("component_class", "inputs", "fixture_name", "output_name", "identity"),
    [
        (SlackSearchComponent, {"query": "deploy"}, "search_messages", "matches", "user_delegated"),
        (
            SlackReadThreadComponent,
            {"channel": "C0SLACKDEMO", "ts": "1700000000.000100"},
            "conversations_replies",
            "messages",
            "user_delegated",
        ),
        (SlackListChannelMembersComponent, {"channel": "C0SLACKDEMO"}, "conversations_members", "members", "bot"),
        (
            SlackListChannelMembersComponent,
            {"channel": "C0SLACKDEMO", "resolve_names": True},
            "conversations_members",
            "members",
            "bot",
        ),
    ],
)
async def test_list_artifacts_include_records_and_pagination(
    transport: SlackTransport,
    monkeypatch: pytest.MonkeyPatch,
    component_class,
    inputs,
    fixture_name,
    output_name,
    identity,
    empty,
    pagination_first,
) -> None:
    token = "xoxb-bot-token" if identity == "bot" else "xoxp-user-token"  # pragma: allowlist secret
    resolver = FakeResolver(identity=identity, tokens=[token])
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    body = load_fixture(fixture_name)
    payload = body["messages"] if output_name == "matches" else body
    if empty:
        payload[output_name] = []
    expected_rows = payload[output_name]
    if output_name == "members":
        expected_rows = [{"id": member} for member in expected_rows]
    transport.enqueue(body)
    if inputs.get("resolve_names") and not empty:
        expected_rows = []
        for index, member_id in enumerate(body["members"]):
            user_body = load_fixture("users_info")
            user = user_body["user"]
            user.update(id=member_id, name=f"member-{index}", real_name=f"Member {index}")
            user["profile"]["display_name"] = f"member-{index}"
            expected_rows.append(
                {
                    "id": member_id,
                    "name": user["name"],
                    "real_name": user["real_name"],
                    "display_name": user["profile"]["display_name"],
                    "is_bot": user["is_bot"],
                }
            )
            transport.enqueue(user_body)
    expected_pagination = {"next_cursor": body["response_metadata"]["next_cursor"]}
    if output_name == "matches":
        expected_pagination.update(payload["pagination"])
    elif output_name == "messages":
        expected_pagination["has_more"] = body["has_more"]
    component = build_component(component_class, **inputs)
    component._vertex.outgoing_edges = []
    if pagination_first:
        component.outputs = list(reversed(component.outputs))

    results, artifacts = await component._build_results()

    assert [row.data for row in results[output_name]] == expected_rows
    if output_name == "members":
        assert [row.data["id"] for row in results[output_name]] == body["members"]
    assert artifacts[output_name]["repr"] == str(results[output_name])
    assert artifacts[output_name]["type"] == "array"
    assert [row["data"] for row in artifacts[output_name]["raw"]] == expected_rows
    assert results["pagination"].data == expected_pagination
    assert artifacts["pagination"]["repr"] == str(results["pagination"])
    assert artifacts["pagination"]["type"] == "object"
    assert artifacts["pagination"]["raw"] == expected_pagination
    expected_calls = 1 + (len(expected_rows) if inputs.get("resolve_names") else 0)
    assert len(transport.calls) == expected_calls
