"""Request variables must not redirect protected flow-author fields."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.graph import Graph


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
        service.return_value.get_account_bound_variable = AsyncMock(return_value=None)
        service.return_value.get_variable = AsyncMock(return_value=stored_value)
        result = await CustomComponent.get_variable(component, "DESTINATION", field, object())

    assert result == stored_value
    service.return_value.get_variable.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_variable_still_overrides_ordinary_field():
    component_class = type("BingSearchAPIComponent", (SimpleNamespace,), {})
    component = component_class(graph=SimpleNamespace(context={"request_variables": {"QUERY": "from caller"}}))
    assert await CustomComponent.get_variable(component, "QUERY", "query", object()) == "from caller"


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", [None, "00000000-0000-0000-0000-000000000001"])
async def test_account_bound_variable_uses_graph_user_before_request_override(user_id):
    chat_input = ChatInput(_id="chat-input", input_value="hello")
    chat_output = ChatOutput(_id="chat-output")
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(
        chat_input,
        chat_output,
        user_id=user_id,
        context={"request_variables": {"QUERY": "from caller"}},
    )
    component = graph.get_vertex("chat-input").custom_component
    session = object()
    with patch("lfx.custom.custom_component.custom_component.get_variable_service") as service:
        resolve_bound = service.return_value.get_account_bound_variable = AsyncMock(
            return_value=SimpleNamespace(value="from account")
        )
        result = await component.get_variable("QUERY", "input_value", session)

    if user_id is None:
        assert result == "from caller"
        resolve_bound.assert_not_awaited()
    else:
        assert result == "from account"
        resolve_bound.assert_awaited_once_with(user_id=user_id, name="QUERY", field="input_value", session=session)
