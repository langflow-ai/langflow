"""Declarative repository triggers whose delivery is owned by the server."""

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import BoolInput, ConnectionRefInput, DropdownInput, MultiselectInput, StrInput

ISSUE_ACTIONS = ["opened", "edited", "closed", "reopened", "assigned", "unassigned", "labeled", "unlabeled"]
PR_ACTIONS = [
    "opened",
    "edited",
    "closed",
    "reopened",
    "synchronize",
    "ready_for_review",
    "converted_to_draft",
    "assigned",
    "unassigned",
    "labeled",
    "unlabeled",
]


def trigger_inputs(kind: str, actions: list[str]):
    return [
        ConnectionRefInput(
            name="connection",
            display_name="GitHub Connection",
            provider="github",
            auth_profile_id="github-installation",
            identity_kind="instance",
            ownership_mode="user",
            required_scopes=[],
            capabilities=[f"github.trigger.{kind}"],
            required=False,
            info="Use the flow owner's GitHub App installation and allow background runs.",
        ),
        StrInput(name="repository", display_name="Repository", required=True, info="GitHub.com owner/repository."),
        MultiselectInput(
            name="actions", display_name="Events", options=actions, value=["opened", "closed", "reopened"]
        ),
        BoolInput(
            name="include_bot_events",
            display_name="Include Bot Events",
            value=False,
            advanced=True,
            info="Disabled by default to keep app-written issues and pull requests from triggering reply loops.",
        ),
        DropdownInput(
            name="delivery_mode",
            display_name="Delivery Mode",
            options=["push"],
            value="push",
            advanced=True,
            info="Requires public HTTPS ingress. Desktop and polling delivery are unavailable.",
        ),
    ]


class GitHubRepositoryTrigger(BaseTriggerComponent):
    provider = "github"
    icon = "Github"
    needs_connection = True

    def trigger_config(self) -> dict:
        return {
            "connection": getattr(self, "connection", None),
            "repository": getattr(self, "repository", None),
            "actions": getattr(self, "actions", []),
            "delivery_mode": "push",
            "include_bot_events": bool(getattr(self, "include_bot_events", False)),
        }
