from unittest.mock import Mock, patch

from langflow.services.database.models.flow.model import Flow


def test_api_exception():
    from langflow.exceptions.api import APIException, ExceptionBody

    mock_exception = Exception("Test exception")
    mock_flow = Mock(spec=Flow)
    mock_outdated_components = ["component1", "component2"]
    mock_suggestion_message = "Update component1, component2"
    mock_component_versions = {
        "component1": "1.0",
        "component2": "1.0",
    }
    # Expected result

    with patch(
        "langflow.services.database.models.flow.utils.get_outdated_components", return_value=mock_outdated_components
    ):
        with patch("langflow.api.utils.get_suggestion_message", return_value=mock_suggestion_message):
            with patch(
                "langflow.services.database.models.flow.utils.get_components_versions",
                return_value=mock_component_versions,
            ):
                # Create an APIException instance
                api_exception = APIException(mock_exception, mock_flow)

                # Expected body
                expected_body = ExceptionBody(
                    message="Test exception",
                    suggestion="The flow contains 2 outdated components. We recommend updating the following components: component1, component2.",
                )

                # Assert the status code
                assert api_exception.status_code == 500

                # Assert the detail
                assert api_exception.detail == expected_body.model_dump_json()


def test_api_exception_no_flow():
    from langflow.exceptions.api import APIException, ExceptionBody

    # Mock data
    mock_exception = Exception("Test exception")

    # Create an APIException instance without a flow
    api_exception = APIException(mock_exception)

    # Expected body
    expected_body = ExceptionBody(message="Test exception")

    # Assert the status code
    assert api_exception.status_code == 500

    # Assert the detail
    assert api_exception.detail == expected_body.model_dump_json()
