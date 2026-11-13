"""Check every value locally before any request is made.

A refused value raises ``TurboNotifyError`` with a code that names the field, so the
person (or the agent in Tool mode) learns what to change without a round trip.
"""

from __future__ import annotations

import ipaddress
import math
import re
import socket
from typing import Any
from urllib.parse import urlsplit

from lfx_turbo_notify._client import TurboNotifyError

MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024
MAX_FILENAME_LENGTH = 255
MAX_URL_LENGTH = 2083
MAX_CURSOR_LENGTH = 2048
MAX_PAGE_SIZE = 200
MAX_IDEMPOTENCY_KEY_LENGTH = 255

DIRECTIONS = ("any", "inbound", "outbound")
MEDIA_TYPES = ("image", "video", "audio", "document", "sticker")
CAPTION_MEDIA_TYPES = frozenset({"image", "video", "document"})

_PHONE = re.compile(r"\+[1-9][0-9]{6,14}")
_PHONE_SEPARATORS = re.compile(r"[\s\-()]")
_MESSAGE_ID = re.compile(r"msg_[0-9a-f]{32}")
_CONTACT_ID = re.compile(r"ct_[0-9a-f]{32}")
_GROUP_ID = re.compile(r"grp_[0-9a-f]{32}")
_IDEMPOTENCY_KEY = re.compile(r"[\x20-\x7e]+")


