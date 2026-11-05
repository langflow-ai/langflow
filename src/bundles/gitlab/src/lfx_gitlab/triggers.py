"""Declarative GitLab project triggers owned by the server runtime."""

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import BoolInput, DropdownInput, MultiselectInput

from lfx_gitlab.base import connection_input, project_input

ISSUE_ACTIONS = ["open", "update", "close", "reopen"]
MR_ACTIONS = ["open", "update", "close", "reopen", "merge", "approved", "unapproved", "approval", "unapproval"]


def trigger_inputs(resource):
    return [
        connection_input(f"gitlab.trigger.{resource}"),
        project_input(),
        MultiselectInput(
            name="actions",
            display_name="Events",
            options=ISSUE_ACTIONS if resource == "issue" else MR_ACTIONS,
            value=["open", "close", "reopen"],
        ),
        BoolInput(
            name="include_self_events",
            display_name="Include Own Events",
            value=False,
            advanced=True,
            info="Enable only when the flow cannot write back into a trigger loop.",
        ),
        BoolInput(name="include_bot_events", display_name="Include Bot Events", value=False, advanced=True),
        DropdownInput(
            name="delivery_mode",
            display_name="Delivery Mode",
            options=["push"],
            value="push",
            advanced=True,
            info="Requires public HTTPS ingress and GitLab 19.1 or newer signing tokens.",
        ),
    ]


class GitLabProjectTriggerComponent(BaseTriggerComponent):
    provider = "gitlab"
    icon = "Gitlab"
    needs_connection = True

    def trigger_config(self):
        return {
            "connection": getattr(self, "connection", None),
            "project_id": getattr(self, "project_id", None),
            "actions": getattr(self, "actions", []),
            "delivery_mode": "push",
            "include_self_events": getattr(self, "include_self_events", False),
            "include_bot_events": getattr(self, "include_bot_events", False),
        }


# Preserve imports of the original helper while component source uses the loader-compatible name.
GitLabProjectTrigger = GitLabProjectTriggerComponent
