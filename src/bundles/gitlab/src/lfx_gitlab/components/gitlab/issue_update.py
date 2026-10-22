"""Update one GitLab issue using a connection."""

from lfx.io import DropdownInput, IntInput, MultilineInput, Output, StrInput

from lfx_gitlab.base import GitLabActionComponent, connection_input, project_input


class GitLabUpdateIssueComponent(GitLabActionComponent):
    display_name = "GitLab Update Issue"
    name = "GitLabUpdateIssueComponent"
    description = "Update a GitLab issue as the connection owner."
    capability_id = "gitlab.issue_update"
    operation = "update"
    resource = "issue"
    inputs = [
        connection_input(capability_id),
        project_input(),
        IntInput(name="number", display_name="Issue or Merge Request Number", required=True),
        StrInput(name="title", display_name="Title", required=True),
        MultilineInput(name="body_content", display_name="Description", value=""),
        DropdownInput(
            name="state_event", display_name="State Change", options=["unchanged", "close", "reopen"], value="unchanged"
        ),
    ]
    outputs = [Output(display_name="Result", name="result", method="build_result")]
