"""Update one GitLab merge request using a connection."""

from lfx.io import DropdownInput, IntInput, MessageTextInput, MultilineInput, Output

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabUpdateMergeRequestComponent(GitLabActionComponent):
    display_name = "GitLab: Update Merge Request"
    name = "GitLabUpdateMergeRequestComponent"
    description = "Update a GitLab merge request as the connection owner."
    capability_id = "gitlab.merge_request_update"
    operation = "update"
    resource = "merge_request"
    inputs = [
        connection_input(capability_id),
        project_input(),
        IntInput(
            name="number", display_name="Merge Request Number", required=True, input_types=["Message"], tool_mode=True
        ),
        MessageTextInput(
            name="title", display_name="Title", value="", info="Leave blank to keep the existing title.", tool_mode=True
        ),
        MultilineInput(
            name="body_content",
            display_name="Description",
            value="",
            info="Leave blank to keep the existing description.",
            tool_mode=True,
        ),
        DropdownInput(
            name="state_event",
            display_name="State Change",
            options=["unchanged", "close", "reopen"],
            value="unchanged",
            tool_mode=True,
        ),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
