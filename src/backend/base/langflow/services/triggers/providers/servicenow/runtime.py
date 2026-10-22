"""Bounded latest-state polling with atomic cursor and event commits."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from lfx.integrations.errors import InvalidRequestError
from lfx_servicenow.client import ServiceNowClient
from lfx_servicenow.schema import READ_SCOPE, origin, record_id, result_record, table

from langflow.services.database.models.connection.model import Connection
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider
from langflow.services.triggers.providers.servicenow.oauth import OAUTH
from langflow.services.triggers.source_poll import SourceRound

_TIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$")
_PAGE_SIZE = 100
_MAX_PAGES = 100
_MAX_TRACKED = 10000


def normalize_config(kind: str, raw: dict) -> dict:
    if kind not in {"servicenow.ticket_created", "servicenow.status_changed"}:
        msg = "Unsupported ServiceNow source kind."
        raise ValueError(msg)
    if set(raw) - {"connection", "table", "delivery_mode", "mechanism_id"}:
        msg = "Unsupported ServiceNow source settings."
        raise ValueError(msg)
    if (raw.get("delivery_mode") or "poll") not in {"auto", "poll"}:
        msg = "ServiceNow triggers require polling in this release."
        raise ValueError(msg)
    if raw.get("mechanism_id") not in {None, "servicenow.poll"}:
        msg = "Unsupported ServiceNow source mechanism."
        raise ValueError(msg)
    return {"connection": raw.get("connection"), "table": table(raw.get("table", "incident")), "delivery_mode": "poll"}


def _stamp(value: object) -> str:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        msg = "ServiceNow returned an invalid time cursor."
        raise ValueError(msg)
    datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return value


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def prepare(session, trigger) -> None:
    connection = await session.get(Connection, trigger.connection_id)
    account = (connection.executing_identity or {}).get("account") if connection else None
    if not isinstance(account, dict) or account.get("tenant_id") != origin():
        msg = "Reconnect ServiceNow to the configured instance before enabling this source."
        raise ValueError(msg)
    if trigger.kind == "servicenow.ticket_created" and not (trigger.provider_state or {}).get("baseline_complete"):
        start = _now().strftime("%Y-%m-%d %H:%M:%S")
        trigger.provider_state = {"watermark": start, "started_at": start, "baseline_complete": True}
        session.add(trigger)


async def collect(trigger, lease) -> SourceRound:
    config = normalize_config(trigger.kind, trigger.config or {})
    chosen = config["table"]
    previous = dict(trigger.provider_state or {})
    cutoff = (_now() - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")
    creation = trigger.kind == "servicenow.ticket_created"
    baseline = not previous.get("baseline_complete")
    if creation and baseline:
        return SourceRound(
            items=[],
            cursor={"watermark": cutoff, "started_at": cutoff, "baseline_complete": True},
            previous_cursor=previous,
            baseline=True,
            snapshot_resource=None,
            connection_id=trigger.connection_id,
            mechanism_id="servicenow.poll",
        )
    lower = None
    if not baseline:
        watermark = datetime.strptime(_stamp(previous.get("watermark")), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        if watermark.strftime("%Y-%m-%d %H:%M:%S") > cutoff:
            return SourceRound(
                items=[],
                cursor={},
                previous_cursor=previous,
                baseline=False,
                snapshot_resource=None,
                connection_id=trigger.connection_id,
                mechanism_id="servicenow.poll",
            )
        lower = (watermark - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
        if creation:
            lower = max(lower, _stamp(previous.get("started_at", previous.get("watermark"))))
    timestamp_field = "sys_created_on" if creation else "sys_updated_on"
    states = dict(previous.get("observed_states", {})) if not creation else {}
    items = []
    after = None
    async with ServiceNowClient(lease) as client:
        for page_index in range(_MAX_PAGES + 1):
            clauses = [f"{timestamp_field}<={cutoff}"]
            if lower:
                clauses.append(f"{timestamp_field}>={lower}")
            if after:
                clauses.append(f"sys_id>{after}")
            response = await client.request(
                "GET",
                f"/api/now/v1/table/{chosen}",
                params={
                    "sysparm_query": "^".join([*clauses, "ORDERBYsys_id"]),
                    "sysparm_limit": _PAGE_SIZE,
                },
            )
            rows = response["result"]
            if not isinstance(rows, list) or len(rows) > _PAGE_SIZE:
                msg = "ServiceNow returned an invalid ticket page."
                raise ValueError(msg)
            # After the data-page budget, only an empty exhaustion probe is
            # allowed. This keeps the advertised record limit inclusive.
            if rows and page_index == _MAX_PAGES:
                msg = "ServiceNow polling exceeded its page limit. The cursor was not advanced."
                raise ValueError(msg)
            for raw in rows:
                record = result_record(raw)
                identifier = record_id(record["sys_id"])
                observed_at = _stamp(record.get(timestamp_field))
                if (
                    (after is not None and identifier <= after)
                    or observed_at > cutoff
                    or (lower and observed_at < lower)
                ):
                    msg = "ServiceNow returned a ticket outside the requested page."
                    raise ValueError(msg)
                after = identifier
                if creation:
                    version = observed_at
                else:
                    status = record.get("state")
                    modified = record.get("sys_mod_count")
                    if (
                        not isinstance(status, str)
                        or not re.fullmatch(r"-?[0-9]{1,3}", status)
                        or not str(modified).isdigit()
                    ):
                        msg = "ServiceNow must expose state and sys_mod_count to this connection."
                        raise ValueError(msg)
                    prior_status = states.get(identifier)
                    states[identifier] = status
                    if len(states) > _MAX_TRACKED:
                        msg = "ServiceNow status polling supports at most 10000 observed records per trigger."
                        raise ValueError(msg)
                    if prior_status is None or prior_status == status:
                        continue
                    version = f"{record['sys_updated_on']}:{modified}:{status}"
                items.append(
                    {
                        "provider": "servicenow",
                        "resource": f"{chosen}:{trigger.kind}",
                        "id": identifier,
                        "version": version,
                        "data": record,
                        "session_key": f"servicenow:{chosen}:{identifier}",
                    }
                )
            # ACL filtering happens after the server page limit. A short page is not proof of exhaustion.
            if not rows:
                if response.get("total_count") != 0:
                    msg = "ServiceNow did not prove an exhausted page. Check table ACLs and count headers."
                    raise ValueError(msg)
                break
    cursor = {"watermark": cutoff, "baseline_complete": True}
    if creation:
        cursor["started_at"] = _stamp(previous.get("started_at", previous.get("watermark")))
    if not creation:
        cursor["observed_states"] = states
    return SourceRound(
        items=items,
        cursor=cursor,
        previous_cursor=previous,
        baseline=False,
        snapshot_resource=None,
        connection_id=trigger.connection_id,
        mechanism_id="servicenow.poll",
    )


try:
    _ORIGINS = (origin(),)
except InvalidRequestError:
    _ORIGINS = ()

PROVIDER = TriggerProvider(
    provider_id="servicenow",
    bundle="servicenow",
    normalize_config=normalize_config,
    collect=collect,
    kinds=tuple(
        TriggerKind(
            kind=kind,
            component=component,
            display_name=name,
            config_fields=("connection", "table", "delivery_mode"),
            required_scopes=(READ_SCOPE,),
            poll_mechanism="servicenow.poll",
        )
        for kind, component, name in (
            ("servicenow.ticket_created", "ServiceNowOnTicketCreatedTriggerComponent", "ServiceNow On Ticket Created"),
            (
                "servicenow.status_changed",
                "ServiceNowOnStatusChangeTriggerComponent",
                "ServiceNow On Observed Status Change",
            ),
        )
    ),
    api_origins=_ORIGINS,
    prepare=prepare,
    oauth=OAUTH,
)
