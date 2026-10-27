"""GitHub create issue through the connected App installation."""

from lfx_github.base import GitHubActionComponent, MultilineInput, Output, StrInput, connection_input, repository_input


class GitHubCreateIssueComponent(GitHubActionComponent):
    display_name = "GitHub: Create Issue"
    description = "Create Issue in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubCreateIssue"
    capability_id = "github.issue_create"
    operation = "create"
    resource = "issues"
    inputs = [
        connection_input("github.issue_create"),
        repository_input(),
        StrInput(name="title", display_name="Title", required=True),
        MultilineInput(name="body", display_name="Body", value="", info="At most 60,000 UTF-8 bytes."),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
