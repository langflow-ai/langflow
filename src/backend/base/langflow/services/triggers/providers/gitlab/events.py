"""Verify Standard Webhooks signatures before interpreting GitLab events."""

import base64
import hashlib
import hmac
import json
import re
import time

from langflow.services.triggers.ingress.verifiers import IngressRejected, Verified
from langflow.services.triggers.providers.gitlab.config import ACTIONS

MAX_EVENT_BYTES = 1024 * 1024


def signing_key(secret):
    return hmac.new(secret.encode(), b"langflow.gitlab.webhook.v1", hashlib.sha256).digest()


def signing_token(secret):
    return "whsec_" + base64.b64encode(signing_key(secret)).decode()


def reject(reason):
    raise IngressRejected(reason)


def verify(request, secrets, *, tolerance_s):
    if (
        request.provider != "gitlab"
        or request.method != "POST"
        or len(request.body) > MAX_EVENT_BYTES
        or not secrets.signing_secret
    ):
        reject("bad_payload")
    message_id = request.header("webhook-id") or ""
    timestamp = request.header("webhook-timestamp") or ""
    signatures = request.header("webhook-signature") or ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", message_id) or not re.fullmatch(r"[0-9]{1,12}", timestamp):
        reject("bad_signature")
    if abs(time.time() - int(timestamp)) > tolerance_s:
        reject("stale_timestamp")
    message = message_id.encode() + b"." + timestamp.encode() + b"." + request.body
    expected = b"v1," + base64.b64encode(
        hmac.new(signing_key(secrets.signing_secret), message, hashlib.sha256).digest()
    )
    if not any(
        hmac.compare_digest(expected, sig.encode("utf-8", "surrogatepass")) for sig in signatures.split(" ")[:10]
    ):
        reject("bad_signature")
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        reject("bad_payload")
    if not isinstance(payload, dict):
        reject("bad_payload")
    project = payload.get("project")
    config = secrets.target_config
    if (
        not isinstance(project, dict)
        or type(project.get("id")) is not int
        or str(project["id"]) != secrets.resource_id
        or project["id"] != config.get("project_id")
    ):
        reject("bad_project")
    kind = secrets.target_kind
    expected_kind = {"gitlab.issue": "issue", "gitlab.merge_request": "merge_request"}.get(kind)
    if kind not in ACTIONS or payload.get("object_kind") != expected_kind:
        reject("unsupported_event")
    item = payload.get("object_attributes")
    user = payload.get("user")
    if (
        not isinstance(item, dict)
        or type(item.get("id")) is not int
        or type(item.get("iid")) is not int
        or item["id"] < 1
        or item["iid"] < 1
        or not isinstance(user, dict)
        or type(user.get("id")) is not int
    ):
        reject("bad_payload")
    action = item.get("action")
    if not isinstance(action, str) or action not in ACTIONS[kind]:
        reject("unsupported_action")
    if kind == "gitlab.issue" and item.get("project_id") != project["id"]:
        reject("bad_project")
    if kind == "gitlab.issue" and item.get("confidential", False):
        return Verified(handshake="")
    if kind == "gitlab.merge_request" and item.get("target_project_id") != project["id"]:
        reject("bad_project")
    if (
        action not in config.get("actions", [])
        or (str(user["id"]) == secrets.channel_id and not config.get("include_self_events", False))
        or (user.get("bot") is True and not config.get("include_bot_events", False))
    ):
        return Verified(handshake="")
    allowed = {
        "id",
        "iid",
        "title",
        "description",
        "state",
        "action",
        "created_at",
        "updated_at",
        "source_branch",
        "target_branch",
        "source_project_id",
        "target_project_id",
        "last_commit",
    }
    item = {key: value for key, value in item.items() if key in allowed}
    if isinstance(item.get("last_commit"), dict):
        item["last_commit"] = {
            key: value for key, value in item["last_commit"].items() if key in {"id", "timestamp", "message"}
        }
    # Delivery headers never determine identity. Identical signed bodies collapse across delivery retries.
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    return Verified(
        dedupe_suffix=f"gitlab:{digest}",
        payload={
            "provider": "gitlab",
            "event": expected_kind,
            "action": action,
            "project": {key: value for key, value in project.items() if key in {"id", "name", "path_with_namespace"}},
            "object_attributes": item,
            "user": {key: value for key, value in user.items() if key in {"id", "username", "name", "bot"}},
        },
    )
