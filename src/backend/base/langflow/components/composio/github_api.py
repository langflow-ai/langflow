from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import (
    BoolInput,
    DropdownInput,
    IntInput,
    LinkInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema.message import Message


class GitHubAPIComponent(LCToolComponent):
    display_name: str = "GitHub"
    description: str = "GitHub API"
    name = "GithubAPI"
    icon = "Github"
    documentation: str = "https://docs.composio.dev"

    _display_to_enum_map = {
        "Create A Pull Request": "GITHUB_CREATE_A_PULL_REQUEST",
        "Star A Repository": "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER",
        "List Commits": "GITHUB_LIST_COMMITS",
        "Get A Pull Request": "GITHUB_GET_A_PULL_REQUEST",
        "Create An Issue": "GITHUB_CREATE_AN_ISSUE",
        "List Repository Issues": "GITHUB_LIST_REPOSITORY_ISSUES",
        "List Branches": "GITHUB_LIST_BRANCHES",
        "List Pull Requests": "GITHUB_LIST_PULL_REQUESTS",
    }

    _actions_data: dict = {
        "GITHUB_CREATE_A_PULL_REQUEST": {
            "display_name": "Create A Pull Request",
            "parameters": [
                "GITHUB_CREATE_A_PULL_REQUEST-owner",
                "GITHUB_CREATE_A_PULL_REQUEST-repo",
                "GITHUB_CREATE_A_PULL_REQUEST-title",
                "GITHUB_CREATE_A_PULL_REQUEST-head",
                "GITHUB_CREATE_A_PULL_REQUEST-head_repo",
                "GITHUB_CREATE_A_PULL_REQUEST-base",
                "GITHUB_CREATE_A_PULL_REQUEST-body",
                "GITHUB_CREATE_A_PULL_REQUEST-maintainer_can_modify",
                "GITHUB_CREATE_A_PULL_REQUEST-draft",
                "GITHUB_CREATE_A_PULL_REQUEST-issue",
            ],
        },
        "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER": {
            "display_name": "Star A Repository",
            "parameters": [
                "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER-owner",
                "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER-repo",
            ],
        },
        "GITHUB_LIST_COMMITS": {
            "display_name": "List Commits",
            "parameters": [
                "GITHUB_LIST_COMMITS-owner",
                "GITHUB_LIST_COMMITS-repo",
                "GITHUB_LIST_COMMITS-sha",
                "GITHUB_LIST_COMMITS-path",
                "GITHUB_LIST_COMMITS-author",
                "GITHUB_LIST_COMMITS-committer",
                "GITHUB_LIST_COMMITS-since",
                "GITHUB_LIST_COMMITS-until",
                "GITHUB_LIST_COMMITS-per_page",
                "GITHUB_LIST_COMMITS-page",
            ],
        },
        "GITHUB_GET_A_PULL_REQUEST": {
            "display_name": "Get A Pull Request",
            "parameters": [
                "GITHUB_GET_A_PULL_REQUEST-owner",
                "GITHUB_GET_A_PULL_REQUEST-repo",
                "GITHUB_GET_A_PULL_REQUEST-pull_number",
            ],
        },
        "GITHUB_CREATE_AN_ISSUE": {
            "display_name": "Create An Issue",
            "parameters": [
                "GITHUB_CREATE_AN_ISSUE-owner",
                "GITHUB_CREATE_AN_ISSUE-repo",
                "GITHUB_CREATE_AN_ISSUE-title",
                "GITHUB_CREATE_AN_ISSUE-body",
                "GITHUB_CREATE_AN_ISSUE-assignee",
                "GITHUB_CREATE_AN_ISSUE-milestone",
                "GITHUB_CREATE_AN_ISSUE-labels",
                "GITHUB_CREATE_AN_ISSUE-assignees",
            ],
        },
        "GITHUB_LIST_REPOSITORY_ISSUES": {
            "display_name": "List Repository Issues",
            "parameters": [
                "GITHUB_LIST_REPOSITORY_ISSUES-owner",
                "GITHUB_LIST_REPOSITORY_ISSUES-repo",
                "GITHUB_LIST_REPOSITORY_ISSUES-milestone",
                "GITHUB_LIST_REPOSITORY_ISSUES-state",
                "GITHUB_LIST_REPOSITORY_ISSUES-assignee",
                "GITHUB_LIST_REPOSITORY_ISSUES-creator",
                "GITHUB_LIST_REPOSITORY_ISSUES-mentioned",
                "GITHUB_LIST_REPOSITORY_ISSUES-labels",
                "GITHUB_LIST_REPOSITORY_ISSUES-sort",
                "GITHUB_LIST_REPOSITORY_ISSUES-direction",
                "GITHUB_LIST_REPOSITORY_ISSUES-since",
                "GITHUB_LIST_REPOSITORY_ISSUES-per_page",
                "GITHUB_LIST_REPOSITORY_ISSUES-page",
            ],
        },
        "GITHUB_LIST_BRANCHES": {
            "display_name": "List Branches",
            "parameters": [
                "GITHUB_LIST_BRANCHES-owner",
                "GITHUB_LIST_BRANCHES-repo",
                "GITHUB_LIST_BRANCHES-protected",
                "GITHUB_LIST_BRANCHES-per_page",
                "GITHUB_LIST_BRANCHES-page",
            ],
        },
        "GITHUB_LIST_PULL_REQUESTS": {
            "display_name": "List Pull Requests",
            "parameters": [
                "GITHUB_LIST_PULL_REQUESTS-owner",
                "GITHUB_LIST_PULL_REQUESTS-repo",
                "GITHUB_LIST_PULL_REQUESTS-state",
                "GITHUB_LIST_PULL_REQUESTS-head",
                "GITHUB_LIST_PULL_REQUESTS-base",
                "GITHUB_LIST_PULL_REQUESTS-sort",
                "GITHUB_LIST_PULL_REQUESTS-direction",
                "GITHUB_LIST_PULL_REQUESTS-per_page",
                "GITHUB_LIST_PULL_REQUESTS-page",
            ],
        },
    }

    _bool_variables = {
        "GITHUB_CREATE_A_PULL_REQUEST-maintainer_can_modify",
        "GITHUB_CREATE_A_PULL_REQUEST-draft",
        "GITHUB_LIST_BRANCHES-protected",
    }

    inputs = [
        MessageTextInput(
            name="entity_id",
            display_name="Entity ID",
            value="default",
            advanced=True,
            tool_mode=True,  # Intentionally setting tool_mode=True to make this Component support both tool and non-tool functionality  # noqa: E501
        ),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            info="Refer to https://docs.composio.dev/faq/api_key/api_key",
            real_time_refresh=True,
        ),
        LinkInput(
            name="auth_link",
            display_name="Authentication Link",
            value="",
            info="Click to authenticate with OAuth2",
            dynamic=True,
            show=False,
            placeholder="Click to authenticate",
        ),
        StrInput(
            name="auth_status",
            display_name="Auth Status",
            value="Not Connected",
            info="Current authentication status",
            dynamic=True,
            show=False,
            refresh_button=True,
        ),
        # Non tool-mode input fields
        DropdownInput(
            name="action",
            display_name="Action",
            options=[],
            value="",
            info="Select Gmail action to pass to the agent",
            show=True,
            real_time_refresh=True,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE-title",
            display_name="Title",
            info="The title of the issue.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE-body",
            display_name="Body",
            info="The contents of the issue.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE-assignee",
            display_name="Assignee",
            info="Login for the user that this issue should be assigned to. _NOTE: Only users with push access can set the assignee for new issues. The assignee is silently dropped otherwise. **This field is deprecated.**_ ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_AN_ISSUE-milestone",
            display_name="Milestone",
            info="Milestone",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="GITHUB_CREATE_AN_ISSUE-labels",
            display_name="Labels",
            info="Labels to associate with this issue. _NOTE: Only users with push access can set labels for new issues. Labels are silently dropped otherwise._ ",  # noqa: E501
            show=False,
            is_list=True,
        ),
        StrInput(
            name="GITHUB_CREATE_AN_ISSUE-assignees",
            display_name="Assignees",
            info="Logins for Users to assign to this issue. _NOTE: Only users with push access can set assignees for new issues. Assignees are silently dropped otherwise._ ",  # noqa: E501
            show=False,
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS-state",
            display_name="StateEnm",
            info="Either `open`, `closed`, or `all` to filter by state.",
            show=False,
            value="open",
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS-head",
            display_name="Head",
            info="Filter pulls by head user or head organization and branch name in the format of `user:ref-name` or `organization:ref-name`. For example: `github:new-script-format` or `octocat:test-branch`. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS-base",
            display_name="Base",
            info="Filter pulls by base branch name. Example: `gh-pages`.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS-sort",
            display_name="SortEnm",
            info="What to sort results by. `popularity` will sort by the number of comments. `long-running` will sort by date created and will limit the results to pull requests that have been open for more than a month and have had activity within the past month. ",  # noqa: E501
            show=False,
            value="created",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_PULL_REQUESTS-direction",
            display_name="DirectionEnm",
            info="The direction of the sort. Default: `desc` when sort is `created` or sort is not specified, otherwise `asc`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_PULL_REQUESTS-per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=1,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_PULL_REQUESTS-page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-title",
            display_name="Title",
            info="The title of the new pull request. Required unless `issue` is specified.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-head",
            display_name="Head",
            info="The name of the branch where your changes are implemented. For cross-repository pull requests in the same network, namespace `head` with a user like this: `username:branch`. ",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-head_repo",
            display_name="Head Repo",
            info="The name of the repository where the changes in the pull request were made. This field is required for cross-repository pull requests if both repositories are owned by the same organization. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-base",
            display_name="Base",
            info="The name of the branch you want the changes pulled into. This should be an existing branch on the current repository. You cannot submit a pull request to one repository that requests a merge to a base of another repository. ",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-body",
            display_name="Body",
            info="The contents of the pull request.",
            show=False,
        ),
        BoolInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-maintainer_can_modify",
            display_name="Maintainer Can Modify",
            info="Indicates whether maintainers can modify the pull request",
            show=False,
        ),
        BoolInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-draft",
            display_name="Draft",
            info="Indicates whether the pull request is a draft",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_CREATE_A_PULL_REQUEST-issue",
            display_name="Issue",
            info="An issue in the repository to convert to a pull request. The issue title, body, and comments will become the title, body, and comments on the new pull request. Required unless `title` is specified. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-milestone",
            display_name="Milestone",
            info="If an `integer` is passed, it should refer to a milestone by its `number` field. If the string `*` is passed, issues with any milestone are accepted. If the string `none` is passed, issues without milestones are returned. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-state",
            display_name="StateEnm",
            info="Indicates the state of the issues to return.",
            show=False,
            value="open",
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-assignee",
            display_name="Assignee",
            info="Can be the name of a user. Pass in `none` for issues with no assigned user, and `*` for issues assigned to any user. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-creator",
            display_name="Creator",
            info="The user that created the issue.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-mentioned",
            display_name="Mentioned",
            info="A user that's mentioned in the issue.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-labels",
            display_name="Labels",
            info="A list of comma separated label names. Example: `bug,ui,@high`",
            show=False,
            is_list=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-sort",
            display_name="SortEnm",
            info="What to sort results by",
            show=False,
            value="created",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-direction",
            display_name="DirectionEnm",
            info="The direction to sort the results by",
            show=False,
            value="desc",
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-since",
            display_name="Since",
            info="Only show results that were last updated after the given time. This is a timestamp in ISO 8601 (https://en.wikipedia.org/wiki/ISO_8601) format: `YYYY-MM-DDTHH:MM:SSZ`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=1,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_REPOSITORY_ISSUES-page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_BRANCHES-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_BRANCHES-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        BoolInput(
            name="GITHUB_LIST_BRANCHES-protected",
            display_name="Protected",
            info="Setting to `true` returns only protected branches. When set to `false`, only unprotected branches are returned. Omitting this parameter returns all branches",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="GITHUB_LIST_BRANCHES-per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=30,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_BRANCHES-page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_GET_A_PULL_REQUEST-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_GET_A_PULL_REQUEST-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        IntInput(
            name="GITHUB_GET_A_PULL_REQUEST-pull_number",
            display_name="Pull Number",
            info="The number that identifies the pull request.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-owner",
            display_name="Owner",
            info="The account owner of the repository. The name is not case sensitive.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-repo",
            display_name="Repo",
            info="The name of the repository without the `.git` extension. The name is not case sensitive. ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-sha",
            display_name="Sha",
            info="SHA or branch to start listing commits from. Default: the repository's default branch (usually `main`). ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-path",
            display_name="Path",
            info="Only commits containing this file path will be returned.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-author",
            display_name="Author",
            info="GitHub username or email address to use to filter by commit author.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-committer",
            display_name="Committer",
            info="GitHub username or email address to use to filter by commit committer.",
            show=False,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-since",
            display_name="Since",
            info="Only show results that were last updated after the given time. This is a timestamp in ISO 8601 (https://en.wikipedia.org/wiki/ISO_8601) format: `YYYY-MM-DDTHH:MM:SSZ`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GITHUB_LIST_COMMITS-until",
            display_name="Until",
            info="Only commits before this date will be returned. This is a timestamp in ISO 8601 (https://en.wikipedia.org/wiki/ISO_8601) format: `YYYY-MM-DDTHH:MM:SSZ`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_COMMITS-per_page",
            display_name="Per Page",
            info="The number of results per page (max 100)",
            show=False,
            value=1,
            advanced=True,
        ),
        IntInput(
            name="GITHUB_LIST_COMMITS-page",
            display_name="Page",
            info="The page number of the results to fetch",
            show=False,
            value=1,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

    def execute_action(self) -> Message:
        """Execute GitHub action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            action_key = self._display_to_enum_map.get(self.action)

            enum_name = getattr(Action, action_key)  # type: ignore[arg-type]
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["parameters"]:
                    param_name = field.split("-", 1)[1] if "-" in field else field
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    if field in self._bool_variables:
                        value = bool(value)

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            self.status = result
            return Message(text=str(result))
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action
            if self.action in self._actions_data:
                display_name = self._actions_data[self.action]["display_name"]
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def show_hide_fields(self, build_config: dict, field_value: Any):
        all_fields = set()
        for action_data in self._actions_data.values():
            all_fields.update(action_data["parameters"])

        for field in all_fields:
            build_config[field]["show"] = False

            if field in self._bool_variables:
                build_config[field]["value"] = False
            else:
                build_config[field]["value"] = ""

        action_key = self._display_to_enum_map.get(field_value)

        if action_key in self._actions_data:
            for field in self._actions_data[action_key]["parameters"]:
                build_config[field]["show"] = True

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False

        if field_name == "tool_mode":
            if field_value:
                build_config["action"]["show"] = False

                all_fields = set()
                for action_data in self._actions_data.values():
                    all_fields.update(action_data["parameters"])
                for field in all_fields:
                    build_config[field]["show"] = False

            else:
                build_config["action"]["show"] = True

        if field_name == "action":
            self.show_hide_fields(build_config, field_value)

        if hasattr(self, "api_key") and self.api_key != "":
            github_display_names = list(self._display_to_enum_map.keys())
            build_config["action"]["options"] = github_display_names

            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                try:
                    entity.get_connection(app="github")
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False

                except NoItemsFound:
                    auth_scheme = self._get_auth_scheme("github")
                    if auth_scheme.auth_mode == "OAUTH2":
                        build_config["auth_link"]["show"] = True
                        build_config["auth_link"]["advanced"] = False
                        auth_url = self._initiate_default_connection(entity, "github")
                        build_config["auth_link"]["value"] = auth_url
                        build_config["auth_status"]["value"] = "Click link to authenticate"

            except (ValueError, ConnectionError) as e:
                logger.error(f"Error checking auth status: {e}")
                build_config["auth_status"]["value"] = f"Error: {e!s}"

        return build_config

    def _get_auth_scheme(self, app_name: str) -> AppAuthScheme:
        """Get the primary auth scheme for an app.

        Args:
        app_name (str): The name of the app to get auth scheme for.

        Returns:
        AppAuthScheme: The auth scheme details.
        """
        toolset = self._build_wrapper()
        try:
            return toolset.get_auth_scheme_for_app(app=app_name.lower())
        except Exception:  # noqa: BLE001
            logger.exception(f"Error getting auth scheme for {app_name}")
            return None

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

    def _build_wrapper(self) -> ComposioToolSet:
        """Build the Composio toolset wrapper.

        Returns:
        ComposioToolSet: The initialized toolset.

        Raises:
        ValueError: If the API key is not found or invalid.
        """
        try:
            if not self.api_key:
                msg = "Composio API Key is required"
                raise ValueError(msg)
            return ComposioToolSet(api_key=self.api_key)
        except ValueError as e:
            logger.error(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e

    async def _get_tools(self) -> list[Tool]:
        toolset = self._build_wrapper()
        tools = toolset.get_tools(actions=self._actions_data.keys())
        for tool in tools:
            tool.tags = [tool.name]  # Assigning tags directly
        return tools

    @property
    def enabled_tools(self):
        return [
            "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER",
            "GITHUB_GET_A_PULL_REQUEST",
        ]
