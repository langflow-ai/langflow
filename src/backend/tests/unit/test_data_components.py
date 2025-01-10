import pytest
from langflow.components import data


@pytest.fixture
def api_request():
    # This fixture provides an instance of APIRequest for each test case
    return data.APIRequestComponent()


def test_parse_curl(api_request):
    # Arrange
    field_value = (
        "curl -X GET https://example.com/api/test -H 'Content-Type: application/json' -d '{\"key\": \"value\"}'"
    )
    build_config = {
        "method": {"value": ""},
        "urls": {"value": []},
        "headers": {},
        "body": {},
    }
    # Act
    new_build_config = api_request.parse_curl(field_value, build_config.copy())

    # Assert
    assert new_build_config["method"]["value"] == "GET"
    assert new_build_config["urls"]["value"] == ["https://example.com/api/test"]
    assert new_build_config["headers"]["value"] == {"Content-Type": "application/json"}
    assert new_build_config["body"]["value"] == {"key": "value"}
