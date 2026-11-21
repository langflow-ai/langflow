"""Frozen scalar record surface shared by actions and source adapters."""

from __future__ import annotations

import math
import os
import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from lfx.integrations.errors import InvalidRequestError

MAX_FIELDS = 30
MAX_FIELD_LENGTH = 32_000
API_ROOT = "/services/data/v66.0"
SYSTEM_FIELDS = ("Id", "CreatedDate", "LastModifiedDate", "SystemModstamp")
FIELDS = {
    "Account": {"Name": str, "Description": str, "Phone": str, "Website": str, "Industry": str},
    "Contact": {"FirstName": str, "LastName": str, "Email": str, "Phone": str, "Title": str, "AccountId": str},
    "Lead": {"FirstName": str, "LastName": str, "Company": str, "Email": str, "Phone": str, "Status": str},
    "Opportunity": {"Name": str, "StageName": str, "CloseDate": str, "Amount": (int, float), "AccountId": str},
    "Case": {"Subject": str, "Description": str, "Status": str, "Priority": str, "Origin": str, "ContactId": str},
}
REQUIRED = {
    "Account": {"Name"},
    "Contact": {"LastName"},
    "Lead": {"LastName", "Company"},
    "Opportunity": {"Name", "StageName", "CloseDate"},
    "Case": set(),
}
_ID = re.compile(r"^[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?$")
_HOST = re.compile(
    r"^[a-z0-9][a-z0-9-]*(?:--[a-z0-9-]+)?\.(?:(?:demo|develop|patch|sandbox|scratch|trailblaze)\.)?my\.salesforce\.com$"
)


def invalid(message: str) -> InvalidRequestError:
    return InvalidRequestError(message, provider="salesforce")


def origin() -> str:
    """Read a single deployment org endpoint from operator configuration."""
    raw = os.environ.get("LANGFLOW_SALESFORCE_ORIGIN", "")
    try:
        parts = urlsplit(raw)
        valid = (
            parts.scheme == "https"
            and parts.hostname
            and _HOST.fullmatch(parts.hostname)
            and parts.netloc == parts.hostname
            and parts.path in {"", "/"}
            and not parts.query
            and not parts.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        msg = "Configure LANGFLOW_SALESFORCE_ORIGIN with a Salesforce My Domain HTTPS origin."
        raise invalid(msg)
    return f"https://{parts.hostname}"


def object_name(value: Any) -> str:
    if not isinstance(value, str) or value not in FIELDS:
        msg = "Choose a supported Salesforce object."
        raise invalid(msg)
    return value


def record_id(value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        msg = "A Salesforce record ID must contain 15 or 18 alphanumeric characters."
        raise invalid(msg)
    return value


def selected_fields(obj: str, value: Any = None) -> list[str]:
    obj = object_name(obj)
    if value is None or value in ("", []):
        return [*SYSTEM_FIELDS, *FIELDS[obj]]
    fields = value.split(",") if isinstance(value, str) else value
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_FIELDS:
        msg = "Select at most 30 supported scalar fields."
        raise invalid(msg)
    fields = [field.strip() if isinstance(field, str) else field for field in fields]
    if any(not isinstance(field, str) or field not in {*SYSTEM_FIELDS, *FIELDS[obj]} for field in fields):
        msg = "A selected Salesforce field is unsupported."
        raise invalid(msg)
    return list(dict.fromkeys([*SYSTEM_FIELDS, *fields]))


def values(obj: str, payload: Any, *, create: bool) -> dict:
    obj = object_name(obj)
    payload = getattr(payload, "data", payload)
    if not isinstance(payload, dict) or not payload or len(payload) > len(FIELDS[obj]):
        msg = "Supply a nonempty object of supported writable fields."
        raise invalid(msg)
    if create and not REQUIRED[obj] <= payload.keys():
        msg = "The record is missing required fields for this object."
        raise invalid(msg)
    for key, value in payload.items():
        expected = FIELDS[obj].get(key)
        if expected is None or (value is not None and (isinstance(value, bool) or not isinstance(value, expected))):
            msg = "A record field name or scalar value type is unsupported."
            raise invalid(msg)
        if isinstance(value, str) and len(value) > MAX_FIELD_LENGTH:
            msg = "A record field exceeds the supported value size."
            raise invalid(msg)
        if isinstance(value, float) and not math.isfinite(value):
            msg = "Numeric fields must be finite."
            raise invalid(msg)
        if key.endswith("Id") and value is not None:
            record_id(value)
        if create and key in REQUIRED[obj] and (value is None or value == ""):
            msg = "Required record fields cannot be empty."
            raise invalid(msg)
        if key == "CloseDate" and value is not None:
            try:
                date.fromisoformat(value)
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError
            except ValueError:
                msg = "CloseDate must use YYYY-MM-DD."
                raise invalid(msg) from None
    return dict(payload)


def timestamp(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError):
        msg = "Salesforce returned an invalid replication timestamp."
        raise invalid(msg) from None


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