def raw_text(value: Any) -> str:
    """Return the text of an input value exactly as written, or an empty string when it holds none.

    A value connected from another component may arrive as a ``Message`` or ``Data``
    object; those carry their text in ``.text``.
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    text = getattr(value, "text", None)
    return text if isinstance(text, str) else ""


def as_text(value: Any) -> str:
    """Return the text of an input value without surrounding white space."""
    return raw_text(value).strip()


def require_text(value: Any, *, field: str, code: str, maximum: int) -> str:
    """Return a text of at most ``maximum`` characters, exactly as written.

    The text must not be blank, but it is checked with its white space trimmed only to
    decide that: what the person wrote is what is sent, and the limit counts what is sent.
    """
    text = raw_text(value)
    if not text.strip():
        msg = f"{field} is empty. Provide the text to send."
        raise TurboNotifyError(msg, code)
    if len(text) > maximum:
        msg = f"{field} is too long ({len(text)} characters, the limit is {maximum}). Shorten it."
        raise TurboNotifyError(msg, code)
    return text


def optional_text(value: Any, *, field: str, code: str, maximum: int) -> str | None:
    """Return the text exactly as written, or ``None`` when the input is blank."""
    if not raw_text(value).strip():
        return None
    return require_text(value, field=field, code=code, maximum=maximum)


def clean_phone(value: Any) -> str:
    """Return an E.164 number: ``+``, then 7 to 15 digits, after spaces, dashes and parentheses are removed."""
    cleaned = _PHONE_SEPARATORS.sub("", as_text(value))
    if not _PHONE.fullmatch(cleaned):
        msg = (
            "Phone Number must be an international number: + and the country code, then 7 to 15 digits in all, "
            "for example +12025550123."
        )
        raise TurboNotifyError(msg, "invalid_phone_number")
    return cleaned


def _identifier(value: Any, *, pattern: re.Pattern[str], prefix: str, field: str, code: str) -> str:
    text = as_text(value)
    if not pattern.fullmatch(text):
        msg = f"{field} is not a valid ID. It is {prefix}_ followed by 32 lowercase letters and digits."
        raise TurboNotifyError(msg, code)
    return text


def contact_id(value: Any) -> str:
    """Return a Turbo Notify contact id (``ct_`` and 32 hex characters)."""
    return _identifier(value, pattern=_CONTACT_ID, prefix="ct", field="Contact ID", code="invalid_contact_id")


def group_id(value: Any) -> str:
    """Return a Turbo Notify group id (``grp_`` and 32 hex characters)."""
    return _identifier(value, pattern=_GROUP_ID, prefix="grp", field="Group ID", code="invalid_group_id")


def message_id(value: Any) -> str:
    """Return a Turbo Notify message id (``msg_`` and 32 hex characters)."""
    return _identifier(value, pattern=_MESSAGE_ID, prefix="msg", field="Message ID", code="invalid_message_id")


def recipient(*, phone: Any, contact: Any, group: Any) -> dict[str, str]:
    """Return the ``to`` object. Exactly one of phone, contact id or group id must be filled in."""
    filled = [name for name, value in (("phone", phone), ("contact", contact), ("group", group)) if as_text(value)]
    if not filled:
        msg = "Choose who receives the message: fill in one of Phone Number, Contact ID or Group ID."
        raise TurboNotifyError(msg, "invalid_recipient")
    if len(filled) > 1:
        msg = "Fill in only one of Phone Number, Contact ID or Group ID. A message has one recipient."
        raise TurboNotifyError(msg, "invalid_recipient")
    if filled[0] == "phone":
        return {"number": clean_phone(phone)}
    if filled[0] == "contact":
        return {"contact_id": contact_id(contact)}
    return {"group_id": group_id(group)}


def _is_local_name(host: str) -> bool:
    name = host.rstrip(".").lower()
    return name == "localhost" or name.endswith(".localhost")


def _literal_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return the address a literal IP host stands for, including the short forms a resolver accepts.

    ``127.1``, ``0x7f.0.0.1`` and ``2130706433`` all mean 127.0.0.1 to the system resolver.
    A name that is not an address returns ``None``.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError:
        return None


def _is_non_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
        or not address.is_global
    )


def http_url(value: Any, *, field: str, code: str) -> str:
    """Return a public ``http://`` or ``https://`` address.

    A host that is written as ``localhost`` or as a loopback, private, link-local, unspecified or
    otherwise non-public IP address (IPv4 or IPv6) is refused, because Turbo Notify downloads the
    file from this address and a local address is never a public file.

    Only the written host is checked. The check does not resolve DNS: a name that resolves to a
    private address is not covered here and must be refused by whoever fetches the file.
    """
    text = as_text(value)
    if not text or len(text) > MAX_URL_LENGTH or re.search(r"\s", text):
        msg = (
            f"{field} must be a full web address of at most {MAX_URL_LENGTH} characters, "
            "for example https://example.com/file.jpg."
        )
        raise TurboNotifyError(msg, code)
    parts = urlsplit(text)
    host = parts.hostname
    if parts.scheme not in {"http", "https"} or not host:
        msg = f"{field} must start with http:// or https:// and name a host, for example https://example.com/file.jpg."
        raise TurboNotifyError(msg, code)
    address = _literal_address(host)
    if _is_local_name(host) or (address is not None and _is_non_public(address)):
        msg = (
            f"{field} points to a local or private address (localhost, loopback, private, link-local or "
            "unspecified). Use a public address that Turbo Notify can download from."
        )
        raise TurboNotifyError(msg, code)
    return text


def media_content(*, media_type: Any, media_url: Any, caption: Any = None, filename: Any = None) -> dict[str, str]:
    """Return the ``content`` object of a media message.

    The caption goes with an image, video or document. The file name goes with a document.
    """
    kind = as_text(media_type).lower()
    if kind not in MEDIA_TYPES:
        msg = f"Media Type must be one of {', '.join(MEDIA_TYPES)}."
        raise TurboNotifyError(msg, "invalid_media_type")
    content = {f"{kind}_url": http_url(media_url, field="Media URL", code="invalid_media_url")}
    text = optional_text(caption, field="Caption", code="invalid_caption", maximum=MAX_CAPTION_LENGTH)
    if text is not None:
        if kind not in CAPTION_MEDIA_TYPES:
            msg = "An audio file or a sticker takes no caption. Leave Caption empty."
            raise TurboNotifyError(msg, "invalid_caption")
        content["caption"] = text
    name = optional_text(as_text(filename), field="File Name", code="invalid_filename", maximum=MAX_FILENAME_LENGTH)
    if name is not None:
        if kind != "document":
            msg = "Only a document takes a file name. Leave File Name empty."
            raise TurboNotifyError(msg, "invalid_filename")
        content["filename"] = name
    return content


def page_size(value: Any, *, default: int) -> int:
    """Return a page size from 1 to 200."""
    if value is None or value == "":
        return default
    number: float | None = None
    if not isinstance(value, bool) and isinstance(value, int | float | str):
        try:
            number = float(value)
        except (ValueError, OverflowError):
            number = None
    if number is None or not math.isfinite(number) or number != int(number) or not 1 <= number <= MAX_PAGE_SIZE:
        msg = f"Limit must be a whole number from 1 to {MAX_PAGE_SIZE}."
        raise TurboNotifyError(msg, "invalid_limit")
    return int(number)


def direction(value: Any) -> str | None:
    """Return ``inbound`` or ``outbound``, or ``None`` for both."""
    text = as_text(value).lower() or "any"
    if text not in DIRECTIONS:
        msg = "Direction must be any, inbound (received) or outbound (sent)."
        raise TurboNotifyError(msg, "invalid_direction")
    return None if text == "any" else text


def cursor(value: Any) -> str | None:
    """Return the opaque page cursor, or ``None`` for the first page."""
    text = as_text(value)
    if not text:
        return None
    if len(text) > MAX_CURSOR_LENGTH or re.search(r"\s", text):
        msg = "Cursor is not valid. Pass back the cursor value of the previous page unchanged."
        raise TurboNotifyError(msg, "invalid_cursor")
    return text


def idempotency_key(value: Any) -> str | None:
    """Return the ``Idempotency-Key`` value, or ``None`` when the input is blank.

    The key has 1 to 255 printable ASCII characters. Control characters (tab, new line) are refused.
    """
    key = as_text(value)
    if not key:
        return None
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH or not _IDEMPOTENCY_KEY.fullmatch(key):
        msg = (
            f"Idempotency Key must have 1 to {MAX_IDEMPOTENCY_KEY_LENGTH} printable characters (letters, digits, "
            "punctuation and spaces, without line breaks or tabs), for example order-4711."
        )
        raise TurboNotifyError(msg, "invalid_idempotency_key")
    return key
