"""A 1.12 flow using the legacy Google loaders must still open cleanly.

``fixtures/flows/gmail_loader_1.12.json`` was recorded from the component
definitions as they stood *before* this change (generated against the PR's base
ref), so it carries the real pre-INT-10 template and code string rather than a
hand-written approximation.

Two properties are pinned:

* the new optional connection field is not a breaking change — the structural
  rules in ``lfx.upgrade.checker`` must never classify these nodes as
  ``outdated_breaking`` or ``blocked``;
* the nodes do not even report as outdated, because both classes are in
  ``COMPONENTS_TO_IGNORE_UPDATE``. Without that entry a changed code string alone
  would put an "update available" banner on every saved 1.12 flow, which is what
  the ticket's "opens without upgrade warnings" requirement rules out.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lfx.upgrade.checker import COMPONENTS_TO_IGNORE_UPDATE, check_flow_compatibility
from lfx_google.components.google import GmailLoaderComponent, GoogleDriveComponent

FLOW_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "flows" / "gmail_loader_1.12.json"

LEGACY_CLASSES = {
    "GmailLoaderComponent": GmailLoaderComponent,
    "GoogleDriveComponent": GoogleDriveComponent,
}


def _current_registry() -> dict[str, dict]:
    """Build a registry lookup from the components as they are shipped now."""
    return {
        name: component_class().to_frontend_node()["data"]["node"] for name, component_class in LEGACY_CLASSES.items()
    }


def _flow() -> dict:
    return json.loads(FLOW_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_predates_the_connection_field() -> None:
    """Guard the guard: a stale fixture would make the checks below vacuous."""
    for node in _flow()["nodes"]:
        assert "connection" not in node["data"]["node"]["template"]
    for component_class in LEGACY_CLASSES.values():
        assert "connection" in component_class().to_frontend_node()["data"]["node"]["template"]


def test_saved_1_12_flow_opens_without_upgrade_warnings() -> None:
    report = check_flow_compatibility(_flow(), {}, registry=_current_registry())

    assert len(report.nodes) == len(LEGACY_CLASSES)
    assert not report.has_blocked
    assert not report.has_breaking
    assert [node.status for node in report.nodes] == ["ok"] * len(LEGACY_CLASSES)


def test_both_legacy_loaders_are_exempt_from_update_prompts() -> None:
    assert LEGACY_CLASSES.keys() <= COMPONENTS_TO_IGNORE_UPDATE


def test_the_added_field_is_structurally_non_breaking() -> None:
    """Without the exemption the nodes would be outdated_safe, never breaking."""
    registry = _current_registry()
    flow = _flow()
    # Rename the types so the exemption does not apply and the structural rules run.
    for node in flow["nodes"]:
        node["data"]["type"] = f"{node['data']['type']}ForTest"
    renamed_registry = {f"{name}ForTest": entry for name, entry in registry.items()}

    report = check_flow_compatibility(flow, {}, registry=renamed_registry)

    assert [node.status for node in report.nodes] == ["outdated_safe"] * len(LEGACY_CLASSES)


def test_the_new_connection_field_is_optional_in_the_registry_template() -> None:
    for entry in _current_registry().values():
        connection = entry["template"]["connection"]
        assert connection["type"] == "connection_ref"
        assert connection["required"] is False
        # json_string was relaxed so a connection-only configuration is valid.
        assert entry["template"]["json_string"]["required"] is False


async def test_gmail_loader_requires_exactly_one_credential_source() -> None:
    component = GmailLoaderComponent(connection="", json_string="", label_ids="INBOX", max_results="5")

    with pytest.raises(ValueError, match="either a managed Google connection or a token JSON"):
        await component.load_emails()

    both = GmailLoaderComponent(
        connection="google/work", json_string='{"token": "x"}', label_ids="INBOX", max_results="5"
    )
    with pytest.raises(ValueError, match="not both"):
        await both.load_emails()


async def test_drive_loader_requires_exactly_one_credential_source() -> None:
    component = GoogleDriveComponent(connection="", json_string="", document_id="doc-1")

    with pytest.raises(ValueError, match="either a managed Google connection or a token JSON"):
        await component.load_documents()

    both = GoogleDriveComponent(connection="google/work", json_string='{"token": "x"}', document_id="doc-1")
    with pytest.raises(ValueError, match="not both"):
        await both.load_documents()


async def test_gmail_loader_builds_credentials_from_a_connection(resolver, monkeypatch) -> None:
    """A connection-configured loader gets a lease token, never a pasted secret."""
    from conftest import FAKE_ACCESS_TOKEN, wire

    captured: dict = {}
    monkeypatch.setattr(
        "langchain_google_community.gmail.loader.GMailLoader.__init__",
        lambda _self, creds, n=100, _raise_error=False: captured.update(creds=creds, n=n),
    )
    monkeypatch.setattr("langchain_google_community.gmail.loader.GMailLoader.load", lambda _self: [])

    component = GmailLoaderComponent(json_string="", label_ids="INBOX", max_results="5")
    wire(component, [])  # no Google call is made; this supplies the graph principal

    await component.load_emails()

    assert captured["creds"].token == FAKE_ACCESS_TOKEN
    assert resolver.requests[0].required_scopes == frozenset({"https://www.googleapis.com/auth/gmail.readonly"})
