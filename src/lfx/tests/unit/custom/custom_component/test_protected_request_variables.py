"""Request variables must not redirect protected flow-author fields."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.custom.custom_component.custom_component import CustomComponent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("component_type", "field"),
    [("BingSearchAPIComponent", "bing_search_url"), ("SQLComponent", "database_url")],
)
async def test_request_variable_cannot_override_protected_field(component_type: str, field: str):
    component_class = type(component_type, (SimpleNamespace,), {})
    user_id = uuid.uuid4()
    component = component_class(
        graph=SimpleNamespace(context={"request_variables": {"DESTINATION": "https://attacker.example"}}),
        user_id=user_id,
        _user_id=user_id,
    )
    stored_value = "https://author.example"
    with patch("lfx.custom.custom_component.custom_component.get_variable_service") as service:
        service.return_value.get_variable = AsyncMock(return_value=stored_value)
        result = await CustomComponent.get_variable(component, "DESTINATION", field, object())

    assert result == stored_value
    service.return_value.get_variable.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_variable_still_overrides_ordinary_field():
    component_class = type("BingSearchAPIComponent", (SimpleNamespace,), {})
    component = component_class(graph=SimpleNamespace(context={"request_variables": {"QUERY": "from caller"}}))
    assert await CustomComponent.get_variable(component, "QUERY", "query", object()) == "from caller"
