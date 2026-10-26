"""GitHub update issue through the connected App installation."""

from lfx_github.base import (
    DropdownInput,
    GitHubActionComponent,
    IntInput,
    MultilineInput,
    Output,
    StrInput,
    connection_input,
    repository_input,
)


class GitHubUpdateIssueComponent(GitHubActionComponent):
    display_name = "GitHub: Update Issue"
    description = "Update Issue in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubUpdateIssue"
    capability_id = "github.issue_update"
    operation = "update"
    resource = "issues"
    inputs = [
        connection_input("github.issue_update"),
        repository_input(),
        IntInput(name="number", display_name="Issue or Pull Request Number", required=True, value=1),
        StrInput(name="title", display_name="Title", value="", info="Leave empty to keep the existing title."),
        MultilineInput(
            name="body",
            display_name="Body",
            value="",
            info="Leave empty to keep the existing body. Nonempty text is limited to 60,000 UTF-8 bytes.",
        ),
        DropdownInput(
            name="state", display_name="State Change", options=["unchanged", "open", "closed"], value="unchanged"
        ),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
