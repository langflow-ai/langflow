"""Load the recorded Slack Events API bodies and wrap them for Socket Mode.

Kept as a plain module (not a conftest) so the API tests, the adapter tests and
the cross-track contract test all read the same files the same way.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "slack"

TEAM_ID = "T0TEAM0001"
OTHER_TEAM_ID = "T0TEAM0002"
APP_ID = "A0APP00001"
BOT_USER_ID = "U0BOT00001"


def load(name: str) -> dict[str, Any]:
    """A fresh copy of one recorded body, so a test may mutate it freely."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


def names() -> list[str]:
    return sorted(path.stem for path in FIXTURES.glob("*.json"))


def raw(name: str) -> bytes:
    """The body exactly as it would be POSTed: the bytes a signature covers."""
    return json.dumps(load(name), separators=(",", ":")).encode()


def socket_envelope(body: dict[str, Any], *, envelope_id: str, retry_attempt: int = 0) -> dict[str, Any]:
    """The Socket Mode frame that carries ``body`` (https://docs.slack.dev/apis/socket-mode/)."""
    return {
        "envelope_id": envelope_id,
        "type": "events_api",
        "accepts_response_payload": False,
        "retry_attempt": retry_attempt,
        "retry_reason": "timeout" if retry_attempt else "",
        "payload": copy.deepcopy(body),
    }


def thread_replies(count: int) -> list[dict[str, Any]]:
    """``count`` distinct replies in one thread (distinct ``event_id`` and ``ts``)."""
    replies = []
    for index in range(count):
        body = load("message_thread_reply")
        body["event_id"] = f"Ev0THR{index:05d}"
        body["event"]["ts"] = body["event"]["event_ts"] = f"17000010{index:02d}.000{index:03d}"
        body["event"]["text"] = f"reply {index + 1}"
        replies.append(body)
    return replies


# --------------------------------------------------------------------------- #
# Database helpers: Slack connections and armed Slack triggers
# --------------------------------------------------------------------------- #

SIGNING_SECRET = "slack-signing-secret"  # noqa: S105 - test fixture  # pragma: allowlist secret
REGISTRATION_ID = "slack-app"


def registration(**overrides: Any) -> dict[str, Any]:
    """A customer-owned Slack bot registration that can receive events."""
    value = {
        "provider": "slack",
        "profile": "bot",
        "owner": "customer",
        "context": "self_managed",
        "client_type": "confidential",
        "client_id": "1234.5678",
        "client_secret": "client-secret-for-tests",  # pragma: allowlist secret
        "redirect_uri": "http://localhost:7860/api/v1/connections/oauth/slack/callback",
        "scopes": ["chat:write", "channels:history", "reactions:read", "app_mentions:read"],
        "signing_secret": SIGNING_SECRET,
    }
    value.update(overrides)
    return {key: item for key, item in value.items() if item is not None}


def use_registrations(monkeypatch, registrations: dict[str, dict[str, Any]] | None = None) -> None:
    """Configure ``LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS`` for this test."""
    monkeypatch.setenv(
        "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS",
        json.dumps(registrations if registrations is not None else {REGISTRATION_ID: registration()}),
    )


def sign(body: bytes, *, secret: str = SIGNING_SECRET, timestamp: int | None = None) -> dict[str, str]:
    """Slack's v0 request signature for ``body``."""
    import hashlib
    import hmac
    import time

    stamp = str(int(time.time()) if timestamp is None else timestamp)
    digest = hmac.new(secret.encode(), f"v0:{stamp}:".encode() + body, hashlib.sha256).hexdigest()
    return {"X-Slack-Signature": f"v0={digest}", "X-Slack-Request-Timestamp": stamp, "Content-Type": "application/json"}


async def make_user(prefix: str = "slack-user"):
    from uuid import uuid4

    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        user = User(username=f"{prefix}-{uuid4().hex[:8]}", password="not-a-login", is_active=True)  # noqa: S106  # pragma: allowlist secret
        session.add(user)
        await session.flush()
        return user.id


