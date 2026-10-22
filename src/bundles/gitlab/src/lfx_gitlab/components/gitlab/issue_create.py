"""Create one GitLab issue using a connection."""

from lfx.io import MultilineInput, Output, StrInput

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabCreateIssueComponent(GitLabActionComponent):
    display_name = "GitLab Create Issue"
    name = "GitLabCreateIssueComponent"
    description = "Create a GitLab issue as the connection owner."
    capability_id = "gitlab.issue_create"
    operation = "create"
    resource = "issue"
    inputs = [
        connection_input(capability_id),
        project_input(),
        StrInput(name="title", display_name="Title", required=True),
        MultilineInput(name="body_content", display_name="Description", value=""),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
