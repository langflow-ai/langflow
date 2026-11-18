"""Agent tools retain operator settings, connections, and inbound reply context."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from conftest import DEBUG, PHONES, TOKEN, GraphTransport, Resolver
from langchain_core.tools import ToolException
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.base import BaseConnectionResolverService, ConnectionAccessPolicy
from lfx_whatsapp import WhatsAppReplyComponent, WhatsAppSendTemplateComponent, WhatsAppSendTextComponent
from pydantic import TypeAdapter

EVENT = {
    "provider": "whatsapp",
    "event": "message",
    "phone_id": "333",
    "waba_id": "222",
    "message_id": "wamid.received",
    "sender": "15551234567",
}


class RecordingResolver(BaseConnectionResolverService):
    def __init__(self):
        super().__init__()
        self.requests = []
        self.set_ready()

    async def _get_access_policy(self, _request):
        return ConnectionAccessPolicy(owner_kind="user", connection_owner_id="owner")

    async def _resolve(self, request, _policy):
        self.requests.append(request)
        return await Resolver().resolve(request)


@pytest.fixture
def tool_context(monkeypatch):
    resolver = RecordingResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        flow_id=None,
        run_id=None,
    )
    return SimpleNamespace(vertex=SimpleNamespace(graph=graph, outputs=[]), resolver=resolver)


@pytest.mark.parametrize(
    ("component_class", "parameters"),
    [
        (WhatsAppSendTextComponent, {"to", "text"}),
        (WhatsAppSendTemplateComponent, {"to", "template_name", "language", "body_parameters"}),
        (WhatsAppReplyComponent, {"text"}),
    ],
)
async def test_action_tool_schema_exposes_only_runtime_content(component_class, parameters):
    component = component_class(connection="whatsapp/business")

    [tool] = await component.to_toolkit()

    assert set(tool.args_schema.model_fields) == parameters
    for field in tool.args_schema.model_fields.values():
        if not field.is_required():
            assert TypeAdapter(field.annotation).validate_python(field.default) == field.default


async def test_text_tool_resolves_the_same_connection_and_sends_each_runtime_message(monkeypatch, tool_context):
    responses = [DEBUG, PHONES, {"messages": [{"id": "wamid.first"}]}]
    responses += [DEBUG, PHONES, {"messages": [{"id": "wamid.second"}]}]
    transport = GraphTransport(responses).install(monkeypatch)
    component = WhatsAppSendTextComponent(_vertex=tool_context.vertex, connection="whatsapp/business")
    [tool] = await component.to_toolkit()

    for to, text, message_id in [
        ("15551234567", "First message", "wamid.first"),
        ("15557654321", "Second message", "wamid.second"),
    ]:
        result = await tool.ainvoke({"to": to, "text": text})
        assert result["accepted"] is True
        assert result["message_id"] == message_id
        assert TOKEN not in repr(result)

    sends = [request for request in transport.requests if request.method == "POST"]
    assert len(sends) == 2
    assert [json.loads(request.content)["text"]["body"] for request in sends] == ["First message", "Second message"]
    assert [json.loads(request.content)["to"] for request in sends] == ["15551234567", "15557654321"]
    assert {request.url.path for request in sends} == {"/v25.0/333/messages"}
    assert {request.headers["authorization"] for request in sends} == {f"Bearer {TOKEN}"}
    assert {request.ref.name for request in tool_context.resolver.requests} == {"business"}
    assert {request.principal.user_id for request in tool_context.resolver.requests} == {"owner"}


async def test_reply_tool_uses_the_configured_inbound_event(monkeypatch, tool_context):
    transport = GraphTransport([DEBUG, PHONES, {"messages": [{"id": "wamid.reply"}]}]).install(monkeypatch)
    component = WhatsAppReplyComponent(
        _vertex=tool_context.vertex,
        connection="whatsapp/business",
        event={"payload": {"data": EVENT}},
    )
    [tool] = await component.to_toolkit()

    result = await tool.ainvoke({"text": "Your update is ready", "event": {**EVENT, "sender": "15557654321"}})

    assert result["accepted"] is True
    payload = json.loads(transport.requests[-1].content)
    assert payload["to"] == EVENT["sender"]
    assert payload["context"] == {"message_id": EVENT["message_id"]}
    assert payload["text"]["body"] == "Your update is ready"


async def test_reply_tool_still_rejects_context_from_another_phone(monkeypatch, tool_context):
    transport = GraphTransport([]).install(monkeypatch)
    component = WhatsAppReplyComponent(
        _vertex=tool_context.vertex,
        connection="whatsapp/business",
        event={**EVENT, "phone_id": "444"},
    )
    [tool] = await component.to_toolkit()

    with pytest.raises(ToolException, match="same WhatsApp"):
        await tool.coroutine(text="Reply")
    assert transport.requests == []


async def test_template_tool_sends_positional_parameters_as_runtime_arguments(monkeypatch, tool_context):
    transport = GraphTransport([DEBUG, PHONES, {"messages": [{"id": "wamid.template"}]}]).install(monkeypatch)
    component = WhatsAppSendTemplateComponent(_vertex=tool_context.vertex, connection="whatsapp/business")
    [tool] = await component.to_toolkit()

    result = await tool.ainvoke(
        {"to": "15551234567", "template_name": "order_update", "language": "en_US", "body_parameters": ["123"]}
    )

    assert result["accepted"] is True
    assert json.loads(transport.requests[-1].content)["template"] == {
        "name": "order_update",
        "language": {"code": "en_US"},
        "components": [{"type": "body", "parameters": [{"type": "text", "text": "123"}]}],
    }


@pytest.mark.parametrize(
    ("template_name", "language", "message"),
    [("Hello World", "en_US", "approved template name"), ("order_update", "Brazil", "template language")],
)
async def test_template_tool_retains_input_validation(monkeypatch, tool_context, template_name, language, message):
    transport = GraphTransport([]).install(monkeypatch)
    component = WhatsAppSendTemplateComponent(_vertex=tool_context.vertex, connection="whatsapp/business")
    [tool] = await component.to_toolkit()

    with pytest.raises(ToolException, match=message):
        await tool.coroutine(to="15551234567", template_name=template_name, language=language, body_parameters=[])
    assert transport.requests == []


async def test_template_tool_keeps_provider_approval_errors_sanitized(monkeypatch, tool_context):
    transport = GraphTransport(
        [DEBUG, PHONES, (400, {"error": {"code": 132001, "message": TOKEN, "error_data": {"details": TOKEN}}})]
    ).install(monkeypatch)
    component = WhatsAppSendTemplateComponent(_vertex=tool_context.vertex, connection="whatsapp/business")
    [tool] = await component.to_toolkit()

    with pytest.raises(ToolException, match="template name or language") as caught:
        await tool.coroutine(to="15551234567", template_name="order_update", language="en_US", body_parameters=[])
    assert TOKEN not in str(caught.value)
    assert len(transport.requests) == 3
