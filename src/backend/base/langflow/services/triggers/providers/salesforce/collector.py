"""Expand replication IDs into latest visible record states."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lfx.integrations.errors import InvalidRequestError
from lfx_salesforce.client import SalesforceClient
from lfx_salesforce.schema import API_ROOT, invalid, iso, object_name, record_id, selected_fields, timestamp

from langflow.services.triggers.source_poll import SourceRound

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease

    from langflow.services.database.models.trigger.model import Trigger

MAX_IDS = 5000
WINDOW = timedelta(minutes=5)


def normalize_config(kind: str, config: dict[str, Any]) -> dict[str, Any]:
    try:
        return _normalize_config(kind, config)
    except InvalidRequestError as exc:
        raise ValueError(str(exc)) from None


def _normalize_config(kind: str, config: dict[str, Any]) -> dict[str, Any]:
    if kind != "salesforce.record" or not isinstance(config, dict):
        msg = "Unsupported Salesforce source kind."
        raise invalid(msg)
    allowed = {"connection", "delivery_mode", "object_name", "fields", "mechanism_id"}
    if config.keys() - allowed or (config.get("delivery_mode") or "poll") not in {"poll", "auto"}:
        msg = "Salesforce record sources support polling with bounded record fields only."
        raise invalid(msg)
    obj = object_name(config.get("object_name") or "Account")
    if not isinstance(config.get("connection"), str) or not config["connection"].startswith("salesforce/"):
        msg = "Choose an owned Salesforce connection."
        raise invalid(msg)
    from lfx.integrations.models import ConnectionRef

    try:
        ConnectionRef.parse(config["connection"])
    except ValueError:
        msg = "Choose a valid Salesforce connection handle."
        raise invalid(msg) from None
    return {**config, "object_name": obj, "fields": selected_fields(obj, config.get("fields")), "delivery_mode": "poll"}


async def collect(trigger: Trigger, lease: CredentialLease) -> SourceRound:
    config = normalize_config(trigger.kind, dict(trigger.config or {}))
    state = dict(trigger.provider_state or {})
    obj, fields = config["object_name"], config["fields"]
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    baseline = "latest_date_covered" not in state
    previous = timestamp(state["latest_date_covered"]) if not baseline else now - timedelta(minutes=1)
    start = previous.replace(second=0, microsecond=0)
    if previous > now or previous < now - timedelta(days=29):
        msg = "The Salesforce replication cursor expired or is invalid. Disable and re-enable the source."
        raise invalid(msg)
    end = min(now, start + WINDOW)
    result = SourceRound(
        items=[],
        cursor=state,
        previous_cursor=state,
        baseline=baseline,
        snapshot_resource=None,
        connection_id=trigger.connection_id,
        mechanism_id=(trigger.config or {}).get("mechanism_id"),
        config=dict(trigger.config or {}),
    )
    if end <= start:
        return result
    client = SalesforceClient(lease)
    try:
        await client.describe(obj, operation="poll", fields=fields)
        response = await client.request(
            "GET", f"{API_ROOT}/sobjects/{obj}/updated/", params={"start": iso(start), "end": iso(end)}
        )
        if not isinstance(response, dict) or not isinstance(response.get("ids"), list):
            msg = "Salesforce returned an invalid replication result."
            raise invalid(msg)
        ids = response["ids"]
        if len(ids) > MAX_IDS:
            msg = "The Salesforce replication window exceeds 5000 IDs. Reduce source volume before retrying."
            raise invalid(msg)
        ids = list(dict.fromkeys(record_id(value) for value in ids))
        covered = timestamp(response.get("latestDateCovered"))
        if covered < previous or covered > end:
            msg = "Salesforce returned an invalid replication cursor."
            raise invalid(msg)
        items = []
        for offset in range(0, len(ids), 200):
            batch = ids[offset : offset + 200]
            records = await client.request(
                "GET",
                f"{API_ROOT}/composite/sobjects/{obj}",
                params={"ids": ",".join(batch), "fields": ",".join(fields)},
            )
            if not isinstance(records, list) or len(records) != len(batch):
                msg = "Salesforce returned an invalid record batch."
                raise invalid(msg)
            for expected, record in zip(batch, records, strict=True):
                if record is None:
                    # Deleted or newly inaccessible records have no visible state.
                    continue
                if not isinstance(record, dict) or record.get("Id") != expected:
                    msg = "Salesforce returned an unrelated source record."
                    raise invalid(msg)
                version = iso(timestamp(record.get("SystemModstamp")))
                payload = {key: value for key, value in record.items() if key in fields}
                items.append(
                    {
                        "provider": "salesforce",
                        "resource": f"records:{obj}",
                        "id": expected,
                        "version": version,
                        "deleted": False,
                        "data": payload,
                        "session_key": f"salesforce:{obj}:{expected}",
                    }
                )
        return SourceRound(
            items=items,
            cursor={"latest_date_covered": iso(covered), "baseline_complete": True},
            previous_cursor=state,
            baseline=baseline,
            snapshot_resource=None,
            connection_id=trigger.connection_id,
            mechanism_id=(trigger.config or {}).get("mechanism_id"),
            config=dict(trigger.config or {}),
        )
    finally:
        await client.aclose()


async def prepare(_session: Any, trigger: Trigger) -> None:
    """A deliberate re-enable starts a fresh baseline after the paused interval."""
    from lfx_salesforce.schema import origin

    try:
        origin()
    except InvalidRequestError as exc:
        raise ValueError(str(exc)) from None
    if trigger.state != "active":
        trigger.provider_state = {}
