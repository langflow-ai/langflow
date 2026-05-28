"""Tests for note node translation in i18n utilities and API endpoints."""

import uuid

from fastapi import status
from httpx import AsyncClient
from langflow.utils.i18n import _safe_flow_key, translate_flow_notes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_note_node(node_id: str, description: str, i18n_key: str | None = None) -> dict:
    node_data: dict = {"description": description}
    if i18n_key is not None:
        node_data["i18n_key"] = i18n_key
    return {
        "id": node_id,
        "type": "noteNode",
        "data": {"node": node_data},
    }


def _make_generic_node(node_id: str) -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {"node": {"display_name": "Chat Input"}},
    }


# ---------------------------------------------------------------------------
# Unit tests — translate_flow_notes()
# ---------------------------------------------------------------------------


class TestTranslateFlowNotes:
    def test_translates_description_when_key_is_baked_in(self, monkeypatch):
        """A noteNode with i18n_key baked in gets its description translated."""
        monkeypatch.setattr(
            "langflow.utils.i18n._translations",
            {
                "en": {"template_notes.simple_agent.0": "Hello"},
                "fr": {"template_notes.simple_agent.0": "Bonjour"},
            },
        )
        nodes = [_make_note_node("n1", "Hello", i18n_key="template_notes.simple_agent.0")]
        result = translate_flow_notes(nodes, "fr")
        assert result[0]["data"]["node"]["description"] == "Bonjour"

    def test_falls_back_to_english_when_locale_missing(self, monkeypatch):
        monkeypatch.setattr(
            "langflow.utils.i18n._translations",
            {"en": {"template_notes.simple_agent.0": "Hello"}},
        )
        nodes = [_make_note_node("n1", "Hello", i18n_key="template_notes.simple_agent.0")]
        result = translate_flow_notes(nodes, "ja")
        assert result[0]["data"]["node"]["description"] == "Hello"

    def test_falls_back_to_original_when_key_not_in_translations(self, monkeypatch):
        monkeypatch.setattr("langflow.utils.i18n._translations", {"en": {}, "fr": {}})
        nodes = [_make_note_node("n1", "Original text", i18n_key="template_notes.unknown_flow.0")]
        result = translate_flow_notes(nodes, "fr")
        assert result[0]["data"]["node"]["description"] == "Original text"

    def test_node_without_i18n_key_is_passed_through_unchanged(self, monkeypatch):
        """NoteNodes without i18n_key (e.g. user-created) are left untouched."""
        monkeypatch.setattr("langflow.utils.i18n._translations", {"fr": {}})
        node = _make_note_node("n1", "User note")  # no i18n_key
        result = translate_flow_notes([node], "fr")
        assert result[0] is node  # same object, not deep-copied

    def test_non_note_nodes_are_passed_through_unchanged(self, monkeypatch):
        monkeypatch.setattr("langflow.utils.i18n._translations", {"en": {}})
        generic = _make_generic_node("g1")
        result = translate_flow_notes([generic], "fr")
        assert result[0] is generic  # same object, untouched

    def test_does_not_mutate_input_nodes(self, monkeypatch):
        monkeypatch.setattr(
            "langflow.utils.i18n._translations",
            {"en": {"template_notes.simple_agent.0": "Hello"}},
        )
        node = _make_note_node("n1", "Hello", i18n_key="template_notes.simple_agent.0")
        original_description = node["data"]["node"]["description"]
        translate_flow_notes([node], "en")
        assert node["data"]["node"]["description"] == original_description

    def test_translates_multiple_note_nodes_independently(self, monkeypatch):
        monkeypatch.setattr(
            "langflow.utils.i18n._translations",
            {
                "en": {
                    "template_notes.simple_agent.0": "First",
                    "template_notes.simple_agent.1": "Second",
                },
                "fr": {
                    "template_notes.simple_agent.0": "Premier",
                    "template_notes.simple_agent.1": "Deuxième",
                },
            },
        )
        nodes = [
            _make_note_node("n0", "First", i18n_key="template_notes.simple_agent.0"),
            _make_note_node("n1", "Second", i18n_key="template_notes.simple_agent.1"),
        ]
        result = translate_flow_notes(nodes, "fr")
        assert result[0]["data"]["node"]["description"] == "Premier"
        assert result[1]["data"]["node"]["description"] == "Deuxième"

    def test_does_not_stamp_i18n_key_onto_nodes(self, monkeypatch):
        """translate_flow_notes must never write i18n_key — that's the bake script's job."""
        monkeypatch.setattr(
            "langflow.utils.i18n._translations",
            {"en": {"template_notes.simple_agent.0": "Hello"}},
        )
        node = _make_note_node("n1", "Hello")  # no i18n_key
        result = translate_flow_notes([node], "en")
        assert "i18n_key" not in result[0]["data"]["node"]


# ---------------------------------------------------------------------------
# Unit tests — _safe_flow_key()
# ---------------------------------------------------------------------------


class TestSafeFlowKey:
    def test_lowercases_and_replaces_spaces(self):
        assert _safe_flow_key("Simple Agent") == "simple_agent"

    def test_parentheses_in_name_become_underscores(self):
        # Parentheses are replaced with underscores, so the dedup number is
        # preserved in the key. Callers must pass the original (deduped) name
        # to get a stable key.
        assert _safe_flow_key("Simple Agent (2)") == "simple_agent_2"

    def test_handles_special_characters(self):
        assert _safe_flow_key("My-Flow! v2") == "my_flow_v2"


# ---------------------------------------------------------------------------
# Integration tests — GET /flows/{id}/note_translations
# ---------------------------------------------------------------------------


async def test_note_translations_returns_empty_for_user_flow(client: AsyncClient, logged_in_headers):
    """A flow without i18n_key on its noteNodes returns an empty map."""
    flow_payload = {
        "name": "User Flow",
        "description": "",
        "data": {
            "nodes": [_make_note_node("note-abc", "My note")],
            "edges": [],
        },
        "is_component": False,
    }
    create_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    flow_id = create_resp.json()["id"]

    resp = await client.get(f"api/v1/flows/{flow_id}/note_translations", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {}


async def test_note_translations_returns_translated_text_for_baked_node(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """A noteNode with a baked i18n_key returns translated text for the locale."""
    import langflow.utils.i18n as i18n_mod

    monkeypatch.setattr(
        i18n_mod,
        "_translations",
        {
            "en": {"template_notes.simple_agent.0": "Hello"},
            "fr": {"template_notes.simple_agent.0": "Bonjour"},
        },
    )

    note_node = _make_note_node("note-xyz", "Hello", i18n_key="template_notes.simple_agent.0")

    flow_payload = {
        "name": "Baked Flow",
        "description": "",
        "data": {"nodes": [note_node], "edges": []},
        "is_component": False,
    }
    create_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    flow_id = create_resp.json()["id"]

    resp = await client.get(
        f"api/v1/flows/{flow_id}/note_translations",
        headers={**logged_in_headers, "Accept-Language": "fr"},
    )
    assert resp.status_code == status.HTTP_200_OK
    translations = resp.json()
    assert "Bonjour" in translations.values()


async def test_note_translations_returns_404_for_missing_flow(client: AsyncClient, logged_in_headers):
    """A non-existent (or inaccessible) flow returns 404, consistent with GET /flows/{id}."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"api/v1/flows/{fake_id}/note_translations", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
