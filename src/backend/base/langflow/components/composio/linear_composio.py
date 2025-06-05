from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioLinearAPIComponent(ComposioBaseComponent):
    display_name: str = "Linear"
    description: str = "Linear API"
    icon = "Linear"
    documentation: str = "https://docs.composio.dev"
    app_name = "linear"

    _actions_data: dict = {
        "LINEAR_CREATE_LINEAR_COMMENT": {
            "display_name": "Create Linear Comment",
            "action_fields": ["LINEAR_CREATE_LINEAR_COMMENT_body", "LINEAR_CREATE_LINEAR_COMMENT_issue_id"],
        },
        "LINEAR_CREATE_LINEAR_ISSUE": {
            "display_name": "Create Linear Issue",
            "action_fields": [
                "LINEAR_CREATE_LINEAR_ISSUE_assignee_id",
                "LINEAR_CREATE_LINEAR_ISSUE_description",
                "LINEAR_CREATE_LINEAR_ISSUE_due_date",
                "LINEAR_CREATE_LINEAR_ISSUE_estimate",
                "LINEAR_CREATE_LINEAR_ISSUE_label_ids",
                "LINEAR_CREATE_LINEAR_ISSUE_parent_id",
                "LINEAR_CREATE_LINEAR_ISSUE_priority",
                "LINEAR_CREATE_LINEAR_ISSUE_project_id",
                "LINEAR_CREATE_LINEAR_ISSUE_state_id",
                "LINEAR_CREATE_LINEAR_ISSUE_team_id",
                "LINEAR_CREATE_LINEAR_ISSUE_title",
            ],
        },
        "LINEAR_CREATE_LINEAR_ISSUE_DETAILS": {
            "display_name": "Get Create Issue Default Params",
            "action_fields": ["LINEAR_CREATE_LINEAR_ISSUE_DETAILS_team_id"],
            "get_result_field": True,
            "result_field": "team",
        },
        "LINEAR_CREATE_LINEAR_LABEL": {
            "display_name": "Create Label",
            "action_fields": [
                "LINEAR_CREATE_LINEAR_LABEL_color",
                "LINEAR_CREATE_LINEAR_LABEL_description",
                "LINEAR_CREATE_LINEAR_LABEL_name",
                "LINEAR_CREATE_LINEAR_LABEL_team_id",
            ],
        },
        "LINEAR_DELETE_LINEAR_ISSUE": {
            "display_name": "Delete Issue",
            "action_fields": ["LINEAR_DELETE_LINEAR_ISSUE_issue_id"],
        },
        "LINEAR_GET_CYCLES_BY_TEAM_ID": {
            "display_name": "Get Cycles By Team",
            "action_fields": ["LINEAR_GET_CYCLES_BY_TEAM_ID_team_id"],
            "get_result_field": True,
            "result_field": "cycles",
        },
        "LINEAR_GET_LINEAR_ISSUE": {
            "display_name": "Get Linear Issue",
            "action_fields": ["LINEAR_GET_LINEAR_ISSUE_issue_id"],
            "get_result_field": True,
            "result_field": "issue",
        },
        "LINEAR_LIST_LINEAR_CYCLES": {
            "display_name": "Get All Cycles",
            "action_fields": [],
            "get_result_field": True,
            "result_field": "cycles",
        },
        "LINEAR_LIST_LINEAR_ISSUES": {
            "display_name": "Get Issues By Project",
            "action_fields": [
                "LINEAR_LIST_LINEAR_ISSUES_after",
                "LINEAR_LIST_LINEAR_ISSUES_first",
                "LINEAR_LIST_LINEAR_ISSUES_project_id",
            ],
        },
        "LINEAR_LIST_LINEAR_LABELS": {
            "display_name": "Get Labels By Team",
            "action_fields": ["LINEAR_LIST_LINEAR_LABELS_team_id"],
            "get_result_field": True,
            "result_field": "labels",
        },
        "LINEAR_LIST_LINEAR_PROJECTS": {
            "display_name": "List Linear Projects",
            "action_fields": [],
            "get_result_field": True,
            "result_field": "projects",
        },
        "LINEAR_LIST_LINEAR_STATES": {
            "display_name": "Get States By Team",
            "action_fields": ["LINEAR_LIST_LINEAR_STATES_team_id"],
            "get_result_field": True,
            "result_field": "states",
        },
        "LINEAR_LIST_LINEAR_TEAMS": {
            "display_name": "Get Teams By Project",
            "action_fields": ["LINEAR_LIST_LINEAR_TEAMS_project_id"],
            "get_result_field": True,
            "result_field": "teams",
        },
        "LINEAR_REMOVE_ISSUE_LABEL": {
            "display_name": "Remove Label From Linear Issue",
            "action_fields": ["LINEAR_REMOVE_ISSUE_LABEL_issue_id", "LINEAR_REMOVE_ISSUE_LABEL_label_id"],
        },
        "LINEAR_UPDATE_ISSUE": {
            "display_name": "Update Issue",
            "action_fields": [
                "LINEAR_UPDATE_ISSUE_assignee_id",
                "LINEAR_UPDATE_ISSUE_description",
                "LINEAR_UPDATE_ISSUE_due_date",
                "LINEAR_UPDATE_ISSUE_estimate",
                "LINEAR_UPDATE_ISSUE_issue_id",
                "LINEAR_UPDATE_ISSUE_label_ids",
                "LINEAR_UPDATE_ISSUE_parent_id",
                "LINEAR_UPDATE_ISSUE_priority",
                "LINEAR_UPDATE_ISSUE_project_id",
                "LINEAR_UPDATE_ISSUE_state_id",
                "LINEAR_UPDATE_ISSUE_team_id",
                "LINEAR_UPDATE_ISSUE_title",
            ],
        },
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}

    inputs = [
        *ComposioBaseComponent._base_inputs,
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_COMMENT_body",
            display_name="Body",
            info="Content of the comment",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_COMMENT_issue_id",
            display_name="Issue Id",
            info="ID of the issue to comment on",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_assignee_id",
            display_name="Assignee Id",
            info="ID of the assignee",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_description",
            display_name="Description",
            info="Description of the issue",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_due_date",
            display_name="Due Date",
            info="Due date of the issue in the comma separated format YYYY,MM,DD,hh,mm,ss. For example, 2024,10,27,12,58,00.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_estimate",
            display_name="Estimate",
            info="The Int scalar type represents non-fractional signed whole numeric values. Int can represent values between -(2^31) and 2^31 - 1.",  # noqa: E501
            show=False,
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_label_ids",
            display_name="Label Ids",
            info="List of label IDs",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_parent_id",
            display_name="Parent Id",
            info="ID of the parent issue",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_priority",
            display_name="Priority",
            info="The priority of the issue. 0 = No priority, 1 = Urgent, 2 = High, 3 = Normal, 4 = Low.",
            show=False,
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_project_id",
            display_name="Project Id",
            info="ID of the project",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_state_id",
            display_name="State Id",
            info="ID of the issue state",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_team_id",
            display_name="Team Id",
            info="ID of the team",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_title",
            display_name="Title",
            info="Title of the issue",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_ISSUE_DETAILS_team_id",
            display_name="Team Id",
            info="ID of the team for which to fetch details",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_LABEL_color",
            display_name="Color",
            info="Color of the label (hex code)",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_LABEL_description",
            display_name="Description",
            info="Description of the label",
            show=False,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_LABEL_name",
            display_name="Name",
            info="Name of the label",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_CREATE_LINEAR_LABEL_team_id",
            display_name="Team Id",
            info="ID of the team to create the label for",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_DELETE_LINEAR_ISSUE_issue_id",
            display_name="Issue Id",
            info="The ID of the issue to delete (can be UUID or shorthand ID like 'LIN-123')",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_GET_CYCLES_BY_TEAM_ID_team_id",
            display_name="Team Id",
            info="ID of the team for which to list cycles",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_GET_LINEAR_ISSUE_issue_id",
            display_name="Issue Id",
            info="ID of the issue for which to fetch details",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_LIST_LINEAR_ISSUES_after",
            display_name="After",
            info="Cursor to start from",
            show=False,
        ),
        IntInput(
            name="LINEAR_LIST_LINEAR_ISSUES_first",
            display_name="First",
            info="Number of issues to return",
            show=False,
            value=10,
        ),
        MessageTextInput(
            name="LINEAR_LIST_LINEAR_ISSUES_project_id",
            display_name="Project Id",
            info="ID of the project for which to list issues. If this is provided the issues returned will be filtered by the given project ID.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_LIST_LINEAR_LABELS_team_id",
            display_name="Team Id",
            info="ID of the team for which to list labels",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_LIST_LINEAR_STATES_team_id",
            display_name="Team Id",
            info="ID of the team for which to list states",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_LIST_LINEAR_TEAMS_project_id",
            display_name="Project Id",
            info="ID of the project for which to list teams",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_REMOVE_ISSUE_LABEL_issue_id",
            display_name="Issue Id",
            info="The ID of the Linear issue from which to remove the label",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_REMOVE_ISSUE_LABEL_label_id",
            display_name="Label Id",
            info="The ID of the label to remove from the issue",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_RUN_QUERY_OR_MUTATION_query_or_mutation",
            display_name="Query Or Mutation",
            info="Query or mutation to run",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_RUN_QUERY_OR_MUTATION_variables",
            display_name="Variables",
            info="Variables to pass to the query or mutation",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_assignee_id",
            display_name="Assignee Id",
            info="ID of the assignee",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_description",
            display_name="Description",
            info="New description for the issue",
            show=False,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_due_date",
            display_name="Due Date",
            info="Due date of the issue in the comma separated format YYYY,MM,DD,hh,mm,ss. For example, 2024,10,27,12,58,00.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="LINEAR_UPDATE_ISSUE_estimate",
            display_name="Estimate",
            info="Time estimate for the issue in minutes",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_issue_id",
            display_name="Issue Id",
            info="ID of the issue to update",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_label_ids",
            display_name="Label Ids",
            info="List of label IDs to assign to the issue",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_parent_id",
            display_name="Parent Id",
            info="ID of the parent issue",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="LINEAR_UPDATE_ISSUE_priority",
            display_name="Priority",
            info="The priority of the issue. 0 = No priority, 1 = Urgent, 2 = High, 3 = Normal, 4 = Low.",
            show=False,
            advanced=True,
        ),
        MessageTextIproject_idnput(
            name="LINEAR_UPDATE_ISSUE_",
            display_name="Project Id",
            info="ID of the project",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_state_id",
            display_name="State Id",
            info="ID of the issue state",
            show=False,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_team_id",
            display_name="Team Id",
            info="ID of the team",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="LINEAR_UPDATE_ISSUE_title",
            display_name="Title",
            info="New title for the issue",
            show=False,
        ),
    ]

    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
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

                    if field in ["LINEAR_CREATE_LINEAR_ISSUE_label_ids", "LINEAR_UPDATE_ISSUE_label_ids"] and value:
                        value = [item.strip() for item in value.split(",")]

                    param_name = field.replace(action_key + "_", "")

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                return {"error": result.get("error", "No response")}

            result_data = result.get("data", [])
            actions_data = self._actions_data.get(action_key, {})
            # If 'get_result_field' is True and 'result_field' is specified, extract the data
            # using 'result_field'. Otherwise, fall back to the entire 'data' field in the response.
            if actions_data.get("get_result_field") and actions_data.get("result_field"):
                result_data = result_data.get(actions_data.get("result_field"), result.get("data", []))
            if len(result_data) != 1 and not actions_data.get("result_field") and actions_data.get("get_result_field"):
                msg = f"Expected a dict with a single key, got {len(result_data)} keys: {result_data.keys()}"
                raise ValueError(msg)
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
            self.sanitize_action_name("LINEAR_CREATE_LINEAR_ISSUE").replace(" ", "-"),
            self.sanitize_action_name("LINEAR_GET_LINEAR_ISSUE").replace(" ", "-"),
        }
