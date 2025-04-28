import json
from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    BoolInput,
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioGitHubAPIComponent(ComposioBaseComponent):
    """GitHub API component for interacting with GitHub services."""

    display_name: str = "GitHub"
    description: str = "GitHub API"
    icon = "Github"
    documentation: str = "https://docs.composio.dev"
    app_name = "github"

    # GitHub-specific actions
    _actions_data: dict = {
        "GITHUB_CREATE_A_PULL_REQUEST": {
            "display_name": "Create A Pull Request",
            "action_fields": [
                "GITHUB_CREATE_A_PULL_REQUEST_owner",
                "GITHUB_CREATE_A_PULL_REQUEST_repo",
                "GITHUB_CREATE_A_PULL_REQUEST_title",
                "GITHUB_CREATE_A_PULL_REQUEST_head",
                "GITHUB_CREATE_A_PULL_REQUEST_head_repo",
                "GITHUB_CREATE_A_PULL_REQUEST_base",
                "GITHUB_CREATE_A_PULL_REQUEST_body",
                "GITHUB_CREATE_A_PULL_REQUEST_maintainer_can_modify",
                "GITHUB_CREATE_A_PULL_REQUEST_draft",
                "GITHUB_CREATE_A_PULL_REQUEST_issue",
            ],
        },
        "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER": {
            "display_name": "Star A Repository",
            "action_fields": [
                "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_owner",
                "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_repo",
            ],
        },
        "GITHUB_LIST_COMMITS": {
            "display_name": "List Commits",
            "action_fields": [
                "GITHUB_LIST_COMMITS_owner",
                "GITHUB_LIST_COMMITS_repo",
                "GITHUB_LIST_COMMITS_sha",
                "GITHUB_LIST_COMMITS_path",
                "GITHUB_LIST_COMMITS_author",
                "GITHUB_LIST_COMMITS_committer",
                "GITHUB_LIST_COMMITS_since",
                "GITHUB_LIST_COMMITS_until",
                "GITHUB_LIST_COMMITS_per_page",
                "GITHUB_LIST_COMMITS_page",
            ],
        },
        "GITHUB_GET_A_PULL_REQUEST": {
            "display_name": "Get A Pull Request",
            "action_fields": [
                "GITHUB_GET_A_PULL_REQUEST_owner",
                "GITHUB_GET_A_PULL_REQUEST_repo",
                "GITHUB_GET_A_PULL_REQUEST_pull_number",
            ],
        },
        "GITHUB_CREATE_AN_ISSUE": {
            "display_name": "Create An Issue",
            "action_fields": [
                "GITHUB_CREATE_AN_ISSUE_owner",
                "GITHUB_CREATE_AN_ISSUE_repo",
                "GITHUB_CREATE_AN_ISSUE_title",
                "GITHUB_CREATE_AN_ISSUE_body",
                "GITHUB_CREATE_AN_ISSUE_assignee",
                "GITHUB_CREATE_AN_ISSUE_milestone",
                "GITHUB_CREATE_AN_ISSUE_labels",
                "GITHUB_CREATE_AN_ISSUE_assignees",
            ],
        },
        "GITHUB_LIST_REPOSITORY_ISSUES": {
            "display_name": "List Repository Issues",
            "action_fields": [
                "GITHUB_LIST_REPOSITORY_ISSUES_owner",
                "GITHUB_LIST_REPOSITORY_ISSUES_repo",
                "GITHUB_LIST_REPOSITORY_ISSUES_milestone",
                "GITHUB_LIST_REPOSITORY_ISSUES_state",
                "GITHUB_LIST_REPOSITORY_ISSUES_assignee",
                "GITHUB_LIST_REPOSITORY_ISSUES_creator",
                "GITHUB_LIST_REPOSITORY_ISSUES_mentioned",
                "GITHUB_LIST_REPOSITORY_ISSUES_labels",
                "GITHUB_LIST_REPOSITORY_ISSUES_sort",
                "GITHUB_LIST_REPOSITORY_ISSUES_direction",
                "GITHUB_LIST_REPOSITORY_ISSUES_since",
                "GITHUB_LIST_REPOSITORY_ISSUES_per_page",
                "GITHUB_LIST_REPOSITORY_ISSUES_page",
            ],
        },
        "GITHUB_LIST_BRANCHES": {
            "display_name": "List Branches",
            "action_fields": [
                "GITHUB_LIST_BRANCHES_owner",
                "GITHUB_LIST_BRANCHES_repo",
                "GITHUB_LIST_BRANCHES_protected",
                "GITHUB_LIST_BRANCHES_per_page",
                "GITHUB_LIST_BRANCHES_page",
            ],
        },
        "GITHUB_LIST_PULL_REQUESTS": {
            "display_name": "List Pull Requests",
            "action_fields": [
                "GITHUB_LIST_PULL_REQUESTS_owner",
                "GITHUB_LIST_PULL_REQUESTS_repo",
                "GITHUB_LIST_PULL_REQUESTS_state",
                "GITHUB_LIST_PULL_REQUESTS_head",
                "GITHUB_LIST_PULL_REQUESTS_base",
                "GITHUB_LIST_PULL_REQUESTS_sort",
                "GITHUB_LIST_PULL_REQUESTS_direction",
                "GITHUB_LIST_PULL_REQUESTS_per_page",
                "GITHUB_LIST_PULL_REQUESTS_page",
            ],
        },
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
    _bool_variables = {
        "GITHUB_CREATE_A_PULL_REQUEST_maintainer_can_modify",
        "GITHUB_CREATE_A_PULL_REQUEST_draft",
        "GITHUB_LIST_BRANCHES_protected",
    }

    inputs = [
        *ComposioBaseComponent._base_inputs,
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_title",
            display_name="Title",
            info="The title of the issue.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_body",
            display_name="Body",
            info="The contents of the issue.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_assignee",
            display_name="Assignee",
            info="Login for the user that this issue should be assigned to. _NOTE: Only users with push access can set the assignee for new issues. The assignee is silently dropped otherwise. **This field is deprecated.**_ ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_milestone",
            display_name="Milestone",
            info="Milestone",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_labels",
            display_name="Labels",
            info="Labels to associate with this issue. _NOTE: Only users with push access can set labels for new issues. Labels are silently dropped otherwise._ ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE_assignees",
            display_name="Assignees",
            info="Logins for Users to assign to this issue. _NOTE: Only users with push access can set assignees for new issues. Assignees are silently dropped otherwise._ ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS_state",
            display_name="State",
            info="Either `open`, `closed`, or `all` to filter by state.",
            show=False,
            value="open",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS_head",
            display_name="Head",
            info="Filter pulls by head user or head organization and branch name in the format of `user:ref-name` or `organization:ref-name`. For example: `github:new-script-format` or `octocat:test-branch`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS_base",
            display_name="Base",
            info="Filter pulls by base branch name. Example: `gh-pages`.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS_sort",
            display_name="Sort",
            info="What to sort results by. `popularity` will sort by the number of comments. `long-running` will sort by date created and will limit the results to pull requests that have been open for more than a month and have had activity within the past month. ",  # noqa: E501
            show=False,
            value="created",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS_direction",
            display_name="Direction",
            info="The direction of the sort. Default: `desc` when sort is `created` or sort is not specified, otherwise `asc`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_PULL_REQUESTS_per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=1,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_PULL_REQUESTS_page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_title",
            display_name="Title",
            info="The title of the new pull request. Required unless `issue` is specified.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_head",
            display_name="Head",
            info="The name of the branch where your changes are implemented. For cross-repository pull requests in the same network, namespace `head` with a user like this: `username:branch`. ",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_head_repo",
            display_name="Head Repo",
            info="The name of the repository where the changes in the pull request were made. This field is required for cross-repository pull requests if both repositories are owned by the same organization. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_base",
            display_name="Base",
            info="The name of the branch you want the changes pulled into. This should be an existing branch on the current repository. You cannot submit a pull request to one repository that requests a merge to a base of another repository. ",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_body",
            display_name="Body",
            info="The contents of the pull request.",
            show=False,
        ),
        BoolInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_maintainer_can_modify",
            display_name="Maintainer Can Modify",
            info="Indicates whether maintainers can modify the pull request",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_draft",
            display_name="Draft",
            info="Indicates whether the pull request is a draft",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_CREATE_A_PULL_REQUEST_issue",
            display_name="Issue",
            info="An issue in the repository to convert to a pull request. The issue title, body, and comments will become the title, body, and comments on the new pull request. Required unless `title` is specified. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_milestone",
            display_name="Milestone",
            info="If an `integer` is passed, it should refer to a milestone by its `number` field. If the string `*` is passed, issues with any milestone are accepted. If the string `none` is passed, issues without milestones are returned. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_state",
            display_name="State",
            info="Indicates the state of the issues to return.",
            show=False,
            value="open",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_assignee",
            display_name="Assignee",
            info="Can be the name of a user. Pass in `none` for issues with no assigned user, and `*` for issues assigned to any user. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_creator",
            display_name="Creator",
            info="The user that created the issue.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_mentioned",
            display_name="Mentioned",
            info="A user that's mentioned in the issue.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_labels",
            display_name="Labels",
            info="A list of comma separated label names. Example: `bug,ui,@high`",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_sort",
            display_name="Sort",
            info="What to sort results by",
            show=False,
            value="created",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_direction",
            display_name="Direction",
            info="The direction to sort the results by",
            show=False,
            value="desc",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_since",
            display_name="Since",
            info="Only show results that were last updated after the given time. This is a timestamp in ISO 8601 (https://en.wikipedia.org/wiki/ISO_8601) format: `YYYY-MM-DDTHH:MM:SSZ`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=1,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES_page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_BRANCHES_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_BRANCHES_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        BoolInput(
            name="GITHUB_LIST_BRANCHES_protected",
            display_name="Protected",
            info="Setting to `true` returns only protected branches. When set to `false`, only unprotected branches are returned. Omitting this parameter returns all branches",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="GITHUB_LIST_BRANCHES_per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=30,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_BRANCHES_page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_GET_A_PULL_REQUEST_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_GET_A_PULL_REQUEST_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        IntInput(
            name="GITHUB_GET_A_PULL_REQUEST_pull_number",
            display_name="Pull Number",
            info="The number that identifies the pull request.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_repo",
            display_name="Repo",
            info="The name of the repository. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_sha",
            display_name="SHA",
            info="SHA or branch to start listing commits from. Default: the repository's default branch (usually `main`). ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_path",
            display_name="Path",
            info="Only commits containing this file path will be returned.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_author",
            display_name="Author",
            info="GitHub username or email address to use to filter by commit author.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_committer",
            display_name="Committer",
            info="GitHub username or email address to use to filter by commit committer.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_since",
            display_name="Since",
            info="Only show results that were last updated after the given time. This is a timestamp in ISO 8601 (https://en.wikipedia.org/wiki/ISO_8601) format: `YYYY-MM-DDTHH:MM:SSZ`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS_until",
            display_name="Until",
            info="Only commits before this date will be returned. This is a timestamp in ISO 8601 (https://en.wikipedia.org/wiki/ISO_8601) format: `YYYY-MM-DDTHH:MM:SSZ`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_COMMITS_per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=1,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_COMMITS_page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
    ]

    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            # Get the display name from the action list
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
            # Use the display_to_key_map to get the action key
            action_key = self._display_to_key_map.get(display_name)
            if not action_key:
                msg = f"Invalid action: {display_name}"
                raise ValueError(msg)

            enum_name = getattr(Action, action_key)
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["action_fields"]:
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    if (
                        field
                        in [
                            "GITHUB_CREATE_AN_ISSUE_labels",
                            "GITHUB_CREATE_AN_ISSUE_assignees",
                            "GITHUB_LIST_REPOSITORY_ISSUES_labels",
                        ]
                        and value
                    ):
                        value = [item.strip() for item in value.split(",")]

                    if field in self._bool_variables:
                        value = bool(value)

                    param_name = field.replace(action_key + "_", "")
                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                try:
                    message_str = result.get("error", {})
                    error_message = message_str.split("`")[1]
                    error_msg_json = json.loads(error_message)
                except (IndexError, json.JSONDecodeError):
                    return {"error": str(message_str)}
                return {
                    "code": error_msg_json.get("status"),
                    "message": error_msg_json.get("message"),
                    "documentation_url": error_msg_json.get("documentation_url"),
                }

            result_data = result.get("data", [])
            if (
                len(result_data) != 1
                and not self._actions_data.get(action_key, {}).get("result_field")
                and self._actions_data.get(action_key, {}).get("get_result_field")
            ):
                msg = f"Expected a dict with a single key, got {len(result_data)} keys: {result_data.keys()}"
                raise ValueError(msg)
            if isinstance(result_data.get("details"), list):
                return result_data.get("details")
            return result_data  # noqa: TRY300
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            self.sanitize_action_name("GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER").replace(" ", "-"),
            self.sanitize_action_name("GITHUB_CREATE_A_PULL_REQUEST").replace(" ", "-"),
        }