async def make_flow(owner_id):
    from uuid import uuid4

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        flow = Flow(name=f"slack-flow-{uuid4().hex[:6]}", user_id=owner_id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        return flow.id


async def make_oauth_connection(
    owner_id,
    *,
    team_id: str = TEAM_ID,
    registration_id: str = REGISTRATION_ID,
    status: str = "ready",
    ownership_mode: str = "user",
    name: str | None = None,
):
    """An OAuth bot installation of ``registration_id`` in workspace ``team_id``."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from langflow.services.database.models.connection.model import Connection
    from langflow.services.database.models.connection.oauth import ConnectionOAuth
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        row = Connection(
            provider_key="slack",
            name=name or f"slack_{uuid4().hex[:8]}",
            display_name="Slack",
            ownership_mode=ownership_mode,
            owner_id=None if ownership_mode == "instance" else owner_id,
            status=status,
            allow_non_interactive=True,
            granted_scopes=["chat:write", "channels:history"],
            executing_identity={"identity": "bot", "account": {"id": BOT_USER_ID, "tenant_id": team_id}},
        )
        session.add(row)
        await session.flush()
        session.add(
            ConnectionOAuth(
                connection_id=row.id,
                user_id=owner_id,
                registration_id=registration_id,
                config_digest="0" * 64,
                scopes=["chat:write"],
                expires_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()
        return row.id


async def arm(
    flow_id,
    owner_id,
    connection_id,
    *,
    kind: str = "slack.message",
    mechanism: str = "slack.events_api",
    state: str = "active",
    config: dict[str, Any] | None = None,
    provider_state: dict[str, Any] | None = None,
):
    """An armed Slack trigger, as reconciliation would write it."""
    from uuid import uuid4

    from langflow.services.database.models.trigger.model import Trigger
    from langflow.services.deps import session_scope
    from langflow.services.triggers.providers.slack.config import normalize_slack_config

    stored = normalize_slack_config(kind, dict(config or {}))
    stored["mechanism_id"] = mechanism
    async with session_scope() as session:
        row = Trigger(
            flow_id=flow_id,
            user_id=owner_id,
            name=kind,
            kind=kind,
            provider="slack",
            node_id=f"{kind}-{uuid4().hex[:6]}",
            connection_id=connection_id,
            config=stored,
            provider_state=dict(provider_state or {}),
            state=state,
            concurrency_limit=1,
            max_attempts=3,
        )
        session.add(row)
        await session.flush()
        return row.id


async def events_for(trigger_id):
    from langflow.services.database.models.trigger.model import TriggerEvent
    from langflow.services.deps import session_scope
    from sqlmodel import select

    async with session_scope() as session:
        return list((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all())


APP_TOKEN = "xapp-1-A0APP00001-1111-testtoken"  # noqa: S105 - test fixture  # pragma: allowlist secret


async def make_app_token_connection(
    owner_id,
    *,
    token: str = APP_TOKEN,
    status: str = "ready",
    allow_non_interactive: bool = True,
    name: str | None = None,
):
    """A manually entered app-level token connection, as Socket Mode needs."""
    import json as _json
    from uuid import uuid4

    from langflow.services.auth.utils import encrypt_api_key
    from langflow.services.database.models.connection.model import Connection, ConnectionSecret
    from langflow.services.deps import session_scope

    payload = _json.dumps({"version": 1, "access_token": token, "token_type": "Bearer"})
    async with session_scope() as session:
        row = Connection(
            provider_key="slack",
            name=name or f"slack_app_{uuid4().hex[:8]}",
            display_name="Slack app-level token",
            ownership_mode="user",
            owner_id=owner_id,
            status=status,
            allow_non_interactive=allow_non_interactive,
            granted_scopes=["connections:write"],
            executing_identity={"identity": "bot"},
        )
        session.add(row)
        await session.flush()
        session.add(ConnectionSecret(connection_id=row.id, encrypted_payload=encrypt_api_key(payload)))
        await session.flush()
        return row.id
