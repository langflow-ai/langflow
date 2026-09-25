"""Opt-in live suite: Slack Socket Mode against a real workspace.

Never run in CI: the default ``-m "not api_key_required"`` deselects it, and every
test also self-skips when its environment variables are absent. Run it by hand
against a workspace where a Socket Mode Slack app (created from
``docs/static/files/slack/langflow-slack-app-socket-mode.json``) is installed and
invited to the channel:

```bash
export LANGFLOW_SLACK_LIVE_APP_TOKEN=xapp-...   # the app's app-level token (connections:write)
export LANGFLOW_SLACK_LIVE_USER_TOKEN=xoxp-...  # a user token with reactions:write
export LANGFLOW_SLACK_LIVE_CHANNEL=C0...        # a channel the app is a member of
uv run pytest src/backend/tests/integration/triggers/test_slack_socket_mode_live.py -m api_key_required -q -s
```

Watch the test output. When it prints a unique marker, a person must post a
message containing it in the configured channel and then two replies containing
it in that message's thread. A message sent through this app's Web API token,
including a user token, is attributed to the app and suppressed. The suite adds
a reaction to the human message through the API and leaves the human's messages
in place.

The Events API transport has no live test here: it needs Slack to reach this
process over public HTTPS. Its route, signature checks and fan-out are covered by
``tests/unit/api/v1/test_trigger_ingress_slack.py``, and the cross-track contract
test proves both transports produce identical Data from the same recorded bodies.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

import httpx
import pytest
from langflow.services.triggers.listeners.adapters import register_builtin_adapters
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

from tests.unit.services.triggers import slack_fixtures as fx

pytestmark = [pytest.mark.api_key_required, pytest.mark.no_blockbuster]

APP_TOKEN = os.environ.get("LANGFLOW_SLACK_LIVE_APP_TOKEN", "")
USER_TOKEN = os.environ.get("LANGFLOW_SLACK_LIVE_USER_TOKEN", "")
CHANNEL = os.environ.get("LANGFLOW_SLACK_LIVE_CHANNEL", "")

requires_workspace = pytest.mark.skipif(
    not (APP_TOKEN and USER_TOKEN and CHANNEL),
    reason="set LANGFLOW_SLACK_LIVE_APP_TOKEN, LANGFLOW_SLACK_LIVE_USER_TOKEN and LANGFLOW_SLACK_LIVE_CHANNEL",
)


async def _slack(method: str, **payload) -> dict:
    async with httpx.AsyncClient(base_url="https://slack.com/api", timeout=15) as http:
        response = await http.post(f"/{method}", json=payload, headers={"Authorization": f"Bearer {USER_TOKEN}"})
    body = response.json()
    assert body.get("ok"), f"{method}: {body.get('error')}"
    return body


async def _rows_matching(trigger_id, predicate, *, count: int, timeout: float = 120.0) -> list:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        rows = [row for row in await fx.events_for(trigger_id) if predicate(row.payload)]
        if len(rows) >= count:
            return rows
        if asyncio.get_running_loop().time() > deadline:
            msg = f"expected {count} event(s), got {len(rows)}"
            raise AssertionError(msg)
        await asyncio.sleep(0.5)


@requires_workspace
@pytest.mark.usefixtures("client")  # the database, and the app built before the listener flag is set
async def test_socket_mode_delivers_messages_threads_and_reactions_from_a_real_workspace(monkeypatch) -> None:
    from langflow.services.triggers.listeners import guard

    monkeypatch.setattr(guard, "_IS_LISTENER_PROCESS", True)
    register_builtin_adapters()
    owner = await fx.make_user("slack-live")
    flow_id = await fx.make_flow(owner)
    connection_id = await fx.make_app_token_connection(owner, token=APP_TOKEN)
    messages = await fx.arm(
        flow_id, owner, connection_id, mechanism="slack.socket_mode", config={"channels": [CHANNEL]}
    )
    reactions = await fx.arm(
        flow_id,
        owner,
        connection_id,
        kind="slack.reaction",
        mechanism="slack.socket_mode",
        config={"channels": [CHANNEL]},
    )
    marker = f"langflow-live-{uuid.uuid4().hex[:8]}"

    supervisor = ListenerSupervisor(holder="live")
    try:
        await supervisor.reconcile()
        await asyncio.sleep(3)  # let the socket say hello before Slack has anything to send

        sys.stdout.write(f"Post {marker} in {CHANNEL}, then post two replies containing {marker} in its thread.\n")
        sys.stdout.flush()
        thread = await _rows_matching(messages, lambda p: marker in (p.get("text") or ""), count=3)
        roots = [row for row in thread if not row.payload["is_thread_reply"]]
        assert len(roots) == 1, "post one top-level message and two replies in its thread"
        root_ts = roots[0].payload["ts"]
        await _slack("reactions.add", channel=CHANNEL, timestamp=root_ts, name="rocket")
        [reaction] = await _rows_matching(
            reactions, lambda p: p.get("item_ts") == root_ts and p.get("reaction") == "rocket", count=1
        )
    finally:
        await supervisor.stop()

    # Three messages in one thread are three events in one session.
    assert len({row.payload["session_key"] for row in thread}) == 1
    assert len({row.dedupe_key for row in thread}) == 3
    assert reaction.payload["type"] == "reaction_added"
