from unittest.mock import MagicMock, patch

import pytest
from composio import Action
from langflow.components.composio.linear_composio import ComposioLinearAPIComponent
from langflow.schema.dataframe import DataFrame

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    LINEAR_CREATE_LINEAR_ISSUE = "LINEAR_CREATE_LINEAR_ISSUE"
    LINEAR_GET_LINEAR_ISSUE = "LINEAR_GET_LINEAR_ISSUE"
    LINEAR_LIST_LINEAR_ISSUES = "LINEAR_LIST_LINEAR_ISSUES"


class TestLinearComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioLinearAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"api_key": "", "entity_id": "default", "action": None}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.17", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.18", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.19", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "composio", "file_name": DID_NOT_EXIST},
        ]

    def test_init(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.display_name == "Linear"
        assert component.app_name == "linear"
        assert "LINEAR_CREATE_LINEAR_ISSUE" in component._actions_data
        assert "LINEAR_GET_LINEAR_ISSUE" in component._actions_data

    def test_execute_action_create_issue(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "LINEAR_CREATE_LINEAR_ISSUE", MockAction.LINEAR_CREATE_LINEAR_ISSUE)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Create Linear Issue"}]
        component.LINEAR_CREATE_LINEAR_ISSUE_description = "Test Description"
        component.LINEAR_CREATE_LINEAR_ISSUE_title = "Test Title"
        component.LINEAR_CREATE_LINEAR_ISSUE_team_id = "123"
        component.LINEAR_CREATE_LINEAR_ISSUE_project_id = "123"

        component._actions_data = {
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
        }

        result = component.execute_action()
        assert result == {"result": "mocked response"}

    def test_execute_action_get_issue(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "LINEAR_GET_LINEAR_ISSUE", MockAction.LINEAR_GET_LINEAR_ISSUE)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Linear Issue"}]
        component.issue_id = "123"

        component._actions_data = {
            "LINEAR_GET_LINEAR_ISSUE": {
                "display_name": "Get Linear Issue",
                "action_fields": ["LINEAR_GET_LINEAR_ISSUE_issue_id"],
            },
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {"successful": True, "data": {"messages": "mocked response"}}

        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            assert result == {"messages": "mocked response"}

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "LINEAR_LIST_LINEAR_ISSUES", MockAction.LINEAR_LIST_LINEAR_ISSUES)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Issues By Project"}]

        mock_issues = [
            {
                "id": "a1b7b19d-41d5-2972-b102-faa0b65d2b47",
                "title": "Fix frontend",
                "description": "Fix error logs on frontend",
                "assignee": {"email": "test@gmail.com", "id": "271027-3d3f-415e-a784-6d2810351b", "name": "Test User"},
                "priority": 0,
                "project": None,
                "state": {"name": "Todo"},
            },
            {
                "id": "346745c-00a-4a15-ab55-89e329b556",
                "title": "Fix backend",
                "description": "Fix error handling on backend",
                "assignee": None,
                "priority": 0,
                "project": None,
                "state": {"name": "Backlog"},
            },
        ]

        with patch.object(component, "execute_action", return_value=mock_issues):
            result = component.as_dataframe()

            assert isinstance(result, DataFrame)

            assert not result.empty

            data_str = result.to_string()
            assert "Fix frontend" in data_str
            assert "Fix backend" in data_str

    def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "auth_link": {"value": "", "auth_tooltip": ""},
            "action": {
                "options": [],
                "helper_text": "",
                "helper_text_metadata": {},
            },
        }

        result = component.update_build_config(build_config, "", "api_key")
        assert result["auth_link"]["value"] == ""
        assert "Please provide a valid Composio API Key" in result["auth_link"]["auth_tooltip"]
        assert result["action"]["options"] == []

        component.api_key = "test_key"
        result = component.update_build_config(build_config, "test_key", "api_key")
        assert len(result["action"]["options"]) > 0
