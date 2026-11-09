"""Create a GitLab comment using a connection."""

from lfx.io import IntInput, MultilineInput, Output

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabCreateIssueCommentComponent(GitLabActionComponent):
    display_name = "GitLab: Create Issue Comment"
    name = "GitLabCreateIssueCommentComponent"
    description = "Create a comment as the connection owner."
    capability_id = "gitlab.issue_comment_create"
    operation = "comment"
    resource = "issue"
    inputs = [
        connection_input(capability_id),
        project_input(),
        IntInput(name="number", display_name="Issue Number", required=True, input_types=["Message"]),
        MultilineInput(name="body", display_name="Comment", required=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
