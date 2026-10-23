# Test fixtures shared by every test module in this package.
#
# `FakeSaltClient` stands in for `saltapp.client.SaltClient` -- no httpx
# transport, no network, just the same method surface the components call,
# recording every call so a test can assert on it. `signed_update_row`
# builds a socket-mode "update" row with a REAL HMAC signature (the exact
# scheme `saltapp.webhook.verify_signature` checks), so tests exercise the
# actual signature-verification path in `_salt_common.check_for_event`
# rather than mocking it away -- matching saltapp-python's own testing
# philosophy (saltapp-langflow AGENTS.md: "None of them stub the thing they claim to test").
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

WEBHOOK_SECRET = "test-webhook-secret"  # noqa: S105  # pragma: allowlist secret


class FakeSaltClient:
    """A drop-in stand-in for `saltapp.client.SaltClient`.

    Every method a component might call is here; each records its call args in `.calls` and returns whatever
    `self.<method>_response` (or a per-call queue) is set to, so a test can script a sequence of poll rounds.
    """

    def __init__(self, host: str = "https://example.test") -> None:
        self.host = host
        self.closed = False
        self.calls: list[tuple[str, tuple, dict]] = []

        self.who_am_i_response: dict[str, Any] = {"agent_id": "agent-self", "webhook_secret": WEBHOOK_SECRET}
        self.chat_members_response: list[dict[str, Any]] = []
        self.get_chat_response: dict[str, Any] = {"session": {"encrypted": True, "users": []}, "messages": []}
        self.post_message_response: dict[str, Any] = {"id": "msg-1"}
        self.post_plain_message_response: dict[str, Any] = {"id": "msg-plain-1"}
        # The REAL POST /api/v1/cards response shape (salt-api 0.96.1): the
        # card's chat BUBBLE, not the card record -- `message_id` (the
        # bubble's own id) and `resource_id` (the card's own id, what GET/
        # PATCH /api/v1/cards/:id read and update), plus `resource` (the
        # card's own as_chat_resource payload, which separately carries an
        # `id` matching `resource_id`). There is NO top-level `id` here --
        # a earlier version of this fake modeled `{"id": "card-1"}`, which
        # is not a shape salt-api ever actually returns, and hid a real
        # `card["id"]` read bug in ask_human.py for as long as that fake
        # was in place. See _salt_common.card_id_from_post.
        self.post_card_response: dict[str, Any] = {
            "message_id": "msg-card-1",
            "resource_id": "card-1",
            "resource": {"id": "card-1", "card_type": "blocks", "state": {}, "owner": {}},
        }
        # The REAL GET /api/v1/cards/:id response shape (salt-api 0.96.0):
        # {id, state, owner_id, interactions: [...]}, interactions newest
        # first -- see CardInteraction#as_json_for_owner. Consumed via
        # FakeSaltClient._request (below), matching how
        # _salt_common.get_card actually reaches SaltClient -- there is no
        # public get_card method on the real SDK either, so faking a
        # get_card METHOD here would test a call shape the real code never
        # makes.
        self.get_card_response: dict[str, Any] = {
            "id": "card-1",
            "state": {},
            "owner_id": "agent-self",
            "interactions": [],
        }
        self.request_payment_response: dict[str, Any] = {"id": "req-1"}
        self.get_chat_subscription_response: dict[str, Any] = {"chat_id": "chat-1", "mode": "addressed", "keywords": []}
        self.set_chat_subscription_response: dict[str, Any] = {"chat_id": "chat-1", "mode": "addressed", "keywords": []}
        self.clear_chat_subscription_response: dict[str, Any] = {
            "chat_id": "chat-1",
            "mode": "addressed",
            "keywords": [],
        }
        # A list of "rounds": each call to get_agent_updates pops the next
        # round (or repeats the last one once the list is exhausted).
        self.update_rounds: list[dict[str, Any]] = [{"updates": [], "cursor": 0}]
        self._round_index = 0
        # A raised exception (or a callable returning one) that the NEXT
        # `_request` call raises instead of returning `get_card_response` --
        # lets a test script a 429 (or any other SaltApiError) from the
        # card-read path without needing a second fake method.
        self.get_card_error: Exception | None = None

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    def close(self) -> None:
        self.closed = True

    def who_am_i(self, api_key: str) -> dict[str, Any]:
        self._record("who_am_i", api_key)
        return self.who_am_i_response

    def get_chat_members(self, api_key: str, chat_id: str) -> list[dict[str, Any]]:
        self._record("get_chat_members", api_key, chat_id)
        return self.chat_members_response

    def get_chat(self, api_key: str, chat_id: str, *, last: Any = None) -> dict[str, Any]:
        self._record("get_chat", api_key, chat_id, last=last)
        return self.get_chat_response

    def post_message(
        self,
        api_key: str,
        chat_id: str,
        message: str,
        sender_message: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._record("post_message", api_key, chat_id, message, sender_message, **kwargs)
        return self.post_message_response

    def post_plain_message(self, api_key: str, chat_id: str, message: str, **kwargs: Any) -> dict[str, Any]:
        self._record("post_plain_message", api_key, chat_id, message, **kwargs)
        return self.post_plain_message_response

    def post_card(self, api_key: str, chat_id: str, blocks: list[dict[str, Any]], text: str) -> dict[str, Any]:
        self._record("post_card", api_key, chat_id, blocks, text)
        return self.post_card_response

    def request_payment(self, api_key: str, **kwargs: Any) -> dict[str, Any]:
        self._record("request_payment", api_key, **kwargs)
        return self.request_payment_response

    def get_chat_subscription(self, api_key: str, chat_id: str) -> dict[str, Any]:
        self._record("get_chat_subscription", api_key, chat_id)
        return self.get_chat_subscription_response

    def set_chat_subscription(
        self, api_key: str, chat_id: str, mode: str, *, keywords: list[str] | None = None
    ) -> dict[str, Any]:
        self._record("set_chat_subscription", api_key, chat_id, mode, keywords=keywords)
        return self.set_chat_subscription_response

    def clear_chat_subscription(self, api_key: str, chat_id: str) -> dict[str, Any]:
        self._record("clear_chat_subscription", api_key, chat_id)
        return self.clear_chat_subscription_response

    def get_agent_updates(self, api_key: str, *, after: int = 0, timeout: int = 2, limit: int = 100) -> dict[str, Any]:
        self._record("get_agent_updates", api_key, after=after, timeout=timeout, limit=limit)
        index = min(self._round_index, len(self.update_rounds) - 1)
        round_ = self.update_rounds[index]
        self._round_index += 1
        return round_

    def _request(self, method: str, path: str, api_key: str, json_body: Any = None, **kwargs: Any) -> Any:
        """Stands in for `saltapp.client.SaltClient._request` -- the one real method `_salt_common.get_card`.

        calls (there is no public `get_card` on the real SDK either; see that function's own docstring for
        why). Only the one path this package's own code actually reaches through `_request` is wired up here:
        a card read. Anything else hitting this is a test writing a call this package's production code does
        not make.
        """
        self._record("_request", method, path, api_key, json_body=json_body, **kwargs)
        if method == "GET" and path.startswith("/api/v1/cards/"):
            if self.get_card_error is not None:
                raise self.get_card_error
            return self.get_card_response
        msg = f"FakeSaltClient._request has no fake response wired up for {method} {path}"
        raise AssertionError(msg)


def sign_body(body: dict[str, Any], secret: str = WEBHOOK_SECRET, *, timestamp: int | None = None) -> tuple[dict, str]:
    """The exact `X-Salt-Signature: t=..,v1=..` scheme saltapp.webhook checks.

    Returns (headers, raw_json_string) -- the raw string is what a test should also put in the update row's
    `body`, so the bytes hashed for the signature match the bytes `_salt_common.check_for_event` re-hashes.
    """
    ts = timestamp if timestamp is not None else int(time.time())
    raw = json.dumps(body)
    signed_string = f"{ts}.".encode() + raw.encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_string, hashlib.sha256).hexdigest()
    headers = {"X-Salt-Signature": f"t={ts},v1={digest}"}
    return headers, raw


