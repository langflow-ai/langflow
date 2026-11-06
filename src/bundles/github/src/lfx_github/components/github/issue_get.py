"""GitHub get issue through the connected App installation."""

from lfx_github.base import GitHubActionComponent, IntInput, Output, connection_input, repository_input


class GitHubGetIssueComponent(GitHubActionComponent):
    display_name = "GitHub: Get Issue"
    description = "Get Issue in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubGetIssue"
    capability_id = "github.issue_read"
    operation = "get"
    resource = "issues"
    inputs = [
        connection_input("github.issue_read"),
        repository_input(),
        IntInput(name="number", display_name="Issue or Pull Request Number", required=True, value=1),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
