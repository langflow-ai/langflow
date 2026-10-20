from __future__ import annotations

from lfx_salt.components.salt import read_room
from lfx_salt.components.salt.read_room import SaltReadRoomComponent
from salt_fakes import FakeSaltClient


def _make_component(monkeypatch, client: FakeSaltClient, **field_overrides) -> SaltReadRoomComponent:
    monkeypatch.setattr(read_room.sc, "get_client", lambda _host: client)
    component = SaltReadRoomComponent()
    fields = {
        "host": "https://example.test",
        "api_key": "sk-test",
        "chat_id": "chat-1",
        "last": "",
    }
    fields.update(field_overrides)
    component.set(**fields)
    return component


def _get_chat_calls(client: FakeSaltClient) -> list:
    return [c for c in client.calls if c[0] == "get_chat"]


def test_read_room_returns_the_raw_chat_payload(monkeypatch):
    client = FakeSaltClient()
    client.get_chat_response = {
        "session": {"encrypted": True, "users": []},
        "messages": [
            {"id": "msg-1", "encrypted": True, "delivered_because": None},
            {"id": "msg-2", "encrypted": False, "delivered_because": "mention"},
        ],
    }

    component = _make_component(monkeypatch, client)
    result = component.read()

    assert result.data == client.get_chat_response
    assert component.status == "2 message(s) in chat chat-1."

    calls = _get_chat_calls(client)
    assert len(calls) == 1
    _, args, kwargs = calls[0]
    assert args == ("sk-test", "chat-1")
    assert kwargs == {"last": None}
    assert client.closed is True


def test_read_room_passes_last_through_as_a_cursor(monkeypatch):
    client = FakeSaltClient()
    client.get_chat_response = {"session": {"encrypted": False, "users": []}, "messages": []}

    component = _make_component(monkeypatch, client, last="17")
    component.read()

    _, args, kwargs = _get_chat_calls(client)[0]
    assert args == ("sk-test", "chat-1")
    assert kwargs == {"last": "17"}


def test_read_room_works_with_a_blank_api_key_against_an_open_room(monkeypatch):
    """Proves the anonymous path: a blank api_key field reaches the client as the literal empty string.

    which SaltClient._request treats as "send no api-key header at all" -- the whole point of Salt Read Room
    being usable keyless against a public, unencrypted room.
    """
    client = FakeSaltClient()
    client.get_chat_response = {"session": {"encrypted": False, "users": []}, "messages": []}

    component = _make_component(monkeypatch, client, api_key="")
    result = component.read()

    assert result.data == client.get_chat_response
    _, args, _kwargs = _get_chat_calls(client)[0]
    assert args == ("", "chat-1")
