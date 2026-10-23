from __future__ import annotations

from lfx_salt.components.salt import interests
from lfx_salt.components.salt.interests import SaltInterestsComponent
from salt_fakes import FakeSaltClient


def _make_component(monkeypatch, client: FakeSaltClient, **field_overrides) -> SaltInterestsComponent:
    monkeypatch.setattr(interests.sc, "get_client", lambda _host: client)
    component = SaltInterestsComponent()
    fields = {
        "host": "https://example.test",
        "agent_id": "agent-self",
        "api_key": "sk-test",
        "chat_id": "chat-1",
        "action": "set",
        "mode": "addressed",
        "keywords": "",
    }
    fields.update(field_overrides)
    component.set(**fields)
    return component


def test_interests_set_calls_set_chat_subscription(monkeypatch):
    client = FakeSaltClient()
    client.set_chat_subscription_response = {"chat_id": "chat-1", "mode": "keywords", "keywords": ["salt", "agent"]}

    component = _make_component(monkeypatch, client, mode="keywords", keywords="salt, agent")
    result = component.apply()

    assert result.data == client.set_chat_subscription_response
    assert "keywords" in component.status

    calls = [c for c in client.calls if c[0] == "set_chat_subscription"]
    assert len(calls) == 1
    _, args, kwargs = calls[0]
    assert args == ("sk-test", "chat-1", "keywords")
    assert kwargs == {"keywords": ["salt", "agent"]}
    assert client.closed is True


def test_interests_set_with_non_keywords_mode_sends_no_keywords(monkeypatch):
    client = FakeSaltClient()
    component = _make_component(monkeypatch, client, mode="all", keywords="ignored,too")
    component.apply()

    _, _args, kwargs = next(c for c in client.calls if c[0] == "set_chat_subscription")
    assert kwargs == {"keywords": None}


def test_interests_get_calls_get_chat_subscription(monkeypatch):
    client = FakeSaltClient()
    client.get_chat_subscription_response = {"chat_id": "chat-1", "mode": "all", "keywords": []}

    component = _make_component(monkeypatch, client, action="get")
    result = component.apply()

    assert result.data == client.get_chat_subscription_response
    assert "'all'" in component.status

    calls = [c for c in client.calls if c[0] == "get_chat_subscription"]
    assert len(calls) == 1
    _, args, _kwargs = calls[0]
    assert args == ("sk-test", "chat-1")
    assert not any(c[0] in ("set_chat_subscription", "clear_chat_subscription") for c in client.calls)


def test_interests_clear_calls_clear_chat_subscription(monkeypatch):
    client = FakeSaltClient()
    client.clear_chat_subscription_response = {"chat_id": "chat-1", "mode": "addressed", "keywords": []}

    component = _make_component(monkeypatch, client, action="clear")
    result = component.apply()

    assert result.data == client.clear_chat_subscription_response
    calls = [c for c in client.calls if c[0] == "clear_chat_subscription"]
    assert len(calls) == 1
    _, args, _kwargs = calls[0]
    assert args == ("sk-test", "chat-1")


def test_interests_set_without_a_mode_is_a_validation_error_not_an_api_call(monkeypatch):
    client = FakeSaltClient()
    component = _make_component(monkeypatch, client, mode="")

    result = component.apply()

    assert result.data == {
        "status": "error",
        "error": 'action="set" needs a mode: "addressed", "keywords", or "all".',
    }
    assert client.calls == []


def test_interests_invalid_action_is_a_validation_error_not_an_api_call(monkeypatch):
    client = FakeSaltClient()
    component = _make_component(monkeypatch, client, action="delete")

    result = component.apply()

    assert result.data["status"] == "error"
    assert "delete" in result.data["error"]
    assert client.calls == []
