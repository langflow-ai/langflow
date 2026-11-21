"""GitHub on pull request declaration."""

from lfx_github.triggers import PR_ACTIONS, GitHubRepositoryTriggerComponent, trigger_inputs


class GitHubOnPullRequestTriggerComponent(GitHubRepositoryTriggerComponent):
    display_name = "GitHub: On Pull Request"
    description = "Run when selected pull request events arrive from a GitHub.com repository webhook."
    name = "GitHubOnPullRequestTrigger"
    trigger_kind = "github.pull_request"
    inputs = trigger_inputs("pull_request", PR_ACTIONS)
