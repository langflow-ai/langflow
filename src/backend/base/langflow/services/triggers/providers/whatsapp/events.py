"""Verify signed raw WhatsApp batches and retain only normalized safe fields."""

from __future__ import annotations

import hashlib
import hmac
import json
import re

from lfx_whatsapp._client import redact

from langflow.services.triggers.ingress.verifiers import (
    IngressRejected,
    IngressRequest,
    IngressSecrets,
    Verified,
    state_digest,
)

_MESSAGE_ID = re.compile(r"[A-Za-z0-9_.:+/=-]{1,512}\Z")
_USER = re.compile(r"[1-9][0-9]{6,14}\Z")
MAX_BODY = 1024 * 1024
MAX_ITEMS = 256


MAX_VERIFY_TOKEN = 1024
MAX_TEXT = 4096

_DELIVERY_ERRORS = {
    131026: "WhatsApp could not deliver this message. Check that the recipient uses WhatsApp and can receive messages.",
    131047: "The conversation's 24-hour reply window closed. Send an approved template to start a new conversation.",
    130429: "WhatsApp's sending rate limit was reached. Wait before sending again.",
    131048: "WhatsApp restricted this message because of the business account's messaging quality limits.",
    131049: "WhatsApp did not deliver this message under its recipient eligibility limits.",
}


def _delivery_failure(row: dict) -> dict:
    errors = row.get("errors")
    code = None
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, dict) and type(error.get("code")) is int:
                code = error["code"]
                break
    result = {
        "delivery_error": _DELIVERY_ERRORS.get(
            code, "WhatsApp could not deliver this message. Check recipient and account eligibility."
        )
    }
    if code is not None:
        result["delivery_error_code"] = code
    return result


def verify_get(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:  # noqa: ARG001
    supplied = request.query.get("hub.verify_token", "")
    challenge = request.query.get("hub.challenge", "")
    if (
        request.provider != "whatsapp"
        or request.method != "GET"
        or request.body
        or request.query.get("hub.mode") != "subscribe"
        or not secrets.verification_token_digest
        or not isinstance(supplied, str)
        or len(supplied) > MAX_VERIFY_TOKEN
        or not hmac.compare_digest(state_digest(supplied), secrets.verification_token_digest)
        or not isinstance(challenge, str)
        or not re.fullmatch(r"[0-9]{1,128}", challenge)
    ):
        msg = "bad_challenge"
        raise IngressRejected(msg)
    return Verified(handshake=challenge)


def verify(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:  # noqa: ARG001
    signature = request.header("x-hub-signature-256") or ""
    if (
        request.provider != "whatsapp"
        or request.method != "POST"
        or len(request.body) > MAX_BODY
        or not secrets.signing_secret
        or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature)
    ):
        msg = "bad_signature"
        raise IngressRejected(msg)
    expected = "sha256=" + hmac.new(secrets.signing_secret.encode(), request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        msg = "bad_signature"
        raise IngressRejected(msg)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        msg = "bad_payload"
        raise IngressRejected(msg) from None
    if (
        not isinstance(payload, dict)
        or payload.get("object") != "whatsapp_business_account"
        or not isinstance(payload.get("entry"), list)
    ):
        msg = "bad_payload"
        raise IngressRejected(msg)
    items = []
    count = 0
    for entry in payload["entry"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("changes"), list):
            msg = "bad_payload"
            raise IngressRejected(msg)
        if entry.get("id") != secrets.resource_id:
            continue
        for change in entry["changes"]:
            if not isinstance(change, dict):
                msg = "bad_payload"
                raise IngressRejected(msg)
            if change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict) or value.get("messaging_product") != "whatsapp":
                msg = "bad_payload"
                raise IngressRejected(msg)
            metadata = value.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != secrets.channel_id:
                continue
            for field_name, event in (("messages", "message"), ("statuses", "status")):
                rows = value.get(field_name, [])
                if not isinstance(rows, list):
                    msg = "bad_payload"
                    raise IngressRejected(msg)
                for row in rows:
                    count += 1
                    if count > MAX_ITEMS or not isinstance(row, dict):
                        msg = "bad_payload"
                        raise IngressRejected(msg)
                    message_id = row.get("id")
                    timestamp = row.get("timestamp")
                    sender = row.get("from" if event == "message" else "recipient_id")
                    if (
                        not isinstance(message_id, str)
                        or not _MESSAGE_ID.fullmatch(message_id)
                        or not isinstance(timestamp, str)
                        or not re.fullmatch(r"[0-9]{1,12}", timestamp)
                    ):
                        msg = "bad_payload"
                        raise IngressRejected(msg)
                    if not isinstance(sender, str) or not _USER.fullmatch(sender):
                        continue
                    data = {
                        "provider": "whatsapp",
                        "event": event,
                        "waba_id": secrets.resource_id,
                        "phone_id": secrets.channel_id,
                        "message_id": message_id,
                        "sender": sender,
                        "timestamp": timestamp,
                        "session_key": f"whatsapp:{secrets.resource_id}:{secrets.channel_id}:{sender}",
                    }
                    if event == "message":
                        if not secrets.target_config.get("receive_messages", True) or row.get("type") != "text":
                            continue
                        text = row.get("text")
                        if (
                            not isinstance(text, dict)
                            or not isinstance(text.get("body"), str)
                            or len(text["body"]) > MAX_TEXT
                        ):
                            msg = "bad_payload"
                            raise IngressRejected(msg)
                        data["text"] = redact(text["body"], secrets.signing_secret)
                        version = "message"
                    else:
                        if not secrets.target_config.get("receive_statuses", False):
                            continue
                        status = row.get("status")
                        if not isinstance(status, str) or status not in {
                            "sent",
                            "delivered",
                            "read",
                            "failed",
                            "deleted",
                        }:
                            continue
                        data["status"] = status
                        if status == "failed":
                            data.update(_delivery_failure(row))
                        version = f"{status}:{timestamp}"
                    filtered = bool(
                        secrets.target_config.get("allowed_senders")
                        and sender not in secrets.target_config["allowed_senders"]
                    )
                    if filtered:
                        data.pop("text", None)
                    items.append(
                        {
                            "provider": "whatsapp",
                            "resource": secrets.channel_id,
                            "id": message_id,
                            "version": version,
                            "data": data,
                            "session_key": data["session_key"],
                            **({"skip_reason": "sender_not_allowed"} if filtered else {}),
                        }
                    )
    return Verified(
        dedupe_suffix=hashlib.sha256(request.body).hexdigest(),
        source_items=tuple(items),
        response_body="",
        response_media_type="text/plain",
        response_status=200,
    )
