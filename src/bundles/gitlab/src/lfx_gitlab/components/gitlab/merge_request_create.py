"""Create one GitLab merge request using a connection."""

from lfx.io import MessageTextInput, MultilineInput, Output

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabCreateMergeRequestComponent(GitLabActionComponent):
    display_name = "GitLab: Create Merge Request"
    name = "GitLabCreateMergeRequestComponent"
    description = "Create a GitLab merge request as the connection owner."
    capability_id = "gitlab.merge_request_create"
    operation = "create"
    resource = "merge_request"
    inputs = [
        connection_input(capability_id),
        project_input(),
        MessageTextInput(name="title", display_name="Title", required=True, tool_mode=True),
        MultilineInput(name="body_content", display_name="Description", value="", tool_mode=True),
        MessageTextInput(name="source_branch", display_name="Source Branch", required=True, tool_mode=True),
        MessageTextInput(name="target_branch", display_name="Target Branch", required=True, tool_mode=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
