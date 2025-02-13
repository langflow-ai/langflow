import os

import pytest

from langflow.components.Notion import NotionListPages
from tests.base import ComponentTestBaseWithClient

API_KEY = "NotionSecret"


@pytest.mark.skipif(
    not os.environ.get(API_KEY),
    reason="Environment variable '{API_KEY}' is not defined.",
)
@pytest.mark.usefixtures("client")
class TestNotionListPagesComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotionListPages

    @pytest.fixture
    def default_kwargs(self):
        return {
            "notion_secret": os.environ.get(API_KEY),
            "database_id": "database_id_example",
            "query_json": (
                '{"filter": {"property": "Status", "select": {"equals": "Done"}}, '
                '"sorts": [{"timestamp": "created_time", "direction": "descending"}]}'
            ),
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "notion", "file_name": "NotionListPages"},
        ]

    async def test_run_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert isinstance(result, list)
        assert all(isinstance(record, dict) for record in result)

    async def test_run_model_invalid_json(self, component_class, default_kwargs):
        component = component_class(
            notion_secret=default_kwargs.get("notion_secret"),
            database_id="database_id_example",
            query_json="invalid_json",
        )
        result = component.run_model()
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Invalid JSON format for query" in result[0].text

    async def test_run_model_request_exception(self, component_class, default_kwargs, mocker):
        mocker.patch("requests.post", side_effect=Exception("Request failed"))
        component = component_class(
            notion_secret=default_kwargs.get("notion_secret"), database_id="database_id_example"
        )
        result = component.run_model()
        assert isinstance(result, list)
        assert len(result) == 1
        assert "An unexpected error occurred" in result[0].text

    async def test_run_model_key_error(self, component_class, default_kwargs, mocker):
        mocker.patch("requests.post", return_value=mocker.Mock(status_code=200, json=dict))
        component = component_class(
            notion_secret=default_kwargs.get("notion_secret"),
            database_id="database_id_example",
        )
        result = component.run_model()
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Unexpected response format from Notion API" in result[0].text
