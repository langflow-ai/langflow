"""GitHub get pull request through the connected App installation."""

from lfx_github.base import GitHubActionComponent, IntInput, Output, connection_input, repository_input


class GitHubGetPullRequestComponent(GitHubActionComponent):
    display_name = "GitHub: Get Pull Request"
    description = "Get Pull Request in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubGetPullRequest"
    capability_id = "github.pull_request_read"
    operation = "get"
    resource = "pulls"
    inputs = [
        connection_input("github.pull_request_read"),
        repository_input(),
        IntInput(name="number", display_name="Issue or Pull Request Number", required=True, value=1),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
