"""WhatsApp configuration and action contracts found during provider acceptance."""

import json

import pytest
from conftest import DEBUG, PHONES, TOKEN, GraphTransport, component, lease
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.components.input_output import ChatOutput
from lfx.graph import Graph
from lfx.graph.utils import UnbuiltObject
from lfx.integrations.errors import InvalidRequestError, ProviderUnavailableError
from lfx.schema.data import Data
from lfx_whatsapp import (
    WhatsAppOnEventTriggerComponent,
    WhatsAppReplyComponent,
    WhatsAppSendTemplateComponent,
    WhatsAppSendTextComponent,
)
from lfx_whatsapp._client import WhatsAppClient
from lfx_whatsapp._components import recipient


@pytest.mark.parametrize("value", ["+1 (555) 123-4567", "1 555 123 4567", "15551234567"])
def test_recipient_accepts_common_phone_formatting(value):
    assert recipient(value) == "15551234567"


@pytest.mark.parametrize(
    "value",
    [
        "1555+1234567",
        "call15551234567",
        "1555/1234567",
        "\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19",
        "   ",
    ],
)
def test_recipient_does_not_strip_arbitrary_characters(value):
    with pytest.raises(ValueError, match="recipient"):
        recipient(value)


def test_new_reply_flows_receive_messages_without_status_runs_by_default():
    trigger = component(WhatsAppOnEventTriggerComponent)
    assert trigger.trigger_definition().config["receive_messages"] is True
    assert trigger.trigger_definition().config["receive_statuses"] is False
    trigger.set(receive_statuses=True)
    assert trigger.trigger_definition().config["receive_statuses"] is True


def _status_event(status="delivered"):
    return {
        "provider": "whatsapp",
        "event": "status",
        "phone_id": "333",
        "waba_id": "222",
        "message_id": "wamid.sent",
        "sender": "15551234567",
        "status": status,
    }


@pytest.mark.parametrize("status", ["sent", "delivered", "read", "failed", "deleted"])
async def test_reply_skips_delivery_statuses_without_resolving_a_connection_or_sending(monkeypatch, status):
    def refuse_resolution():
        pytest.fail("A delivery status must not resolve reply credentials")

    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", refuse_resolution)
    transport = GraphTransport([]).install(monkeypatch)
    action = component(
        WhatsAppReplyComponent, event=Data(data={"payload": {"data": _status_event(status)}}), text="Reply"
    )

    result = await action.build_message()

    assert result.data["skipped"] is True
    assert result.data["accepted"] is False
    assert result.data["status"] == status
    assert "Skipped" in action.status
    assert transport.requests == []


@pytest.mark.parametrize(
    "change", [{"provider": "other"}, {"status": "other"}, {"message_id": None}, {"phone_id": None}]
)
async def test_reply_still_rejects_malformed_or_non_whatsapp_status_events(change):
    action = component(WhatsAppReplyComponent, event={**_status_event(), **change}, text="Reply")
    with pytest.raises(ValueError, match=r"WhatsApp|message ID"):
        await action.build_message()


async def test_saved_both_event_types_flow_stops_the_reply_branch_for_a_delivery_status(monkeypatch):
    transport = GraphTransport([]).install(monkeypatch)
    trigger = WhatsAppOnEventTriggerComponent(_id="trigger", connection="whatsapp/business", receive_statuses=True).set(
        event_payload=json.dumps(
            {"kind": "whatsapp.event", "event_id": "status-1", "payload": {"data": _status_event()}}
        )
    )
    reply = WhatsAppReplyComponent(_id="reply", connection="whatsapp/business", text="Reply").set(
        event=trigger.build_event
    )
    output = ChatOutput(_id="output").set(input_value=reply.build_message)
    graph = Graph(start=trigger, end=output)

    results = [result async for result in graph.async_start()]

    assert results
    assert graph.get_vertex("reply").built_object["message"].data["skipped"] is True
    assert isinstance(graph.get_vertex("output").built_object, UnbuiltObject)
    assert transport.requests == []


@pytest.mark.parametrize(
    ("event", "status", "label"),
    [
        ("message", None, "Message received"),
        ("status", "delivered", "Status delivered"),
        ("status", "failed", "Status failed"),
    ],
)
def test_canvas_summary_identifies_the_firing_event(event, status, label):
    payload = {"provider": "whatsapp", "event": event, "status": status}
    trigger = component(
        WhatsAppOnEventTriggerComponent,
        event_payload=json.dumps({"kind": "whatsapp.event", "event_id": "event-123", "payload": {"data": payload}}),
    )
    result = trigger.build_event()
    assert result.data["event_id"] == "event-123"
    assert trigger.status == label


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (WhatsAppSendTextComponent, {"to", "text"}),
        (WhatsAppSendTemplateComponent, {"to", "template_name", "language", "body_parameters"}),
        (WhatsAppReplyComponent, {"text"}),
    ],
)
def test_action_tools_expose_content_inputs_but_keep_the_connection_fixed(cls, expected):
    action = component(cls)
    node = action.to_frontend_node()["data"]["node"]
    assert {
        name for name, field in node["template"].items() if isinstance(field, dict) and field.get("tool_mode")
    } == expected
    tools = ComponentToolkit(component=action).get_tools()
    assert len(tools) == 1
    assert set(tools[0].args_schema.model_fields) == expected


@pytest.mark.parametrize(
    ("name", "language", "message"),
    [("Hello World", "en_US", "approved template name"), ("hello_world", "Brazil", "template language")],
)
async def test_template_validation_names_the_wrong_field(name, language, message):
    action = component(WhatsAppSendTemplateComponent, to="15551234567", template_name=name, language=language)
    with pytest.raises(ValueError, match=message):
        await action.build_message()


