"""Jira Cloud runtime owned by the installed Jira bundle."""

from langflow.services.triggers.providers.jira.collector import collect, normalize_config, prepare
from langflow.services.triggers.providers.jira.oauth import OAUTH
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider

PROVIDER = TriggerProvider(
    provider_id="jira",
    bundle="jira",
    kinds=tuple(
        TriggerKind(
            kind=kind,
            component=component,
            display_name=name,
            config_fields=("connection", "project", "issue_type_id", "delivery_mode"),
            required_scopes=("read:jira-work", "offline_access"),
            poll_mechanism="jira.issue.poll",
        )
        for kind, component, name in (
            ("jira.issue_created", "JiraOnIssueCreatedTriggerComponent", "Jira On Issue Created"),
            ("jira.issue_updated", "JiraOnIssueUpdatedTriggerComponent", "Jira On Issue Updated"),
            ("jira.issue_status", "JiraOnIssueStatusChangedTriggerComponent", "Jira On Issue Status Changed"),
        )
    ),
    normalize_config=normalize_config,
    collect=collect,
    prepare=prepare,
    oauth=OAUTH,
    api_origins=("https://api.atlassian.com",),
)