def signed_update_row(
    row_id: int,
    body: dict[str, Any],
    *,
    secret: str = WEBHOOK_SECRET,
    delivery_id: str | None = None,
    agent_id: str = "agent-self",
) -> dict[str, Any]:
    """One `GET /api/v1/agent/updates` row, correctly signed."""
    headers, raw = sign_body(body, secret)
    headers["X-Salt-Agent-Id"] = agent_id
    if delivery_id is not None:
        headers["X-Salt-Delivery-Id"] = delivery_id
    return {
        "id": row_id,
        "headers": headers,
        "body": raw,
        "delivery_id": delivery_id,
        "created_at": "2026-09-18T00:00:00Z",
    }


def card_interaction(
    interaction_id: int,
    *,
    action_id: str,
    user_id: str,
    created_at: str = "2026-09-26T00:00:00Z",
    transfer_request_id: str | None = None,
    transfer_request_status: str | None = None,
) -> dict[str, Any]:
    """One row of `GET /api/v1/cards/:id`'s `interactions` array, exactly as.

    `CardInteraction#as_json_for_owner` shapes it: `{id, user_id, action_id, value, created_at}`, plus
    `transfer_request_id`/ `transfer_request_status` only when the tap produced a real TransferRequest (a
    "pay" button -- Salt Ask Human never posts one of those, but the shape is modeled here for
    completeness/parity with salt-mcp's and saltapp-agentkit's identical fakes). Callers build a LIST of
    these, newest first (matching the real route's `order( created_at: :desc, id: :desc)`), and set it as
    `FakeSaltClient.get_card_response["interactions"]`.
    """
    row: dict[str, Any] = {
        "id": interaction_id,
        "user_id": user_id,
        "action_id": action_id,
        "value": None,
        "created_at": created_at,
    }
    if transfer_request_id is not None:
        row["transfer_request_id"] = transfer_request_id
        row["transfer_request_status"] = transfer_request_status
    return row


def chat_member(user_id: str, *, username: str, account_type: str = "User") -> dict[str, Any]:
    """One row of a chat's member list, the fields Salt Ask Human's tap classification actually reads.

    (`id`, `account_type`, `username`) -- salt-api's own `SAFE_USER_FIELDS` carries more (display_name,
    public_key, ...), trimmed here to what this package's tests need.
    """
    return {"id": user_id, "username": username, "account_type": account_type}
