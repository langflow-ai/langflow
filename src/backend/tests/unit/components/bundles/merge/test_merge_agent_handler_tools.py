"""Unit tests for Merge Agent Handler bundle utilities."""

import pytest
from lfx.components.merge.merge_agent_handler_tool import MergeAgentHandlerToolsComponent


class _FakeValidationError:
    def errors(self):
        return [
            {"type": "missing", "loc": ("input", "cursor")},
            {"type": "missing", "loc": ("input", "id")},
        ]


@pytest.mark.unit
class TestMergeAgentHandlerToolsComponent:
    """Tests for Merge Agent Handler tool helper behavior."""

    def test_tool_pack_option_map_includes_connectors(self):
        packs = [
            {
                "id": "tp_1234567890ab",
                "name": "HR Pack",
                "connectors": [{"name": "Greenhouse", "slug": "greenhouse"}, {"slug": "workday"}],
            }
        ]

        option_map = MergeAgentHandlerToolsComponent._tool_pack_option_map(packs)

        assert len(option_map) == 1
        label = next(iter(option_map.keys()))
        assert "HR Pack" in label
        assert "Apps:" in label
        assert "Greenhouse" in label
        assert "workday" in label
        assert option_map[label] == "tp_1234567890ab"

    def test_registered_user_option_map_includes_authenticated_connectors(self):
        users = [
            {
                "id": "ru_1234567890ab",
                "origin_user_name": "Taylor",
                "authenticated_connectors": ["salesforce", "jira", "salesforce"],
            }
        ]

        option_map = MergeAgentHandlerToolsComponent._registered_user_option_map(users)

        assert len(option_map) == 1
        label = next(iter(option_map.keys()))
        assert "Taylor" in label
        assert "Connected:" in label
        assert "salesforce" in label
        assert "jira" in label
        assert option_map[label] == "ru_1234567890ab"

    def test_validation_error_message_lists_missing_fields(self):
        message = MergeAgentHandlerToolsComponent._handle_tool_validation_error(_FakeValidationError())

        assert "Missing required fields" in message
        assert "input.cursor" in message
        assert "input.id" in message

    def test_environment_options_are_capitalized(self):
        environment_input = next(
            input_ for input_ in MergeAgentHandlerToolsComponent.inputs if input_.name == "environment"
        )

        assert set(environment_input.options) == {"Production", "Test"}
