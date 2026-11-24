"""Opt-in live-workspace suite for the seven Slack actions.

Never run in CI: .github/workflows/cross-bundle-test.yml deselects
``api_key_required``, and every test here also self-skips when its environment
variables are absent.

Run it by hand against a workspace where a Langflow Slack app is installed:

```bash
export LANGFLOW_SLACK_LIVE_USER_TOKEN=xoxp-...
export LANGFLOW_SLACK_LIVE_BOT_TOKEN=xoxb-...
export LANGFLOW_SLACK_LIVE_CHANNEL=C0SLACKDEMO
.venv/bin/python -m pytest src/bundles/slack/tests/test_slack_live.py -q -m api_key_required
```

The user token needs `search:read`, the four `*:history` scopes, `chat:write`,
and `canvases:write`; the bot token needs `chat:write`, `reactions:write`,
`channels:read` (plus `groups:read` for a private channel and `users:read` to
resolve display names), and the bot must be a member of the channel. The suite
posts real messages, adds a real reaction, and creates a real canvas.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest
from lfx.integrations.models import ConnectionAccount, ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_slack import (
    SlackAddReactionComponent,
    SlackCanvasComponent,
    SlackListChannelMembersComponent,
    SlackPostAsAppComponent,
    SlackReadThreadComponent,
    SlackSearchComponent,
    SlackSendAsUserComponent,
)
from pydantic import SecretStr

pytestmark = pytest.mark.api_key_required

USER_TOKEN_ENV = "LANGFLOW_SLACK_LIVE_USER_TOKEN"  # noqa: S105 - env var name, not a token
BOT_TOKEN_ENV = "LANGFLOW_SLACK_LIVE_BOT_TOKEN"  # noqa: S105 - env var name, not a token
CHANNEL_ENV = "LANGFLOW_SLACK_LIVE_CHANNEL"


class _LiveResolver:
    """Hands a manually provisioned workspace token to the component."""

    def __init__(self, token: str, identity: str) -> None:
        self._token = token
        self._identity = identity

    async def resolve(self, request: Any) -> ResolvedCredential:
        return ResolvedCredential(
            access_token=SecretStr(self._token),
            provider="slack",
            name=request.ref.name,
            owner_kind="env",
            identity=self._identity,
            account=ConnectionAccount(id="live"),
        )

    async def describe(self, _ref: Any, _principal: Any) -> None:
        return None


def _require(*names: str) -> list[str]:
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.skip(f"live Slack suite needs {', '.join(missing)}")
    return [os.environ[name] for name in names]


def _live_component(monkeypatch: pytest.MonkeyPatch, component_class: type, token: str, identity: str, **kwargs: Any):
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: _LiveResolver(token, identity))
    component = component_class(connection="slack/live", **kwargs)
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="headless_operator", interactive=False),
        flow_id=None,
        run_id=None,
        session_id="live",
    )
    component.set_vertex(SimpleNamespace(graph=graph))
    return component


async def test_search_as_user(monkeypatch: pytest.MonkeyPatch) -> None:
    (token,) = _require(USER_TOKEN_ENV)
    component = _live_component(monkeypatch, SlackSearchComponent, token, "user_delegated", query="langflow", count=5)

    matches = await component.build_matches()

    assert isinstance(matches, list)


async def test_send_read_and_canvas_as_user(monkeypatch: pytest.MonkeyPatch) -> None:
    token, channel = _require(USER_TOKEN_ENV, CHANNEL_ENV)

    sender = _live_component(
        monkeypatch,
        SlackSendAsUserComponent,
        token,
        "user_delegated",
        channel=channel,
        text="Langflow lfx-slack live suite: send as user",
    )
    message = await sender.build_message()
    assert message.data["ts"]

    reader = _live_component(
        monkeypatch,
        SlackReadThreadComponent,
        token,
        "user_delegated",
        channel=channel,
        ts=message.data["ts"],
    )
    replies = await reader.build_messages()
    assert replies[0].data["ts"] == message.data["ts"]

    canvas = _live_component(
        monkeypatch,
        SlackCanvasComponent,
        token,
        "user_delegated",
        title="Langflow lfx-slack live suite",
        markdown="# live suite\n\ncreated by the lfx-slack opt-in tests",
        channel_id=channel,
    )
    created = await canvas.build_canvas()
    assert created.data["canvas_id"]


async def test_post_react_and_list_members_as_app(monkeypatch: pytest.MonkeyPatch) -> None:
    token, channel = _require(BOT_TOKEN_ENV, CHANNEL_ENV)

    poster = _live_component(
        monkeypatch,
        SlackPostAsAppComponent,
        token,
        "bot",
        channel=channel,
        text="Langflow lfx-slack live suite: post as app",
    )
    message = await poster.build_message()
    assert message.data["ts"]

    reaction = _live_component(
        monkeypatch,
        SlackAddReactionComponent,
        token,
        "bot",
        channel=channel,
        timestamp=message.data["ts"],
        emoji_name="white_check_mark",
    )
    assert (await reaction.build_result()).data["ok"] is True

    members = _live_component(
        monkeypatch,
        SlackListChannelMembersComponent,
        token,
        "bot",
        channel=channel,
        resolve_names=True,
        limit=5,
    )
    listed = await members.build_members()
    assert listed
    assert listed[0].data["id"]
