"""Get one GitLab issue using a connection."""

from lfx.io import IntInput, Output

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabGetIssueComponent(GitLabActionComponent):
    display_name = "GitLab Get Issue"
    name = "GitLabGetIssueComponent"
    description = "Get a GitLab issue as the connection owner."
    capability_id = "gitlab.issue_read"
    operation = "get"
    resource = "issue"
    inputs = [
        connection_input(capability_id),
        project_input(),
        IntInput(name="number", display_name="Issue or Merge Request Number", required=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
