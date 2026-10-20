"""Salt Ask Human, rewritten 2026-09-26 to poll its own card (`GET /api/v1/cards/:id`) instead of the.

shared socket-mode outbox (`GET /api/v1/agent/updates`) -- see `_salt_common.get_card`'s docstring and
saltapp-langflow HANDOFF.md's 2026-09-26 entry for why. `test_shared_cursor.py`, which used to document the
bug class this file now proves is gone, has been deleted; the assertion that this component makes zero
`get_agent_updates` calls (in every test below, via `_no_get_agent_updates_calls`) is what replaces it.
"""

from __future__ import annotations

import pytest
from lfx_salt.components.salt import ask_human
from lfx_salt.components.salt.ask_human import SaltAskHumanComponent
from salt_fakes import FakeSaltClient, card_interaction, chat_member
from saltapp.errors import SaltApiError


def _make_component(monkeypatch, client: FakeSaltClient, **field_overrides) -> SaltAskHumanComponent:
    monkeypatch.setattr(ask_human.sc, "get_client", lambda _host: client)
    component = SaltAskHumanComponent()
    fields = {
        "host": "https://example.test",
        "agent_id": "agent-self",
        "api_key": "sk-test",
        "private_key": "",
        "passphrase": "",
        "chat_id": "chat-1",
        "question": "Which environment?",
        "options": "Yes,No,Maybe",
        "card_id": "",
    }
    fields.update(field_overrides)
    component.set(**fields)
    return component


def _calls(client: FakeSaltClient, name: str) -> list:
    return [c for c in client.calls if c[0] == name]


def _assert_never_touches_the_outbox(client: FakeSaltClient) -> None:
    """The exact regression this whole rewrite is about: Salt Ask Human must never call.

    `get_agent_updates` (the shared per-agent outbox), in any code path. `grep -rn "agent/updates"
    lfx_salt.components.salt/` returning nothing outside comments is the source-level proof; this is the
    behavioral one.
    """
    assert _calls(client, "get_agent_updates") == []


def test_ask_human_posts_a_card_and_returns_pending_when_nothing_tapped_yet(monkeypatch):
    client = FakeSaltClient()
    # Default get_card_response has interactions=[] -- nothing tapped yet.

    component = _make_component(monkeypatch, client)
    result = component.ask()

    assert result.text == "pending:card-1"
    assert "card_id='card-1'" in component.status
    assert len(_calls(client, "_request")) == 1  # exactly one card read, no loop

    post_card_calls = _calls(client, "post_card")
    assert len(post_card_calls) == 1
    _, args, _kwargs = post_card_calls[0]
    _api_key, chat_id, blocks, text = args
    assert chat_id == "chat-1"
    assert text == "Which environment?"
    # One section (the question) + one actions row (the three buttons).
    assert blocks[0]["type"] == "section"
    assert blocks[0]["text"] == "Which environment?"
    assert [b["label"] for b in blocks[1]["elements"]] == ["Yes", "No", "Maybe"]

    # No interactions at all -> no reason to fetch chat members either.
    assert _calls(client, "get_chat_members") == []
    assert client.closed is True
    _assert_never_touches_the_outbox(client)


def test_ask_human_returns_the_answer_immediately_when_the_instant_tap_is_already_there(monkeypatch):
    """The one card-read this fresh post makes still covers the rare instant-tap case."""
    client = FakeSaltClient()
    client.get_card_response["interactions"] = [
        card_interaction(1, action_id="opt_1", user_id="user-2"),
    ]
    client.chat_members_response = [chat_member("user-2", username="ada")]

    component = _make_component(monkeypatch, client)
    result = component.ask()

    assert result.text == "No"
    assert "ada" in component.status
    assert "'No'" in component.status
    assert len(_calls(client, "_request")) == 1
    _assert_never_touches_the_outbox(client)


def test_ask_human_ignores_a_tap_from_another_agent(monkeypatch):
    client = FakeSaltClient()
    client.get_card_response["interactions"] = [
        card_interaction(1, action_id="opt_0", user_id="agent-3"),
    ]
    client.chat_members_response = [chat_member("agent-3", username="some_other_agent", account_type="Agent")]

    component = _make_component(monkeypatch, client)
    result = component.ask()

    # An agent's own tap must never resolve a pending human ask -- the
    # one check still happens, but nothing answers.
    assert result.text == "pending:card-1"
    assert len(_calls(client, "_request")) == 1
    _assert_never_touches_the_outbox(client)


