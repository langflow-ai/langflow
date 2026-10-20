from __future__ import annotations

from lfx_salt.components.salt import read_updates
from lfx_salt.components.salt.read_updates import SaltReadUpdatesComponent
from salt_fakes import FakeSaltClient, signed_update_row


def _make_component(monkeypatch, client: FakeSaltClient, **field_overrides) -> SaltReadUpdatesComponent:
    monkeypatch.setattr(read_updates.sc, "get_client", lambda _host: client)
    component = SaltReadUpdatesComponent()
    fields = {
        "host": "https://example.test",
        "agent_id": "agent-self",
        "api_key": "sk-test",
        "private_key": "",
        "passphrase": "",
        "event_types": "",
    }
    fields.update(field_overrides)
    component.set(**fields)
    return component


def _get_agent_updates_calls(client: FakeSaltClient) -> list:
    return [c for c in client.calls if c[0] == "get_agent_updates"]


def test_read_updates_returns_no_new_events_on_an_empty_check(monkeypatch):
    client = FakeSaltClient()
    client.update_rounds = [{"updates": [], "cursor": 0}]

    component = _make_component(monkeypatch, client)
    result = component.read()

    assert result.data == {"status": "no_new_events", "events": []}
    assert component.status == "No new events since last check."
    assert len(_get_agent_updates_calls(client)) == 1  # exactly one check, no loop
    assert client.closed is True


def test_read_updates_returns_every_matching_event_from_one_round(monkeypatch):
    """A one-shot check must return ALL matching events in the response page, not just the first -- unlike.

    the old poll_for_event, which stopped at the first predicate hit.
    """
    client = FakeSaltClient()
    message_body = {"message": {"id": "msg-1"}, "chat_id": "chat-1"}
    invoice_body = {"type": "invoice_paid", "chat_id": "chat-1", "transfer_request_id": "tr-1"}
    another_invoice_body = {"type": "invoice_paid", "chat_id": "chat-2", "transfer_request_id": "tr-2"}
    client.update_rounds = [
        {
            "updates": [
                signed_update_row(1, message_body),
                signed_update_row(2, invoice_body),
                signed_update_row(3, another_invoice_body),
            ],
            "cursor": 3,
        }
    ]

    component = _make_component(monkeypatch, client, event_types="invoice_paid")
    result = component.read()

    assert result.data["status"] == "events"
    assert len(result.data["events"]) == 2
    assert [e["body"] for e in result.data["events"]] == [invoice_body, another_invoice_body]
    assert component.status == "2 new event(s)."
    assert len(_get_agent_updates_calls(client)) == 1


def test_read_updates_filters_by_event_type_within_one_round(monkeypatch):
    client = FakeSaltClient()
    message_body = {"message": {"id": "msg-1"}, "chat_id": "chat-1"}
    invoice_body = {"type": "invoice_paid", "chat_id": "chat-1", "transfer_request_id": "tr-1"}
    client.update_rounds = [
        {
            "updates": [
                signed_update_row(1, message_body),
                signed_update_row(2, invoice_body),
            ],
            "cursor": 2,
        }
    ]

    component = _make_component(monkeypatch, client, event_types="invoice_paid")
    result = component.read()

    assert result.data["status"] == "events"
    assert len(result.data["events"]) == 1
    assert result.data["events"][0]["event_type"] == "invoice_paid"
    assert result.data["events"][0]["body"] == invoice_body


def test_read_updates_persists_its_cursor_across_component_runs(monkeypatch):
    """A second 'flow run' (a fresh component + a fresh fake client) must start checking from where the.

    first run's cursor left off, not from 0 -- the whole point of PersistentCursor.
    """
    first_client = FakeSaltClient()
    first_body = {"message": {"id": "msg-1"}, "chat_id": "chat-1"}
    first_client.update_rounds = [{"updates": [signed_update_row(5, first_body)], "cursor": 5}]

    first_run = _make_component(monkeypatch, first_client)
    first_result = first_run.read()
    assert first_result.data["status"] == "events"

    second_client = FakeSaltClient()
    second_client.update_rounds = [{"updates": [], "cursor": 5}]

    second_run = _make_component(monkeypatch, second_client)
    second_run.read()

    after_values = [kwargs["after"] for name, _args, kwargs in second_client.calls if name == "get_agent_updates"]
    assert after_values == [5]
