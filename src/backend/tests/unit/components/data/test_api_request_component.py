from pathlib import Path
from unittest.mock import patch

import aiofiles
import aiofiles.os
import httpx
import pytest
import respx
from httpx import Response
from langflow.components.data import APIRequestComponent
from langflow.schema import Data, DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestAPIRequestComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return APIRequestComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "urls": ["https://example.com/api/test"],
            "method": "GET",
            "headers": [],
            "body": [],
            "timeout": 5,
            "follow_redirects": True,
            "save_to_file": False,
            "include_httpx_metadata": False,
            "use_curl": False,
            "curl": "",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    async def component(self, component_class, default_kwargs):
        """Return a component instance."""
        return component_class(**default_kwargs)

    async def test_parse_curl(self, component):
        # Test basic curl command parsing
        curl_cmd = (
            "curl -X GET https://example.com/api/test -H 'Content-Type: application/json' -d '{\"key\": \"value\"}'"
        )
        build_config = {
            "method": {"value": ""},
            "urls": {"value": []},
            "headers": {},
            "body": {},
        }
        new_build_config = component.parse_curl(curl_cmd, build_config.copy())

        assert new_build_config["method"]["value"] == "GET"
        assert new_build_config["urls"]["value"] == ["https://example.com/api/test"]
        assert new_build_config["headers"]["value"] == [{"key": "Content-Type", "value": "application/json"}]
        assert new_build_config["body"]["value"] == [{"key": "key", "value": "value"}]

    @respx.mock
    async def test_make_request_success(self, component):
        # Test successful request with JSON response
        url = "https://example.com/api/test"
        response_data = {"key": "value"}
        respx.get(url).mock(return_value=Response(200, json=response_data))

        result = await component.make_request(
            client=httpx.AsyncClient(),
            method="GET",
            url=url,
        )

        assert isinstance(result, Data)
        assert result.data["source"] == url
        # The JSON response is nested in the 'result' key
        assert "result" in result.data
        assert result.data["result"]["key"] == "value"

    @respx.mock
    async def test_make_request_with_metadata(self, component):
        # Test request with metadata included
        url = "https://example.com/api/test"
        headers = {"Custom-Header": "Value"}
        response_data = {"key": "value"}
        respx.get(url).mock(return_value=Response(200, json=response_data, headers=headers))

        result = await component.make_request(
            client=httpx.AsyncClient(),
            method="GET",
            url=url,
            include_httpx_metadata=True,
        )

        assert isinstance(result, Data)
        assert result.data["source"] == url
        assert result.data["status_code"] == 200
        assert result.data["response_headers"]["custom-header"] == "Value"

    @respx.mock
    async def test_make_request_save_to_file(self, component):
        # Test saving response to file
        url = "https://example.com/api/test"
        content = "Test content"
        respx.get(url).mock(return_value=Response(200, text=content))

        result = await component.make_request(
            client=httpx.AsyncClient(),
            method="GET",
            url=url,
            save_to_file=True,
        )

        assert isinstance(result, Data)
        assert "file_path" in result.data
        file_path = Path(result.data["file_path"])

        # Use async file operations
        assert await aiofiles.os.path.exists(file_path)
        async with aiofiles.open(file_path) as f:
            saved_content = await f.read()
        assert saved_content == content

        # Cleanup using async operation
        await aiofiles.os.remove(file_path)

    @respx.mock
    async def test_make_request_binary_response(self, component):
        # Test handling binary response
        url = "https://example.com/api/binary"
        binary_content = b"Binary content"
        headers = {"Content-Type": "application/octet-stream"}
        respx.get(url).mock(return_value=Response(200, content=binary_content, headers=headers))

        result = await component.make_request(
            client=httpx.AsyncClient(),
            method="GET",
            url=url,
        )

        assert isinstance(result, Data)
        assert result.data["source"] == url

    @respx.mock
    async def test_make_request_timeout(self, component):
        # Test request timeout
        url = "https://example.com/api/test"
        respx.get(url).mock(side_effect=httpx.TimeoutException("Request timed out"))

        result = await component.make_request(
            client=httpx.AsyncClient(),
            method="GET",
            url=url,
            timeout=1,
        )

        assert isinstance(result, Data)
        assert result.data["status_code"] == 408
        assert result.data["error"] == "Request timed out"

    @respx.mock
    async def test_make_request_with_redirects(self, component):
        # Test handling redirects
        url = "https://example.com/api/test"
        redirect_url = "https://example.com/api/redirect"
        final_data = {"key": "value"}

        respx.get(url).mock(return_value=Response(303, headers={"Location": redirect_url}))
        respx.get(redirect_url).mock(return_value=Response(200, json=final_data))

        result = await component.make_request(
            client=httpx.AsyncClient(),
            method="GET",
            url=url,
            include_httpx_metadata=True,
            follow_redirects=True,
        )

        assert isinstance(result, Data)
        assert result.data["source"] == url
        assert result.data["status_code"] == 200
        assert result.data["redirection_history"] == [{"url": redirect_url, "status_code": 303}]

    async def test_process_headers(self, component):
        # Test header processing
        headers_list = [
            {"key": "Content-Type", "value": "application/json"},
            {"key": "Authorization", "value": "Bearer token"},
        ]
        processed = component._process_headers(headers_list)
        assert processed == {
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
        }

        # Test invalid headers
        assert component._process_headers(None) == {}
        assert component._process_headers([{"invalid": "format"}]) == {}

    async def test_process_body(self, component):
        # Test body processing
        # Test dictionary body
        dict_body = {"key": "value", "nested": {"inner": "value"}}
        assert component._process_body(dict_body) == dict_body

        # Test string body
        json_str = '{"key": "value"}'
        assert component._process_body(json_str) == {"key": "value"}

        # Test list body
        list_body = [{"key": "key1", "value": "value1"}, {"key": "key2", "value": "value2"}]
        assert component._process_body(list_body) == {"key1": "value1", "key2": "value2"}

        # Test invalid body
        assert component._process_body(None) == {}
        assert component._process_body([{"invalid": "format"}]) == {}

    async def test_add_query_params(self, component):
        # Test query parameter handling
        url = "https://example.com/api/test"
        params = {"param1": "value1", "param2": "value2"}
        result = component.add_query_params(url, params)
        assert "param1=value1" in result
        assert "param2=value2" in result

        # Test with existing query params
        url_with_params = "https://example.com/api/test?existing=true"
        result = component.add_query_params(url_with_params, params)
        assert "existing=true" in result
        assert "param1=value1" in result
        assert "param2=value2" in result

    async def test_output_formats(self, component):
        # Test different output formats
        with patch.object(component, "make_requests") as mock_make_requests:
            mock_make_requests.return_value = [Data(data={"key": "value"})]

            # Test DataFrame output
            df_result = await component.as_dataframe()
            assert isinstance(df_result, DataFrame)

            # Test Data output - to_data returns a list of Data objects
            test_data = {"test": "value"}
            data_result = component.to_data(test_data)
            assert isinstance(data_result, list)
            assert all(isinstance(item, Data) for item in data_result)

    async def test_invalid_urls(self, component):
        # Test invalid URL handling
        component.urls = ["not_a_valid_url"]
        with pytest.raises(ValueError, match="Invalid URLs provided"):
            await component.make_requests()

    async def test_update_build_config(self, component):
        # Test build config updates
        build_config = {
            "method": {"value": "GET", "advanced": False},
            "urls": {"value": [], "advanced": False},
            "headers": {"value": [], "advanced": True},
            "body": {"value": [], "advanced": True},
            "use_curl": {"value": False, "advanced": False},
            "curl": {"value": "", "advanced": True},
            "timeout": {"value": 5, "advanced": True},
            "follow_redirects": {"value": True, "advanced": True},
            "save_to_file": {"value": False, "advanced": True},
            "include_httpx_metadata": {"value": False, "advanced": True},
            "query_params": {"value": {}, "advanced": True},
        }

        # Test curl mode update
        updated = component.update_build_config(
            build_config=build_config.copy(), field_value=True, field_name="use_curl"
        )
        assert updated["curl"]["advanced"] is False
        assert updated["urls"]["advanced"] is True

        # Test method update
        updated = component.update_build_config(
            build_config=build_config.copy(), field_value="POST", field_name="method"
        )
        assert updated["body"]["advanced"] is False

    @respx.mock
    async def test_error_handling(self, component):
        # Test various error scenarios
        url = "https://example.com/api/test"

        # Test connection error
        respx.get(url).mock(side_effect=httpx.ConnectError("Connection failed"))
        result = await component.make_request(
            client=httpx.AsyncClient(),
            method="GET",
            url=url,
        )
        assert result.data["status_code"] == 500
        assert "Connection failed" in result.data["error"]

        # Test invalid method
        with pytest.raises(ValueError, match="Unsupported method"):
            await component.make_request(
                client=httpx.AsyncClient(),
                method="INVALID",
                url=url,
            )
