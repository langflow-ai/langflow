from unittest.mock import MagicMock, patch

import pytest
from composio import Action
from langflow.components.composio.googlesheets_composio import ComposioGooglesheetsAPIComponent
from langflow.schema.dataframe import DataFrame

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    GOOGLESHEETS_CREATE_GOOGLE_SHEET1 = "GOOGLESHEETS_CREATE_GOOGLE_SHEET1"
    GOOGLESHEETS_GET_SPREADSHEET_INFO = "GOOGLESHEETS_GET_SPREADSHEET_INFO"


class TestGooglesheetsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("langflow.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioGooglesheetsAPIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "",
            "entity_id": "default",
            "action": None,
        }

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
        assert component.display_name == "Google Sheets"
        assert component.app_name == "googlesheets"
        assert "GOOGLESHEETS_CREATE_GOOGLE_SHEET1" in component._actions_data
        assert "GOOGLESHEETS_GET_SPREADSHEET_INFO" in component._actions_data

    def test_execute_action_create_sheet(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "GOOGLESHEETS_CREATE_GOOGLE_SHEET1", MockAction.GOOGLESHEETS_CREATE_GOOGLE_SHEET1)

        # Setup component
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Create Google Sheet"}]
        component.GOOGLESHEETS_CREATE_GOOGLE_SHEET1_title = "test title"

        component._actions_data = {
            "GOOGLESHEETS_CREATE_GOOGLE_SHEET1": {
                "display_name": "Create Google Sheet",
                "action_fields": ["GOOGLESHEETS_CREATE_GOOGLE_SHEET1_title"],
            },
        }

        result = component.execute_action()
        assert result == {"response": "mocked response"}

    def test_execute_action_get_sheet_info(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "GOOGLESHEETS_GET_SPREADSHEET_INFO", MockAction.GOOGLESHEETS_GET_SPREADSHEET_INFO)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Spreadsheet Info"}]
        component.GOOGLESHEETS_GET_SPREADSHEET_INFO_spreadsheet_id = "12345"

        component._actions_data = {
            "GOOGLESHEETS_GET_SPREADSHEET_INFO": {
                "display_name": "Get Spreadsheet Info",
                "action_fields": ["GOOGLESHEETS_GET_SPREADSHEET_INFO_spreadsheet_id"],
            },
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {"successful": True, "data": {"response": "mocked response"}}

        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            assert result == {"response": "mocked response"}

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "GOOGLESHEETS_GET_SPREADSHEET_INFO", MockAction.GOOGLESHEETS_GET_SPREADSHEET_INFO)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Get Spreadsheet Info"}]
        component.GOOGLESHEETS_GET_SPREADSHEET_INFO_spreadsheet_id = "12345"

        mock_sheet_info = [
            {
                "spreadsheetId": "1xXaF_aJgZ0rSAeSwcGP_epqefFGCQUfRA_1",
                "title": "Test Sheet 1",
                "url": "https://docs.google.com/spreadsheets/d/random/edit",
                "locale": "en_US",
                "timeZone": "America/Los_Angeles",
                "sheetCount": 3,
                "sheets": [
                    {"sheetId": 0, "title": "Sheet1", "rowCount": 1000, "columnCount": 26},
                    {"sheetId": 1, "title": "Sheet2", "rowCount": 1000, "columnCount": 26},
                ],
            },
            {
                "spreadsheetId": "1xXaF_aJgZ0rSAeSwcGP_epqefFGCQUfRA_2",
                "title": "Test Sheet 2",
                "url": "https://docs.google.com/spreadsheets/d/random/edit",
                "locale": "en_GB",
                "timeZone": "Europe/London",
                "sheetCount": 2,
                "sheets": [
                    {"sheetId": 0, "title": "Data", "rowCount": 500, "columnCount": 20},
                    {"sheetId": 1, "title": "Summary", "rowCount": 100, "columnCount": 10},
                ],
            },
        ]

        with patch.object(component, "execute_action", return_value=mock_sheet_info):
            result = component.as_dataframe()

            assert isinstance(result, DataFrame)
            assert not result.empty

            assert result.iloc[0]["title"] == "Test Sheet 1"
            assert result.iloc[1]["title"] == "Test Sheet 2"
            assert result.iloc[0]["url"] == "https://docs.google.com/spreadsheets/d/random/edit"
            assert result.iloc[1]["url"] == "https://docs.google.com/spreadsheets/d/random/edit"
            assert result.iloc[0]["locale"] == "en_US"
            assert result.iloc[1]["locale"] == "en_GB"

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
