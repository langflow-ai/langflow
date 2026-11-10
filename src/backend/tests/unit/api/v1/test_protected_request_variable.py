"""Run headers cannot redirect a protected flow-author destination."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langflow.api.utils import extract_global_variables_from_headers
from lfx.custom.custom_component.custom_component import CustomComponent


@pytest.mark.asyncio
async def test_bing_url_header_does_not_override_owner_global_variable():
    request_variables = extract_global_variables_from_headers(
        {"X-LANGFLOW-GLOBAL-VAR-BING_SEARCH_URL": "https://attacker.example/search"}
    )
    component_class = type("BingSearchAPIComponent", (SimpleNamespace,), {})
    user_id = uuid.uuid4()
    component = component_class(
        graph=SimpleNamespace(context={"request_variables": request_variables}),
        user_id=user_id,
        _user_id=user_id,
    )
    with patch("lfx.custom.custom_component.custom_component.get_variable_service") as service:
        service.return_value.get_variable = AsyncMock(return_value="https://api.bing.microsoft.com/v7.0/search")
        result = await CustomComponent.get_variable(component, "BING_SEARCH_URL", "bing_search_url", object())

    assert result == "https://api.bing.microsoft.com/v7.0/search"
    service.return_value.get_variable.assert_awaited_once()
