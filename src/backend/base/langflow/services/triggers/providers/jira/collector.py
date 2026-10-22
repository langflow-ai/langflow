"""Observe bounded project snapshots without claiming an exact event stream."""

from datetime import datetime, timezone

from lfx.integrations.errors import InvalidRequestError
from lfx.integrations.models import ConnectionRef
from lfx_jira.client import JiraClient
from lfx_jira.schema import cloud_id, invalid, issue_data, numeric_id, project_key, search_body, timestamp

from langflow.services.triggers.source_poll import SourceRound

MAX_ISSUES = 5000
MAX_PAGES = 50
PAGE_SIZE = 100
MAX_PAGE_TOKEN = 8192
KINDS = {"jira.issue_created", "jira.issue_updated", "jira.issue_status"}


def normalize_config(kind, config):
    if (
        kind not in KINDS
        or not isinstance(config, dict)
        or config.keys() - {"connection", "project", "delivery_mode", "mechanism_id", "issue_type_id"}
    ):
        msg = "Unsupported Jira trigger configuration."
        raise ValueError(msg)
    if (config.get("delivery_mode") or "poll") not in {"poll", "auto"}:
        msg = "Jira issue sources support authenticated polling only."
        raise ValueError(msg)
    try:
        ref = ConnectionRef.parse(config.get("connection", ""))
        if ref.provider != "jira":
            raise ValueError
        project = project_key(config.get("project"))
        issue_type = numeric_id(config["issue_type_id"]) if config.get("issue_type_id") else ""
    except (ValueError, TypeError, InvalidRequestError):
        msg = "Choose an owned Jira connection and a valid project key."
        raise ValueError(msg) from None
    return {**config, "connection": str(ref), "project": project, "issue_type_id": issue_type, "delivery_mode": "poll"}


async def prepare(_session, trigger):
    cloud_id()
    if trigger.state != "active":
        trigger.provider_state = {}


async def collect(trigger, lease):
    config = normalize_config(trigger.kind, dict(trigger.config or {}))
    previous = dict(trigger.provider_state or {})
    baseline = not previous.get("baseline_complete")
    started = previous.get("started_at") or datetime.now(timezone.utc).isoformat()
    threshold = timestamp(started)
    seen = previous.get("issues", {})
    if not isinstance(seen, dict) or len(seen) > MAX_ISSUES:
        msg = "The Jira source cursor is invalid. Re-enable the source for a fresh baseline."
        raise invalid(msg)
    current = {}
    rows = []
    page = ""
    tokens = set()
    client = JiraClient(lease)
    try:
        for _ in range(MAX_PAGES):
            result = await client.request(
                "POST",
                "/rest/api/3/search/jql",
                body=search_body(config["project"], page=page, issue_type_id=config["issue_type_id"]),
            )
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("issues"), list)
                or len(result["issues"]) > PAGE_SIZE
            ):
                msg = "Jira returned an invalid project snapshot."
                raise invalid(msg)
            for raw in result["issues"]:
                issue = issue_data(raw, project=config["project"])
                if config["issue_type_id"] and issue["issue_type_id"] != config["issue_type_id"]:
                    msg = "Jira returned an issue outside the selected issue type."
                    raise invalid(msg)
                identifier = issue["id"]
                if identifier in current:
                    msg = "The Jira project changed during pagination. Retry the complete snapshot."
                    raise invalid(msg)
                current[identifier] = {"updated": issue["updated"], "status": issue["status_id"]}
                old = seen.get(identifier)
                if old is not None and (not isinstance(old, dict) or set(old) != {"updated", "status"}):
                    msg = "The Jira source cursor is invalid."
                    raise invalid(msg)
                changed = (
                    (trigger.kind == "jira.issue_created" and old is None and timestamp(issue["created"]) >= threshold)
                    or (trigger.kind == "jira.issue_updated" and old is not None and old["updated"] != issue["updated"])
                    or (trigger.kind == "jira.issue_status" and old is not None and old["status"] != issue["status_id"])
                )
                if changed and not baseline:
                    rows.append(
                        {
                            "provider": "jira",
                            "resource": f"project:{config['project']}",
                            "id": identifier,
                            "version": "created"
                            if trigger.kind == "jira.issue_created"
                            else issue["updated"] + ":" + issue["status_id"],
                            "deleted": False,
                            "data": {**issue, "observation": trigger.kind.rsplit(".", 1)[-1]},
                            "session_key": f"jira:{cloud_id()}:{identifier}",
                        }
                    )
            page = result.get("nextPageToken")
            if result.get("isLast") is True or not page:
                if result.get("isLast") is False:
                    msg = "Jira returned an incomplete snapshot without a page token."
                    raise invalid(msg)
                break
            if not isinstance(page, str) or not page or len(page) > MAX_PAGE_TOKEN or page in tokens:
                msg = "Jira returned an invalid pagination cursor."
                raise invalid(msg)
            tokens.add(page)
        else:
            msg = "The Jira project exceeds the 5000-issue snapshot limit."
            raise invalid(msg)
    finally:
        await client.aclose()
    updated = {**seen, **current}
    if len(updated) > MAX_ISSUES:
        msg = "The Jira source exceeded 5000 observed issues. Re-enable it for a fresh baseline."
        raise invalid(msg)
    return SourceRound(
        items=rows,
        cursor={"baseline_complete": True, "started_at": started, "issues": updated},
        previous_cursor=previous,
        baseline=baseline,
        snapshot_resource=None,
        connection_id=trigger.connection_id,
        mechanism_id=(trigger.config or {}).get("mechanism_id"),
        config=dict(trigger.config or {}),
    )