async def test_missing_template_is_an_input_error_without_provider_404_or_raw_details(monkeypatch):
    GraphTransport([(404, {"error": {"code": 132001, "message": TOKEN, "error_data": {"details": TOKEN}}})]).install(
        monkeypatch
    )
    async with WhatsAppClient(lease()) as client:
        with pytest.raises(InvalidRequestError, match="template name or language") as caught:
            await client.request("POST", "333/messages", body={"type": "template"})
    assert caught.value.http_status == 400
    assert TOKEN not in str(caught.value)


async def test_approved_template_catalog_is_bound_to_waba_and_uses_only_opaque_paging(monkeypatch):
    template = {
        "name": "order_update",
        "language": "en_US",
        "status": "APPROVED",
        "components": [{"type": "BODY", "text": "Order {{1}} for {{2}}, repeated {{1}}"}],
        "secret_extra": TOKEN,
    }
    first = {
        "data": [template, {**template, "name": "pending_template", "status": "PENDING"}],
        "paging": {"next": "https://evil.example/steal", "cursors": {"after": "opaque"}},
    }
    transport = GraphTransport([DEBUG, PHONES, first, {"data": [{**template, "language": "pt_BR"}]}]).install(
        monkeypatch
    )
    async with WhatsAppClient(lease()) as client:
        templates = await client.approved_templates()
    assert [(row.name, row.language, row.body_parameters) for row in templates] == [
        ("order_update", "en_US", 2),
        ("order_update", "pt_BR", 2),
    ]
    assert TOKEN not in repr(templates)
    for request in transport.requests[2:]:
        assert request.url.host == "graph.facebook.com"
        assert request.url.path == "/v25.0/222/message_templates"
        assert json.loads(request.url.params["status"]) == ["APPROVED"]
        assert request.url.params["fields"] == "name,language,status,components"
    assert transport.requests[-1].url.params["after"] == "opaque"


async def test_template_catalog_refuses_repeated_pagination_cursor(monkeypatch):
    page = {"data": [], "paging": {"next": "next", "cursors": {"after": "same"}}}
    GraphTransport([DEBUG, PHONES, page, page]).install(monkeypatch)
    async with WhatsAppClient(lease()) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.approved_templates()


@pytest.mark.usefixtures("resolver")
async def test_template_refresh_populates_name_language_and_parameter_guidance(monkeypatch):
    templates = {
        "data": [
            {
                "name": "order_update",
                "language": "pt_BR",
                "status": "APPROVED",
                "components": [{"type": "BODY", "text": "Order {{1}} for {{2}}"}],
            }
        ]
    }
    transport = GraphTransport([DEBUG, PHONES, templates]).install(monkeypatch)
    action = component(WhatsAppSendTemplateComponent, template_name="order_update", language="en_US")
    config = {field.name: field.model_dump() for field in action.inputs}
    result = await action.update_build_config(config, "whatsapp/business", "connection")
    assert result["template_name"]["options"] == ["order_update"]
    assert result["template_name"]["combobox"] is True
    assert result["template_name"]["refresh_button"] is True
    assert result["language"]["options"] == ["pt_BR"]
    assert result["language"]["value"] == "pt_BR"
    assert "2 positional" in result["body_parameters"]["info"]
    assert TOKEN not in repr(result)
    assert all(request.method == "GET" for request in transport.requests)


@pytest.mark.usefixtures("resolver")
async def test_manual_template_name_and_language_remain_usable_when_catalog_is_empty(monkeypatch):
    GraphTransport([DEBUG, PHONES, {"data": []}]).install(monkeypatch)
    action = component(WhatsAppSendTemplateComponent, template_name="dynamic_name", language="pt_BR")
    config = {field.name: field.model_dump() for field in action.inputs}
    result = await action.update_build_config(config, "dynamic_name", "template_name")
    assert result["template_name"]["value"] == "dynamic_name"
    assert result["language"]["value"] == "pt_BR"
    assert result["language"]["combobox"] is True


async def test_unrelated_field_refresh_keeps_template_choices_without_resolving_credentials(monkeypatch):
    action = component(WhatsAppSendTemplateComponent, template_name="order_update", language="pt_BR")
    config = {field.name: field.model_dump() for field in action.inputs}
    config["template_name"].update(options=["order_update"], value="order_update")
    config["language"].update(options=["pt_BR"], value="pt_BR")
    transport = GraphTransport([]).install(monkeypatch)

    result = await action.update_build_config(config, "15551234567", "to")

    assert result["template_name"]["options"] == ["order_update"]
    assert result["template_name"]["value"] == "order_update"
    assert result["language"]["options"] == ["pt_BR"]
    assert result["language"]["value"] == "pt_BR"
    assert transport.requests == []


async def test_language_change_uses_its_own_parameter_count_without_refetching(monkeypatch):
    action = component(WhatsAppSendTemplateComponent, template_name="order_update", language="en_US")
    config = {field.name: field.model_dump() for field in action.inputs}
    config["template_name"]["options_metadata"] = [{"name": "order_update", "languages": {"en_US": 2, "pt_BR": 1}}]
    transport = GraphTransport([]).install(monkeypatch)

    result = await action.update_build_config(config, "pt_BR", "language")

    assert result["language"]["value"] == "pt_BR"
    assert "1 positional" in result["body_parameters"]["info"]
    assert transport.requests == []
