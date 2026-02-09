from unittest.mock import patch

from langflow.api.utils import get_suggestion_message, remove_api_keys
from langflow.services.database.models.flow.utils import get_outdated_components
from langflow.utils.version import get_version_info


def test_get_suggestion_message():
    # Test case 1: No outdated components
    assert get_suggestion_message([]) == "The flow contains no outdated components."

    # Test case 2: One outdated component
    assert (
        get_suggestion_message(["component1"])
        == "The flow contains 1 outdated component. We recommend updating the following component: component1."
    )

    # Test case 3: Multiple outdated components
    outdated_components = ["component1", "component2", "component3"]
    expected_message = (
        "The flow contains 3 outdated components. "
        "We recommend updating the following components: component1, component2, component3."
    )
    assert get_suggestion_message(outdated_components) == expected_message


def test_get_outdated_components():
    # Mock data
    flow = "mock_flow"
    version = get_version_info()["version"]
    mock_component_versions = {
        "component1": version,
        "component2": version,
        "component3": "2.0",
    }
    # Expected result
    expected_outdated_components = ["component3"]

    with patch(
        "langflow.services.database.models.flow.utils.get_components_versions", return_value=mock_component_versions
    ):
        # Call the function with the mock flow
        result = get_outdated_components(flow)
        # Assert the result is as expected
        assert result == expected_outdated_components


def test_remove_api_keys():
    """Test that remove_api_keys properly removes API keys and handles various template structures.

    This test validates the fix for the bug where remove_api_keys would crash when
    encountering template values without 'name' keys (e.g., Note components with
    only backgroundColor).
    """
    # Test case 1: Flow with API key that should be removed
    flow_with_api_key = {
        "data": {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "name": "api_key",
                                    "value": "secret-123",
                                    "password": True,
                                },
                                "openai_api_key": {
                                    "name": "openai_api_key",
                                    "value": "sk-abc123",
                                    "password": True,
                                },
                            }
                        }
                    }
                }
            ]
        }
    }

    result = remove_api_keys(flow_with_api_key)
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["openai_api_key"]["value"] is None

    # Test case 2: Flow with Note component (no 'name' key) - this is the bug fix
    flow_with_note = {
        "data": {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "backgroundColor": {"value": "#ffffff"},  # No 'name' key
                                "text": {"value": "Test note"},  # No 'name' key
                            }
                        }
                    }
                }
            ]
        }
    }

    # This should not raise an error (the bug that was fixed)
    result = remove_api_keys(flow_with_note)
    # Values should be preserved since they're not API keys
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["backgroundColor"]["value"] == "#ffffff"
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["text"]["value"] == "Test note"

    # Test case 3: Mixed flow with both API keys and template values without 'name'
    mixed_flow = {
        "data": {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "backgroundColor": {"value": "#ffffff"},  # No 'name' key
                                "api_token": {
                                    "name": "api_token",
                                    "value": "token-xyz",
                                    "password": True,
                                },
                                "regular_field": {
                                    "name": "regular_field",
                                    "value": "keep-this",
                                },
                            }
                        }
                    }
                }
            ]
        }
    }

    result = remove_api_keys(mixed_flow)
    # backgroundColor should be preserved (no 'name' key)
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["backgroundColor"]["value"] == "#ffffff"
    # API token should be removed
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["api_token"]["value"] is None
    # Regular field should be kept
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["regular_field"]["value"] == "keep-this"

    # Test case 4: Flow with auth_token (password field but not password=True)
    flow_with_non_password_api = {
        "data": {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "name": "api_key",
                                    "value": "should-not-be-removed",
                                    "password": False,  # Not a password field
                                },
                            }
                        }
                    }
                }
            ]
        }
    }

    result = remove_api_keys(flow_with_non_password_api)
    # Should NOT be removed because password is False
    assert result["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "should-not-be-removed"

    # Test case 5: Empty flow
    empty_flow = {"data": {"nodes": []}}
    result = remove_api_keys(empty_flow)
    assert result == empty_flow
