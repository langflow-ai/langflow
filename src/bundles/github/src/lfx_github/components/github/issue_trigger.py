"""GitHub on issue declaration."""

from lfx_github.triggers import ISSUE_ACTIONS, GitHubRepositoryTrigger, trigger_inputs


class GitHubOnIssueTriggerComponent(GitHubRepositoryTrigger):
    display_name = "GitHub: On Issue"
    description = "Run when selected issue events arrive from a GitHub.com repository webhook."
    name = "GitHubOnIssueTrigger"
    trigger_kind = "github.issue"
    inputs = trigger_inputs("issue", ISSUE_ACTIONS)
