"""Verify GitHub's signed raw payload before interpreting event data."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from uuid import UUID

from langflow.services.triggers.ingress.verifiers import IngressRejected, IngressRequest, IngressSecrets, Verified
from langflow.services.triggers.providers.github.config import ACTIONS

MAX_EVENT_BYTES = 1024 * 1024
_SIGNATURE = re.compile(r"sha256=[0-9a-f]{64}\Z")
_EVENT = {"github.issue": "issues", "github.pull_request": "pull_request"}
_OBJECT = {"github.issue": "issue", "github.pull_request": "pull_request"}


def verify(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:  # noqa: ARG001
    if request.provider != "github" or len(request.body) > MAX_EVENT_BYTES:
        msg = "bad_payload"
        raise IngressRejected(msg)
    signature = request.header("x-hub-signature-256") or ""
    if not secrets.signing_secret or not _SIGNATURE.fullmatch(signature):
        msg = "bad_signature"
        raise IngressRejected(msg)
    expected = "sha256=" + hmac.new(secrets.signing_secret.encode(), request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        msg = "bad_signature"
        raise IngressRejected(msg)
    try:
        delivery = str(UUID(request.header("x-github-delivery") or ""))
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        msg = "bad_payload"
        raise IngressRejected(msg) from None
    if not isinstance(payload, dict):
        msg = "bad_payload"
        raise IngressRejected(msg)
    repository = payload.get("repository")
    config = secrets.target_config
    if (
        not isinstance(repository, dict)
        or not isinstance(repository.get("full_name"), str)
        or repository["full_name"].lower() != config.get("repository")
    ):
        msg = "bad_repository"
        raise IngressRejected(msg)
    if secrets.resource_id and str(repository.get("id")) != secrets.resource_id:
        msg = "bad_repository"
        raise IngressRejected(msg)
    event = request.header("x-github-event")
    if event == "ping":
        return Verified(handshake="")
    kind = secrets.target_kind
    if kind not in _EVENT or event != _EVENT[kind]:
        msg = "unsupported_event"
        raise IngressRejected(msg)
    action = payload.get("action")
    if not isinstance(action, str) or action not in ACTIONS[kind]:
        msg = "unsupported_action"
        raise IngressRejected(msg)
    if action not in config.get("actions", []):
        return Verified(handshake="")
    item = payload.get(_OBJECT[kind])
    if (
        not isinstance(item, dict)
        or type(item.get("number")) is not int
        or item["number"] < 1
        or type(item.get("id")) is not int
    ):
        msg = "bad_payload"
        raise IngressRejected(msg)
    if kind == "github.issue" and "pull_request" in item:
        msg = "bad_payload"
        raise IngressRejected(msg)
    sender = payload.get("sender")
    if isinstance(sender, dict) and sender.get("type") == "Bot" and not config.get("include_bot_events", False):
        return Verified(handshake="")
    # The delivery header is unsigned. Body identity also collapses a replay with a forged header.
    digest = hashlib.sha256(request.body).hexdigest()
    return Verified(
        dedupe_suffix=f"github:{digest}",
        payload={
            "provider": "github",
            "event": event,
            "action": action,
            "repository": repository,
            _OBJECT[kind]: item,
            "sender": payload.get("sender"),
            "delivery_id": delivery,
        },
    )
