"""GitHub create issue comment through the connected App installation."""

from lfx_github.base import GitHubActionComponent, IntInput, MultilineInput, Output, connection_input, repository_input


class GitHubCreateCommentComponent(GitHubActionComponent):
    display_name = "GitHub: Create Issue Comment"
    description = "Create Issue Comment in a selected GitHub.com repository as the connected GitHub App."
    name = "GitHubCreateComment"
    capability_id = "github.comment_create"
    operation = "comment"
    resource = "issues"
    inputs = [
        connection_input("github.comment_create"),
        repository_input(),
        IntInput(name="number", display_name="Issue or Pull Request Number", required=True, value=1),
        MultilineInput(name="body", display_name="Body", value="", info="At most 60,000 UTF-8 bytes."),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
