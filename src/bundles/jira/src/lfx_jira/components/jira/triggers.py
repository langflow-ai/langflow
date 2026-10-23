"""Declarations for bounded Jira latest-state observation."""

from lfx.io import MessageTextInput

from lfx_jira.base import JiraIssueTriggerComponent
from lfx_jira.manifest import connection_input


class JiraOnIssueCreatedTriggerComponent(JiraIssueTriggerComponent):
    display_name = "Jira On Issue Created"
    description = "Observe newly created visible issues after an initial project baseline."
    name = "JiraOnIssueCreatedTrigger"
    trigger_kind = "jira.issue_created"
    inputs = [
        connection_input("jira.trigger.created", required=False),
        MessageTextInput(name="project", display_name="Project Key", required=True),
        MessageTextInput(
            name="issue_type_id",
            display_name="Issue Type ID",
            info="Optional numeric issue type filter. At most 5000 matching issues can be observed.",
        ),
    ]


class JiraOnIssueUpdatedTriggerComponent(JiraIssueTriggerComponent):
    display_name = "Jira On Issue Updated"
    description = "Observe changed latest states of previously seen issues. Intermediate edits can be missed."
    name = "JiraOnIssueUpdatedTrigger"
    trigger_kind = "jira.issue_updated"
    inputs = [
        connection_input("jira.trigger.updated", required=False),
        MessageTextInput(name="project", display_name="Project Key", required=True),
        MessageTextInput(
            name="issue_type_id",
            display_name="Issue Type ID",
            info="Optional numeric issue type filter. At most 5000 matching issues can be observed.",
        ),
    ]


class JiraOnIssueStatusChangedTriggerComponent(JiraIssueTriggerComponent):
    display_name = "Jira On Issue Status Changed"
    description = "Observe status differences between polls. Intermediate transitions can be missed."
    name = "JiraOnIssueStatusChangedTrigger"
    trigger_kind = "jira.issue_status"
    inputs = [
        connection_input("jira.trigger.status", required=False),
        MessageTextInput(name="project", display_name="Project Key", required=True),
        MessageTextInput(
            name="issue_type_id",
            display_name="Issue Type ID",
            info="Optional numeric issue type filter. At most 5000 matching issues can be observed.",
        ),
    ]
