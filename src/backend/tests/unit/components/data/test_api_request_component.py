from pathlib import Path

import aiofiles
import aiofiles.os
import httpx
import pytest
import respx
from httpx import Response
from langflow.components.data import APIRequestComponent
from langflow.schema import Data
from langflow.schema.dotdict import dotdict

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
            "url_input": "https://example.com/api/test",
            "method": "GET",
            "headers": [{"key": "User-Agent", "value": "test-agent"}],
            "body": [],
            "timeout": 30,
            "follow_redirects": True,
            "save_to_file": False,
            "include_httpx_metadata": False,
            "mode": "URL",
            "curl_input": "",
            "query_params": {},
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
        build_config = dotdict(
            {
                "method": {"value": ""},
                "url_input": {"value": ""},
                "headers": {"value": []},
                "body": {"value": []},
            }
        )
        new_build_config = component.parse_curl(curl_cmd, build_config.copy())

        assert new_build_config["method"]["value"] == "GET"
        assert new_build_config["url_input"]["value"] == "https://example.com/api/test"
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
        assert result.data["result"] == binary_content

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
        assert result.data["status_code"] == 500
        assert "Request timed out" in result.data["error"]

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

    async def test_make_api_requests(self, component):
        # Test making API requests
        url = "https://example.com/api/test"
        response_data = {"key": "value"}

        with respx.mock:
            respx.get(url).mock(return_value=Response(200, json=response_data))

            result = await component.make_api_requests()

            assert isinstance(result, Data)
            assert result.data["source"] == url
            assert result.data["result"]["key"] == "value"

    async def test_invalid_urls(self, component):
        # Test invalid URL handling
        component.url_input = "not_a_valid_url"
        with pytest.raises(ValueError, match="Invalid URL provided"):
            await component.make_api_requests()

    async def test_update_build_config(self, component):
        # Test build config updates
        build_config = dotdict(
            {
                "method": {"value": "GET", "advanced": False},
                "url_input": {"value": "", "advanced": False},
                "headers": {"value": [], "advanced": True},
                "body": {"value": [], "advanced": True},
                "mode": {"value": "URL", "advanced": False},
                "curl_input": {"value": "curl -X GET https://example.com/api/test", "advanced": True},
                "timeout": {"value": 30, "advanced": True},
                "follow_redirects": {"value": True, "advanced": True},
                "save_to_file": {"value": False, "advanced": True},
                "include_httpx_metadata": {"value": False, "advanced": True},
                "query_params": {"value": {}, "advanced": True},
            }
        )

        # Test URL mode
        updated = component.update_build_config(build_config=build_config.copy(), field_value="URL", field_name="mode")
        assert updated["curl_input"]["advanced"] is True
        assert updated["url_input"]["advanced"] is False

        # Set the component's curl_input attribute to match the build_config before switching to cURL mode
        component.curl_input = build_config["curl_input"]["value"]
        # Test cURL mode
        updated = component.update_build_config(build_config=build_config.copy(), field_value="cURL", field_name="mode")
        assert updated["curl_input"]["advanced"] is False
        assert updated["url_input"]["advanced"] is True

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

    async def test_response_info(self, component):
        # Test response info handling
        url = "https://example.com/api/test"
        request = httpx.Request("GET", url)
        response = Response(200, text="test content", request=request)
        is_binary, file_path = await component._response_info(response, with_file_path=True)

        assert not is_binary
        assert file_path is not None
        assert file_path.suffix == ".txt"

        # Test binary response
        binary_response = Response(
            200, content=b"binary content", headers={"Content-Type": "application/octet-stream"}, request=request
        )
        is_binary, file_path = await component._response_info(binary_response, with_file_path=True)

        assert is_binary
        assert file_path is not None
        assert file_path.suffix == ".bin"
