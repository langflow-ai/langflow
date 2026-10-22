"""GitHub update pull request through the connected App installation."""

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


class GitHubUpdatePullRequestComponent(GitHubActionComponent):
    display_name = "GitHub: Update Pull Request"
    description = "Update Pull Request in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubUpdatePullRequest"
    capability_id = "github.pull_request_update"
    operation = "update"
    resource = "pulls"
    inputs = [
        connection_input("github.pull_request_update"),
        repository_input(),
        IntInput(name="number", display_name="Issue or Pull Request Number", required=True, value=1),
        StrInput(name="title", display_name="Title", required=True),
        MultilineInput(name="body", display_name="Body", value="", info="At most 60,000 UTF-8 bytes."),
        DropdownInput(name="state", display_name="State", options=["open", "closed"], value="open"),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
