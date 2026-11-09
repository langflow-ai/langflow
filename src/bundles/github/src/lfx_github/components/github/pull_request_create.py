"""GitHub create pull request through the connected App installation."""

from lfx_github.base import GitHubActionComponent, MultilineInput, Output, StrInput, connection_input, repository_input


class GitHubCreatePullRequestComponent(GitHubActionComponent):
    display_name = "GitHub: Create Pull Request"
    description = "Create Pull Request in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubCreatePullRequest"
    capability_id = "github.pull_request_create"
    operation = "create"
    resource = "pulls"
    inputs = [
        connection_input("github.pull_request_create"),
        repository_input(),
        StrInput(name="title", display_name="Title", required=True),
        MultilineInput(name="body", display_name="Body", value="", info="At most 60,000 UTF-8 bytes."),
        StrInput(name="head", display_name="Head Branch", required=True),
        StrInput(name="base", display_name="Base Branch", required=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