def test_ask_human_ignores_a_tap_from_someone_no_longer_in_the_chat(monkeypatch):
    """The card's own interaction log carries only `user_id` -- never an account_type or a username.

    (unlike the old outbox event body). A tapper who has since left the chat can't be proven to be a human at
    all, so their tap is treated the same as an agent's: it doesn't resolve the ask.
    """
    client = FakeSaltClient()
    client.get_card_response["interactions"] = [
        card_interaction(1, action_id="opt_0", user_id="user-departed"),
    ]
    client.chat_members_response = []  # user-departed is no longer a member

    component = _make_component(monkeypatch, client)
    result = component.ask()

    assert result.text == "pending:card-1"


def test_ask_human_picks_the_newest_valid_tap_skipping_invalid_ones_above_it(monkeypatch):
    """Interactions come back newest-first.

    An agent's tap sitting above a genuine human tap must not hide it -- the scan keeps going past an invalid
    row instead of stopping at the first one.
    """
    client = FakeSaltClient()
    client.get_card_response["interactions"] = [
        card_interaction(2, action_id="opt_0", user_id="agent-3"),  # newest: an agent, ignored
        card_interaction(1, action_id="opt_1", user_id="user-2"),  # older: the real answer
    ]
    client.chat_members_response = [
        chat_member("agent-3", username="some_other_agent", account_type="Agent"),
        chat_member("user-2", username="ada"),
    ]

    component = _make_component(monkeypatch, client)
    result = component.ask()

    assert result.text == "No"
    assert "ada" in component.status


def test_ask_human_rechecks_an_existing_card_id_without_posting_a_new_one(monkeypatch):
    client = FakeSaltClient()
    client.get_card_response = {
        "id": "card-42",
        "state": {},
        "owner_id": "agent-self",
        "interactions": [
            card_interaction(1, action_id="opt_0", user_id="user-2"),
        ],
    }
    client.chat_members_response = [chat_member("user-2", username="ada")]

    component = _make_component(monkeypatch, client, card_id="card-42")
    result = component.ask()

    assert result.text == "Yes"
    assert not any(c[0] == "post_card" for c in client.calls)  # no new card posted
    _, args, _kwargs = _calls(client, "_request")[0]
    assert args[1] == "/api/v1/cards/card-42"  # rechecked the GIVEN card, not the default fake's
    _assert_never_touches_the_outbox(client)


def test_ask_human_recheck_returns_pending_again_with_no_tap(monkeypatch):
    client = FakeSaltClient()
    # Default get_card_response has interactions=[].

    component = _make_component(monkeypatch, client, card_id="card-42")
    result = component.ask()

    assert result.text == "pending:card-42"
    assert "Still" in component.status
    assert not any(c[0] == "post_card" for c in client.calls)
    assert len(_calls(client, "_request")) == 1


def test_ask_human_recheck_with_blank_options_still_answers_using_the_raw_action_id(monkeypatch):
    """A recheck call that doesn't re-supply `options` can't map the tapped `action_id` back to a.

    human-readable label, but the tap still resolves the ask -- matching a tap has never depended on `options`
    (only display does). See ask_human.py's `label_by_action` comment.
    """
    client = FakeSaltClient()
    client.get_card_response["interactions"] = [
        card_interaction(1, action_id="opt_1", user_id="user-2"),
    ]
    client.chat_members_response = [chat_member("user-2", username="ada")]

    component = _make_component(monkeypatch, client, card_id="card-1", options="")
    result = component.ask()

    assert result.text == "opt_1"  # raw action_id, no label to fall back on
    assert "ada" in component.status


def test_ask_human_with_no_options_and_no_card_id_does_not_call_the_api(monkeypatch):
    client = FakeSaltClient()
    component = _make_component(monkeypatch, client, options="", card_id="")

    result = component.ask()

    assert result.text == "No options given; nothing to ask."
    assert client.calls == []


def test_ask_human_rate_limited_card_read_returns_pending_with_a_hint(monkeypatch):
    """A 429 from the card read is Salt's own rate limit, not "nobody has answered yet" -- it must not.

    raise, and must not be reported as a generic error: it degrades to the same pending result a real "no tap"
    would, with a hint a caller can act on.
    """
    client = FakeSaltClient()
    client.get_card_error = SaltApiError(
        "GET", "https://example.test/api/v1/cards/card-1", 429, {"error": "slow down"}, retry_after=7
    )

    component = _make_component(monkeypatch, client, card_id="card-1")
    result = component.ask()

    assert result.text == "pending:card-1"
    assert "7s" in component.status
    assert "card_id='card-1'" in component.status


def test_ask_human_other_api_errors_still_raise(monkeypatch):
    client = FakeSaltClient()
    client.get_card_error = SaltApiError("GET", "https://example.test/api/v1/cards/card-1", 500, {"error": "boom"})

    component = _make_component(monkeypatch, client, card_id="card-1")

    with pytest.raises(SaltApiError) as excinfo:
        component.ask()
    assert excinfo.value.status == 500
