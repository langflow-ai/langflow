from unittest.mock import patch

import pytest
from composio import Action

from lfx.components.composio.github_composio import ComposioGitHubAPIComponent
from lfx.schema.dataframe import DataFrame
from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER = "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER"
    GITHUB_LIST_BRANCHES = "GITHUB_LIST_BRANCHES"
    GITHUB_LIST_REPOSITORY_ISSUES = "GITHUB_LIST_REPOSITORY_ISSUES"


class TestGitHubComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioGitHubAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "",
            "entity_id": "default",
            "action": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        # Component not yet released, mark all versions as non-existent
        return [
            {"version": "1.0.17", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.18", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.0.19", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "composio", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "composio", "file_name": DID_NOT_EXIST},
        ]

    def test_init(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.display_name == "GitHub"
        assert component.app_name == "github"
        assert "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER" in component._actions_data
        assert "GITHUB_LIST_BRANCHES" in component._actions_data

    def test_execute_action_star_a_repo(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(
            Action,
            "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER",
            MockAction.GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER,
        )

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Star A Repository"}]
        component.GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_owner = "langflow-ai"
        component.GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_repo = "langflow"

        # For this specific test, customize the _actions_data to not use get_result_field
        component._actions_data = {
            "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER": {
                "display_name": "Star A Repository",
                "action_fields": [
                    "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_owner",
                    "GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER_repo",
                ],
            },
        }

        # Execute action
        result = component.execute_action()
        assert result == {"result": "mocked response"}

    def test_execute_action_list_branches(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GITHUB_LIST_BRANCHES", MockAction.GITHUB_LIST_BRANCHES)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Branches"}]
        component.GITHUB_LIST_BRANCHES_owner = "langflow-ai"
        component.GITHUB_LIST_BRANCHES_repo = "langflow"

        # For this specific test, customize the _actions_data to not use get_result_field
        component._actions_data = {
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
        }

        # Execute action
        result = component.execute_action()
        assert result == {"result": "mocked response"}

    def test_execute_action_list_repo_issues(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GITHUB_LIST_REPOSITORY_ISSUES", MockAction.GITHUB_LIST_REPOSITORY_ISSUES)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Repository Issues"}]
        component.GITHUB_LIST_REPOSITORY_ISSUES_owner = "langflow-ai"
        component.GITHUB_LIST_REPOSITORY_ISSUES_repo = "langflow"

        # For this specific test, customize the _actions_data to not use get_result_field
        component._actions_data = {
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
        }

        # Execute action
        result = component.execute_action()
        assert result == {"result": "mocked response"}

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        # Execute action should raise ValueError
        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        # Mock Action enum
        monkeypatch.setattr(Action, "GITHUB_LIST_REPOSITORY_ISSUES", MockAction.GITHUB_LIST_REPOSITORY_ISSUES)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Repository Issues"}]
        component.max_results = 10

        # Create mock email data that would be returned by execute_action
        mock_issues = [
            {
                "url": "url1",
                "repository_url": "repository_url1",
                "id": "id1",
                "title": "test issue",
                "state": "open",
            },
            {
                "url": "url2",
                "repository_url": "repository_url2",
                "id": "id2",
                "title": "test issue",
                "state": "open",
            },
        ]

        # Mock the execute_action method to return our mock data
        with patch.object(component, "execute_action", return_value=mock_issues):
            # Test as_dataframe method
            result = component.as_dataframe()

            # Verify the result is a DataFrame
            assert isinstance(result, DataFrame)

            # Verify the DataFrame is not empty
            assert not result.empty

            # Check for expected content in the DataFrame string representation
            data_str = str(result)
            assert "test issue" in data_str

    def test_update_build_config(self, component_class, default_kwargs):
        # Test that the GitHub component properly inherits and uses the base component's
        # update_build_config method
        component = component_class(**default_kwargs)
        build_config = {
            "auth_link": {"value": "", "auth_tooltip": ""},
            "action": {
                "options": [],
                "helper_text": "",
                "helper_text_metadata": {},
            },
        }

        # Test with empty API key
        result = component.update_build_config(build_config, "", "api_key")
        assert result["auth_link"]["value"] == ""
        assert "Please provide a valid Composio API Key" in result["auth_link"]["auth_tooltip"]
        assert result["action"]["options"] == []

        # Test with valid API key
        component.api_key = "test_key"
        result = component.update_build_config(build_config, "test_key", "api_key")
        assert len(result["action"]["options"]) > 0  # Should have GitHub actions
