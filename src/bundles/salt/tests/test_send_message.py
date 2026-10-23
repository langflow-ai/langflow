# Salt Send Message: real PGP round-trip (generate two real keypairs,
# encrypt through the component, decrypt with each recipient's own private
# key) plus the no-recipients error path and the open-room plain-text path.
from __future__ import annotations

import pytest
from lfx_salt.components.salt import send_message
from lfx_salt.components.salt.send_message import SaltSendMessageComponent
from salt_fakes import FakeSaltClient
from saltapp import crypto
from saltapp.errors import SaltApiError


def _make_component(monkeypatch, client: FakeSaltClient, **field_overrides) -> SaltSendMessageComponent:
    monkeypatch.setattr(send_message.sc, "get_client", lambda _host: client)
    component = SaltSendMessageComponent()
    fields = {
        "host": "https://example.test",
        "agent_id": "agent-self",
        "api_key": "sk-test",
        "private_key": "",
        "passphrase": "",
        "chat_id": "chat-1",
        "text": "hello there",
        "quiet": False,
    }
    fields.update(field_overrides)
    component.set(**fields)
    return component


def test_send_message_encrypts_for_every_recipient_and_a_self_copy(monkeypatch):
    self_keys = crypto.generate_keypair("self-pass")
    other_keys = crypto.generate_keypair("other-pass")

    client = FakeSaltClient()
    # Members now come from the chat's own session.users (the same call
    # that tells sc.send_message whether the room is encrypted), not a
    # second get_chat_members round trip -- see _salt_common.send_message.
    client.get_chat_response = {
        "session": {
            "encrypted": True,
            "users": [
                {"id": "agent-self", "public_key": self_keys.public_key},
                {"id": "user-2", "public_key": other_keys.public_key},
            ],
        },
        "messages": [],
    }

    component = _make_component(monkeypatch, client)
    result = component.send()

    assert result.text == "Sent to chat chat-1."
    assert "message id msg-1" in component.status

    post_calls = [c for c in client.calls if c[0] == "post_message"]
    assert len(post_calls) == 1
    _, args, _kwargs = post_calls[0]
    api_key, chat_id, ciphertext, sender_copy = args
    assert api_key == "sk-test"
    assert chat_id == "chat-1"

    # Real decrypt, not a stubbed check: the recipient's own private key
    # must recover exactly the plaintext that was sent.
    decrypted_for_recipient = crypto.decrypt(ciphertext, other_keys.private_key, "other-pass")
    assert decrypted_for_recipient == "hello there"

    # The sender copy exists and decrypts under the SENDER's own key too.
    assert sender_copy is not None
    decrypted_for_sender = crypto.decrypt(sender_copy, self_keys.private_key, "self-pass")
    assert decrypted_for_sender == "hello there"

    # No second round trip for members: get_chat_members is never called
    # once session.users is present.
    assert not any(c[0] == "get_chat_members" for c in client.calls)
    assert client.closed is True


def test_send_message_falls_back_to_get_chat_members_when_session_has_no_users_key(monkeypatch):
    """A defensive fallback for a response shape session["users"] would not carry -- see sc.send_message's.

    own docstring. Exercised directly since the real SDK's session payload always has "users" today.
    """
    self_keys = crypto.generate_keypair("self-pass")
    other_keys = crypto.generate_keypair("other-pass")

    client = FakeSaltClient()
    client.get_chat_response = {"session": {"encrypted": True}, "messages": []}  # no "users" key at all
    client.chat_members_response = [
        {"id": "agent-self", "public_key": self_keys.public_key},
        {"id": "user-2", "public_key": other_keys.public_key},
    ]

    component = _make_component(monkeypatch, client)
    result = component.send()

    assert result.text == "Sent to chat chat-1."
    assert any(c[0] == "get_chat_members" for c in client.calls)

    _, args, _kwargs = next(c for c in client.calls if c[0] == "post_message")
    _api_key, _chat_id, ciphertext, _sender_copy = args
    assert crypto.decrypt(ciphertext, other_keys.private_key, "other-pass") == "hello there"


def test_send_message_raises_when_nobody_else_has_a_public_key(monkeypatch):
    self_keys = crypto.generate_keypair("self-pass")
    client = FakeSaltClient()
    # Only this agent's own row has a key -- nobody else to encrypt for.
    client.get_chat_response = {
        "session": {"encrypted": True, "users": [{"id": "agent-self", "public_key": self_keys.public_key}]},
        "messages": [],
    }

    component = _make_component(monkeypatch, client)

    with pytest.raises(SaltApiError, match="no recipient public keys"):
        component.send()

    assert not any(c[0] == "post_message" for c in client.calls)


def test_send_message_posts_plain_text_in_an_open_room(monkeypatch):
    """session.encrypted == False (saltapp 0.2.0's open rooms) must go through post_plain_message, never.

    touching crypto.encrypt_for/ post_message at all.
    """
    client = FakeSaltClient()
    client.get_chat_response = {"session": {"encrypted": False, "users": []}, "messages": []}
    client.post_plain_message_response = {"id": "msg-open-1", "encrypted": False, "delivered_because": "all"}

    encrypt_calls = []
    monkeypatch.setattr(crypto, "encrypt_for", lambda *a, **kw: encrypt_calls.append((a, kw)))

    component = _make_component(monkeypatch, client)
    result = component.send()

    assert encrypt_calls == []

    assert result.text == "Sent to chat chat-1."
    assert "plain (open room)" in component.status
    assert "delivered because all" in component.status
    assert "message id msg-open-1" in component.status

    plain_calls = [c for c in client.calls if c[0] == "post_plain_message"]
    assert len(plain_calls) == 1
    _, args, kwargs = plain_calls[0]
    assert args == ("sk-test", "chat-1", "hello there")
    assert kwargs == {"mentions": None, "quiet": False}

    assert not any(c[0] == "post_message" for c in client.calls)
    assert not any(c[0] in ("get_chat_members",) for c in client.calls)
