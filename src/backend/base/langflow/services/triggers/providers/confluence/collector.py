"""Observe complete bounded page snapshots and commit cursors through the shared runtime."""

from datetime import datetime, timezone

from lfx.integrations.errors import IntegrationError
from lfx.integrations.models import ConnectionRef
from lfx_confluence.client import ConfluenceClient
from lfx_confluence.schema import (
    MAX_ITEMS,
    MAX_PAGES,
    MAX_VERSION,
    approved_space,
    cloud_id,
    invalid,
    list_params,
    numeric_id,
    page_list,
    timestamp,
)

from langflow.services.triggers.source_poll import SourceRound

KINDS = {"confluence.page_created", "confluence.page_updated"}


def normalize_config(kind, config):
    if (
        kind not in KINDS
        or not isinstance(config, dict)
        or config.keys() - {"connection", "space_id", "delivery_mode", "mechanism_id"}
    ):
        msg = "Unsupported Confluence trigger configuration."
        raise ValueError(msg)
    if (config.get("delivery_mode") or "poll") not in {"poll", "auto"}:
        msg = "Confluence page sources support authenticated polling only."
        raise ValueError(msg)
    try:
        ref = ConnectionRef.parse(config.get("connection", ""))
        if ref.provider != "confluence":
            raise ValueError
        space = approved_space(config.get("space_id"))
    except (ValueError, TypeError, IntegrationError):
        msg = "Choose an owned Confluence connection and an approved space."
        raise ValueError(msg) from None
    return {**config, "connection": str(ref), "space_id": space, "delivery_mode": "poll"}


async def prepare(_session, trigger):
    cloud_id()
    approved_space((trigger.config or {}).get("space_id"))
    if trigger.state != "active":
        trigger.provider_state = {}


async def collect(trigger, lease):
    config = normalize_config(trigger.kind, dict(trigger.config or {}))
    previous = dict(trigger.provider_state or {})
    baseline = not previous.get("baseline_complete")
    started = previous.get("started_at") or datetime.now(timezone.utc).isoformat()
    threshold = timestamp(started)
    seen = previous.get("pages", {})
    if not isinstance(seen, dict) or len(seen) > MAX_ITEMS:
        msg = "The Confluence cursor is invalid. Re-enable the source for a fresh baseline."
        raise invalid(msg)
    for key, version in seen.items():
        numeric_id(key)
        if type(version) is not int or not 1 <= version <= MAX_VERSION:
            msg = "The Confluence source version cursor is invalid."
            raise invalid(msg)
    current, rows, cursors = {}, [], set()
    cursor = ""
    client = ConfluenceClient(lease)
    try:
        for _ in range(MAX_PAGES):
            result = await client.request(
                "GET", "/wiki/api/v2/pages", params=list_params(config["space_id"], cursor=cursor)
            )
            pages, cursor = page_list(result, space=config["space_id"])
            for page in pages:
                identifier = page["id"]
                if identifier in current:
                    msg = "The Confluence space changed during pagination. Retry the complete snapshot."
                    raise invalid(msg)
                current[identifier] = page["version"]
                old = seen.get(identifier)
                if old is not None and page["version"] < old:
                    msg = "Confluence returned an older page version. Retry the complete snapshot."
                    raise invalid(msg)
                changed = (
                    trigger.kind == "confluence.page_created"
                    and old is None
                    and timestamp(page["created_at"]) >= threshold
                ) or (trigger.kind == "confluence.page_updated" and old is not None and page["version"] > old)
                if changed and not baseline:
                    rows.append(
                        {
                            "provider": "confluence",
                            "resource": f"space:{config['space_id']}",
                            "id": identifier,
                            "version": "created" if trigger.kind == "confluence.page_created" else str(page["version"]),
                            "deleted": False,
                            "data": {**page, "observation": trigger.kind.rsplit(".", 1)[-1]},
                            "session_key": f"confluence:{cloud_id()}:{identifier}",
                        }
                    )
            if len(current) > MAX_ITEMS:
                msg = "The Confluence space exceeds the 5000-page snapshot limit."
                raise invalid(msg)
            if not cursor:
                break
            if cursor in cursors:
                msg = "Confluence repeated a pagination cursor."
                raise invalid(msg)
            cursors.add(cursor)
        else:
            msg = "The Confluence space exceeds the 50-page request limit."
            raise invalid(msg)
    finally:
        await client.aclose()
    updated = {**seen, **current}
    if len(updated) > MAX_ITEMS:
        msg = "The source exceeded 5000 observed page IDs. Re-enable it for a fresh baseline."
        raise invalid(msg)
    return SourceRound(
        items=rows,
        cursor={"baseline_complete": True, "started_at": started, "pages": updated},
        previous_cursor=previous,
        baseline=baseline,
        snapshot_resource=None,
        connection_id=trigger.connection_id,
        mechanism_id=(trigger.config or {}).get("mechanism_id"),
        config=dict(trigger.config or {}),
    )
