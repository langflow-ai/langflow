"""Fixed deployment identity and bounded Confluence page targets."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from lfx.integrations.errors import InvalidRequestError

API_ORIGIN = "https://api.atlassian.com"
READ = "read:page:confluence"
WRITE = "write:page:confluence"
USER = "read:confluence-user"
SCOPES = frozenset({READ, WRITE, USER, "offline_access"})
PAGE_SIZE = 100
MAX_PAGES = 50
MAX_ITEMS = 5000
MAX_CURSOR = 8192
MAX_VERSION = 2147483647
MAX_SPACES = 100


def invalid(message):
    return InvalidRequestError(message, provider="confluence")


def cloud_id():
    value = os.environ.get("LANGFLOW_CONFLUENCE_CLOUD_ID", "")
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        msg = "Configure one canonical lowercase Confluence Cloud site UUID on the server."
        raise invalid(msg) from None
    return value


def numeric_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        msg = "Use a positive Confluence numeric ID within 19 digits."
        raise invalid(msg)
    return value


def approved_space(value):
    value = numeric_id(value)
    configured = os.environ.get("LANGFLOW_CONFLUENCE_SPACE_IDS", "").split(",")
    if not 1 <= len(configured) <= MAX_SPACES or any(
        not re.fullmatch(r"[1-9][0-9]{0,18}", item) for item in configured
    ):
        msg = "Configure one to 100 approved Confluence space IDs as a comma-separated server setting."
        raise invalid(msg)
    if value not in configured:
        msg = "This Confluence space is not approved by the deployment operator."
        raise invalid(msg)
    return value


def text(value, *, maximum=32768, required=True):
    try:
        valid = (
            isinstance(value, str) and len(value.encode("utf-8")) <= maximum and (not required or bool(value.strip()))
        )
    except UnicodeEncodeError:
        valid = False
    if not valid:
        msg = "Provide text within the documented size limit."
        raise invalid(msg)
    return value


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (AttributeError, ValueError, TypeError, OverflowError):
        msg = "Confluence returned an invalid page timestamp."
        raise invalid(msg) from None


def page_data(value, *, space, identifier=None, include_body=False):
    if not isinstance(value, dict) or not isinstance(value.get("version"), dict):
        msg = "Confluence returned an invalid page."
        raise invalid(msg)
    page_id = numeric_id(value.get("id"))
    if value.get("spaceId") != approved_space(space) or (identifier is not None and page_id != identifier):
        msg = "Confluence returned a page outside the selected target."
        raise invalid(msg)
    version = value["version"].get("number")
    if type(version) is not int or not 1 <= version <= MAX_VERSION or value.get("status") != "current":
        msg = "Confluence returned an invalid current page version."
        raise invalid(msg)
    result = {
        "id": page_id,
        "space_id": space,
        "title": text(value.get("title"), maximum=4096),
        "created_at": timestamp(value.get("createdAt")).isoformat(),
        "updated_at": timestamp(value["version"].get("createdAt")).isoformat(),
        "version": version,
    }
    if include_body:
        body = value.get("body", {}).get("storage") if isinstance(value.get("body"), dict) else None
        if not isinstance(body, dict):
            msg = "Confluence returned no storage page body."
            raise invalid(msg)
        result["body_storage"] = text(body.get("value"), maximum=1048576, required=False)
    return result


def list_params(space, *, title="", cursor=""):
    result = {
        "space-id": approved_space(space),
        "status": "current",
        "sort": "id",
        "subtype": "page",
        "limit": PAGE_SIZE,
    }
    if title:
        result["title"] = text(title, maximum=255)
    if cursor:
        result["cursor"] = text(cursor, maximum=MAX_CURSOR)
    return result


def next_cursor(result):
    links = result.get("_links", {}) if isinstance(result, dict) else None
    if not isinstance(links, dict):
        msg = "Confluence returned malformed page links."
        raise invalid(msg)
    link = links.get("next")
    if link is None or link == "":
        return ""
    link = text(link, maximum=MAX_CURSOR + 4096)
    parts = urlsplit(link)
    allowed = {"/wiki/api/v2/pages", f"/ex/confluence/{cloud_id()}/wiki/api/v2/pages"}
    if (parts.scheme or parts.netloc) and f"{parts.scheme}://{parts.netloc}" != API_ORIGIN:
        msg = "Confluence returned an unsafe pagination origin."
        raise invalid(msg)
    if parts.path not in allowed or parts.fragment or parts.username or parts.password:
        msg = "Confluence returned an unrelated pagination resource."
        raise invalid(msg)
    try:
        pairs = parse_qsl(parts.query, strict_parsing=True, max_num_fields=12)
    except ValueError:
        msg = "Confluence returned malformed pagination parameters."
        raise invalid(msg) from None
    cursors = [value for key, value in pairs if key == "cursor"]
    if len(cursors) != 1:
        msg = "Confluence returned no unique pagination cursor."
        raise invalid(msg)
    # Rebuild every request from approved space and fixed filters. Never follow the provider URL.
    return text(cursors[0], maximum=MAX_CURSOR)


def page_list(result, *, space):
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("results"), list)
        or len(result["results"]) > PAGE_SIZE
    ):
        msg = "Confluence returned an invalid page list."
        raise invalid(msg)
    pages = [page_data(value, space=space) for value in result["results"]]
    if len({value["id"] for value in pages}) != len(pages):
        msg = "Confluence returned duplicate pages. Retry the complete snapshot."
        raise invalid(msg)
    return pages, next_cursor(result)
