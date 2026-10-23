"""Update one GitLab merge request using a connection."""

from lfx.io import DropdownInput, IntInput, MultilineInput, Output, StrInput

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabUpdateMergeRequestComponent(GitLabActionComponent):
    display_name = "GitLab Update Merge Request"
    name = "GitLabUpdateMergeRequestComponent"
    description = "Update a GitLab merge request as the connection owner."
    capability_id = "gitlab.merge_request_update"
    operation = "update"
    resource = "merge_request"
    inputs = [
        connection_input(capability_id),
        project_input(),
        IntInput(name="number", display_name="Issue or Merge Request Number", required=True),
        StrInput(name="title", display_name="Title", value="", info="Leave blank to keep the existing title."),
        MultilineInput(
            name="body_content",
            display_name="Description",
            value="",
            info="Leave blank to keep the existing description.",
        ),
        DropdownInput(
            name="state_event", display_name="State Change", options=["unchanged", "close", "reopen"], value="unchanged"
        ),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
