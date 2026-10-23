"""Validate non-secret project trigger configuration."""

from lfx.integrations.models import ConnectionRef
from lfx_gitlab.client import positive_id
from lfx_gitlab.triggers import ISSUE_ACTIONS, MR_ACTIONS

ACTIONS = {"gitlab.issue": frozenset(ISSUE_ACTIONS), "gitlab.merge_request": frozenset(MR_ACTIONS)}


def normalize_config(kind, raw):
    if kind not in ACTIONS:
        msg = "Unsupported GitLab trigger kind."
        raise ValueError(msg)
    ref = ConnectionRef.parse(raw.get("connection"))
    if ref.provider != "gitlab":
        msg = "Choose a GitLab connection."
        raise ValueError(msg)
    if raw.get("delivery_mode", "push") not in {"auto", "push"}:
        msg = "GitLab triggers require signed public HTTPS webhook ingress."
        raise ValueError(msg)
    actions = raw.get("actions", ["open", "close", "reopen"])
    if (
        not isinstance(actions, list)
        or not actions
        or any(not isinstance(action, str) or action not in ACTIONS[kind] for action in actions)
    ):
        msg = "Choose supported GitLab event actions."
        raise ValueError(msg)
    if any(type(raw.get(field, False)) is not bool for field in ("include_self_events", "include_bot_events")):
        msg = "Event filters must be true or false."
        raise ValueError(msg)
    return {
        "connection": ref.to_handle(),
        "project_id": positive_id(raw.get("project_id")),
        "actions": sorted(set(actions)),
        "delivery_mode": "push",
        "include_self_events": raw.get("include_self_events", False),
        "include_bot_events": raw.get("include_bot_events", False),
    }
