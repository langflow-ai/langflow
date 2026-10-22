"""Get one GitLab merge request using a connection."""

from lfx.io import IntInput, Output

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabGetMergeRequestComponent(GitLabActionComponent):
    display_name = "GitLab Get Merge Request"
    name = "GitLabGetMergeRequestComponent"
    description = "Get a GitLab merge request as the connection owner."
    capability_id = "gitlab.merge_request_read"
    operation = "get"
    resource = "merge_request"
    inputs = [
        connection_input(capability_id),
        project_input(),
        IntInput(name="number", display_name="Issue or Merge Request Number", required=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
