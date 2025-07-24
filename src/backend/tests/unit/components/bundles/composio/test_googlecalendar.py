from unittest.mock import MagicMock, patch

import pytest
from composio import Action

from lfx.components.composio.googlecalendar_composio import ComposioGoogleCalendarAPIComponent
from lfx.schema.dataframe import DataFrame
from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient

from .test_base import MockComposioToolSet


class MockAction:
    GOOGLECALENDAR_CREATE_EVENT = "GOOGLECALENDAR_CREATE_EVENT"
    GOOGLECALENDAR_LIST_CALENDARS = "GOOGLECALENDAR_LIST_CALENDARS"


class TestGoogleCalendarComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def mock_composio_toolset(self):
        with patch("lfx.base.composio.composio_base.ComposioToolSet", MockComposioToolSet):
            yield

    @pytest.fixture
    def component_class(self):
        return ComposioGoogleCalendarAPIComponent

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
        assert component.display_name == "Google Calendar"
        assert component.app_name == "googlecalendar"
        assert "GOOGLECALENDAR_CREATE_EVENT" in component._actions_data
        assert "GOOGLECALENDAR_LIST_CALENDARS" in component._actions_data

    def test_execute_action_create_event(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "GOOGLECALENDAR_CREATE_EVENT", MockAction.GOOGLECALENDAR_CREATE_EVENT)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Create Event"}]
        component.GOOGLECALENDAR_CREATE_EVENT_attendees = "test@example.com"
        component.GOOGLECALENDAR_CREATE_EVENT_start_datetime = "2025-01-16T15:00:00"
        component.GOOGLECALENDAR_CREATE_EVENT_summary = "test title"

        component._actions_data = {
            "GOOGLECALENDAR_CREATE_EVENT": {
                "display_name": "Create Event",
                "action_fields": [
                    "GOOGLECALENDAR_CREATE_EVENT_description",
                    "GOOGLECALENDAR_CREATE_EVENT_eventType",
                    "GOOGLECALENDAR_CREATE_EVENT_create_meeting_room",
                    "GOOGLECALENDAR_CREATE_EVENT_guestsCanSeeOtherGuests",
                    "GOOGLECALENDAR_CREATE_EVENT_guestsCanInviteOthers",
                    "GOOGLECALENDAR_CREATE_EVENT_location",
                    "GOOGLECALENDAR_CREATE_EVENT_summary",
                    "GOOGLECALENDAR_CREATE_EVENT_transparency",
                    "GOOGLECALENDAR_CREATE_EVENT_visibility",
                    "GOOGLECALENDAR_CREATE_EVENT_timezone",
                    "GOOGLECALENDAR_CREATE_EVENT_recurrence",
                    "GOOGLECALENDAR_CREATE_EVENT_guests_can_modify",
                    "GOOGLECALENDAR_CREATE_EVENT_attendees",
                    "GOOGLECALENDAR_CREATE_EVENT_send_updates",
                    "GOOGLECALENDAR_CREATE_EVENT_start_datetime",
                    "GOOGLECALENDAR_CREATE_EVENT_event_duration_hour",
                    "GOOGLECALENDAR_CREATE_EVENT_event_duration_minutes",
                    "GOOGLECALENDAR_CREATE_EVENT_calendar_id",
                ],
            }
        }

        result = component.execute_action()
        assert result == "mocked response"

    def test_execute_action_list_calendars(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "GOOGLECALENDAR_LIST_CALENDARS", MockAction.GOOGLECALENDAR_LIST_CALENDARS)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Google Calendars"}]
        component.GOOGLECALENDAR_LIST_CALENDARS_max_results = 1

        component._actions_data = {
            "GOOGLECALENDAR_LIST_CALENDARS": {
                "display_name": "List Google Calendars",
                "action_fields": [
                    "GOOGLECALENDAR_LIST_CALENDARS_max_results",
                    "GOOGLECALENDAR_LIST_CALENDARS_min_access_role",
                    "GOOGLECALENDAR_LIST_CALENDARS_page_token",
                    "GOOGLECALENDAR_LIST_CALENDARS_show_deleted",
                    "GOOGLECALENDAR_LIST_CALENDARS_show_hidden",
                    "GOOGLECALENDAR_LIST_CALENDARS_sync_token",
                ],
            }
        }

        mock_toolset = MagicMock()
        mock_toolset.execute_action.return_value = {"successful": True, "data": {"messages": "mocked response"}}

        with patch.object(component, "_build_wrapper", return_value=mock_toolset):
            result = component.execute_action()
            assert result == "mocked response"

    def test_execute_action_invalid_action(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "Invalid Action"}]

        with pytest.raises(ValueError, match="Invalid action: Invalid Action"):
            component.execute_action()

    def test_as_dataframe(self, component_class, default_kwargs, monkeypatch):
        monkeypatch.setattr(Action, "GOOGLECALENDAR_LIST_CALENDARS", MockAction.GOOGLECALENDAR_LIST_CALENDARS)

        component = component_class(**default_kwargs)
        component.api_key = "test_key"
        component.action = [{"name": "List Google Calendars"}]
        component.GOOGLECALENDAR_LIST_CALENDARS_max_results = 10

        mock_emails = [
            {
                "kind": "test kind 1",
                "etag": "1",
                "id": "1",
                "summary": "test summary 1",
                "description": "test description 1",
            },
            {
                "kind": "test kind 2",
                "etag": "2",
                "id": "2",
                "summary": "test summary 2",
                "description": "test description 2",
            },
        ]

        with patch.object(component, "execute_action", return_value=mock_emails):
            result = component.as_dataframe()

            assert isinstance(result, DataFrame)

            assert not result.empty

            data_str = str(result)
            assert "test summary 2" in data_str

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
