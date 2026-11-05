"""Bounded issue targets and operator-owned Jira Cloud identity."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from uuid import UUID

from lfx.integrations.errors import InvalidRequestError

API_ORIGIN = "https://api.atlassian.com"
READ = "read:jira-work"
WRITE = "write:jira-work"
USER = "read:jira-user"
SCOPES = frozenset({READ, WRITE, USER, "offline_access"})
FIELDS = ["summary", "status", "created", "updated", "project", "issuetype"]


def invalid(message: str) -> InvalidRequestError:
    return InvalidRequestError(message, provider="jira")


def cloud_id() -> str:
    raw = os.environ.get("LANGFLOW_JIRA_CLOUD_ID", "")
    try:
        canonical = str(UUID(raw))
    except (ValueError, AttributeError):
        msg = "Configure one Jira Cloud site UUID on the Langflow server."
        raise invalid(msg) from None
    if canonical != raw:
        msg = "Use a canonical lowercase Jira Cloud site UUID."
        raise invalid(msg)
    return canonical


def project_key(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,31}", value):
        msg = "Use an uppercase Jira project key within 32 characters."
        raise invalid(msg)
    return value


def issue_key(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,31}-[1-9][0-9]{0,18}", value):
        msg = "Use a Jira issue key such as DEMO-123."
        raise invalid(msg)
    return value


def numeric_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        msg = "Use a positive Jira numeric ID."
        raise invalid(msg)
    return value


def text(value: str, *, maximum: int = 4096, required: bool = True) -> str:
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


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (AttributeError, ValueError, TypeError, OverflowError):
        msg = "Jira returned an invalid issue timestamp."
        raise invalid(msg) from None


def issue_data(value: dict, *, project: str | None = None, key: str | None = None) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("fields"), dict):
        msg = "Jira returned an invalid issue."
        raise invalid(msg)
    identifier, issue = numeric_id(value.get("id")), issue_key(value.get("key"))
    fields = value["fields"]
    if key is not None and issue != key:
        msg = "Jira returned an unrelated issue."
        raise invalid(msg)
    status = fields.get("status")
    found_project = fields.get("project")
    if (
        not isinstance(found_project, dict)
        or project_key(found_project.get("key")) != issue.rsplit("-", 1)[0]
        or (project is not None and found_project["key"] != project)
        or not isinstance(status, dict)
    ):
        msg = "Jira returned an unrelated project or invalid status."
        raise invalid(msg)
    created, updated = timestamp(fields.get("created")), timestamp(fields.get("updated"))
    return {
        "id": identifier,
        "key": issue,
        "summary": text(fields.get("summary"), maximum=32768, required=False),
        "project": found_project["key"],
        "status_id": numeric_id(status.get("id")),
        "issue_type_id": numeric_id(fields.get("issuetype", {}).get("id"))
        if isinstance(fields.get("issuetype"), dict)
        else numeric_id(None),
        "status": text(status.get("name"), maximum=1024),
        "created": created.isoformat(),
        "updated": updated.isoformat(),
    }


def search_body(project: str, status: str = "", page: str = "", *, issue_type_id: str = "") -> dict:
    query = f'project = "{project_key(project)}"'
    if status:
        query += f' AND status = "{numeric_id(status)}"'
    if issue_type_id:
        query += f' AND issuetype = "{numeric_id(issue_type_id)}"'
    result = {"jql": query + " ORDER BY key ASC", "fields": FIELDS, "maxResults": 100}
    if page:
        result["nextPageToken"] = text(page, maximum=8192)
    return result


def document(value: str) -> dict:
    value = text(value, maximum=32768, required=False)
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": value}]}],
    }
