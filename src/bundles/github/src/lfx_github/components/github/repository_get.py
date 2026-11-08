"""GitHub get repository through the connected App installation."""

from lfx_github.base import GitHubActionComponent, Output, connection_input, repository_input


class GitHubGetRepositoryComponent(GitHubActionComponent):
    display_name = "GitHub: Get Repository"
    description = "Get Repository in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubGetRepository"
    capability_id = "github.repository_read"
    operation = "repository"
    resource = ""
    inputs = [connection_input("github.repository_read"), repository_input()]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
