"""Get one GitLab project using a connection."""

from lfx.io import Output

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabGetProjectComponent(GitLabActionComponent):
    display_name = "GitLab Get Project"
    name = "GitLabGetProjectComponent"
    description = "Get a GitLab project as the connection owner."
    capability_id = "gitlab.project_read"
    operation = "get"
    resource = "project"
    inputs = [connection_input(capability_id), project_input()]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
