"""Validate the non-secret configuration persisted for GitHub triggers."""

from __future__ import annotations

from typing import Any

from lfx.integrations.models import ConnectionRef
from lfx_github.client import repository_path
from lfx_github.triggers import ISSUE_ACTIONS, PR_ACTIONS

ACTIONS = {"github.issue": frozenset(ISSUE_ACTIONS), "github.pull_request": frozenset(PR_ACTIONS)}


def normalize_config(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    if kind not in ACTIONS:
        msg = "Unsupported GitHub trigger kind."
        raise ValueError(msg)
    ref = ConnectionRef.parse(raw.get("connection"))
    if ref.provider != "github":
        msg = "Choose a GitHub App installation connection."
        raise ValueError(msg)
    repository = raw.get("repository")
    repository_path(repository)
    delivery = raw.get("delivery_mode") or "push"
    if delivery not in {"auto", "push"}:
        msg = "GitHub event triggers require public HTTPS webhook ingress. Polling is unavailable."
        raise ValueError(msg)
    actions = raw.get("actions") if raw.get("actions") is not None else ["opened", "closed", "reopened"]
    if (
        not isinstance(actions, list)
        or not actions
        or any(not isinstance(action, str) or action not in ACTIONS[kind] for action in actions)
    ):
        msg = "Choose one or more supported GitHub events."
        raise ValueError(msg)
    include_bots = raw.get("include_bot_events") if raw.get("include_bot_events") is not None else False
    if type(include_bots) is not bool:
        msg = "Include Bot Events must be true or false."
        raise ValueError(msg)
    return {
        "connection": ref.to_handle(),
        "repository": repository.lower(),
        "delivery_mode": "push",
        "include_bot_events": include_bots,
        "actions": sorted(set(actions)),
    }
