"""Fixed deployment origin and bounded Table API input grammar."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlsplit

from lfx.integrations.errors import InvalidRequestError

PROVIDER = "servicenow"
READ_SCOPE = "langflow_table_read"
WRITE_SCOPE = "langflow_table_write"
TABLES = ("incident", "problem", "change_request")
READ_FIELDS = (
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "priority",
    "impact",
    "urgency",
    "assignment_group",
    "assigned_to",
    "active",
    "sys_created_on",
    "sys_updated_on",
    "sys_mod_count",
)
WRITE_FIELDS = frozenset(
    {
        "short_description",
        "description",
        "state",
        "impact",
        "urgency",
        "assignment_group",
        "assigned_to",
    }
)
_ID = re.compile(r"^[0-9a-f]{32}$")
_HOST = re.compile(r"^[a-z0-9][a-z0-9-]*\.service-now\.com$")
_MAX_LITERAL = 250
_MAX_FIELD = 4000


def invalid(message: str) -> InvalidRequestError:
    return InvalidRequestError(message, provider=PROVIDER)


def origin() -> str:
    raw = os.environ.get("LANGFLOW_SERVICENOW_ORIGIN", "")
    try:
        parts = urlsplit(raw)
        valid = (
            parts.scheme == "https"
            and _HOST.fullmatch(parts.netloc)
            and parts.path in {"", "/"}
            and not parts.query
            and not parts.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        msg = "Configure one HTTPS ServiceNow instance origin on the server."
        raise invalid(msg)
    return f"https://{parts.netloc}"


def table(value: Any) -> str:
    approved = os.environ.get("LANGFLOW_SERVICENOW_TABLES", "incident").split(",")
    if not isinstance(value, str) or value not in TABLES or value not in approved:
        msg = "Choose an approved incident, problem, or change_request table."
        raise invalid(msg)
    return value


def record_id(value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        msg = "Record ID must contain 32 lowercase hexadecimal characters."
        raise invalid(msg)
    return value


def literal(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_LITERAL
        or not re.fullmatch(r"[A-Za-z0-9 _.,@/-]+", value)
    ):
        msg = "Filter values must contain ordinary text without query operators or scripts."
        raise invalid(msg)
    return value


def fields(value: Any, *, create: bool = False) -> dict[str, Any]:
    data = value.data if hasattr(value, "data") else value
    if not isinstance(data, dict) or not data or not set(data) <= WRITE_FIELDS:
        msg = "Supply a nonempty object containing only approved writable fields."
        raise invalid(msg)
    clean = {}
    for key, item in data.items():
        if not isinstance(item, str) or len(item) > _MAX_FIELD or "\x00" in item:
            msg = "Writable fields must be strings of at most 4000 characters."
            raise invalid(msg)
        if key in {"assignment_group", "assigned_to"} and item:
            record_id(item)
        if key in {"state", "impact", "urgency"} and not re.fullmatch(r"-?[0-9]{1,3}", item):
            msg = "State, impact, and urgency must be numeric choice values."
            raise invalid(msg)
        clean[key] = item
    if create and not clean.get("short_description", "").strip():
        msg = "Creating a ticket requires a short_description."
        raise invalid(msg)
    return clean


def result_record(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        msg = "ServiceNow returned an invalid record."
        raise invalid(msg)
    record_id(value.get("sys_id"))
    return {key: item for key, item in value.items() if key in READ_FIELDS and isinstance(item, str)}
