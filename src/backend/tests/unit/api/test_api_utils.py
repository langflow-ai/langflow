from unittest.mock import patch

from langflow.api.utils import get_suggestion_message
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
