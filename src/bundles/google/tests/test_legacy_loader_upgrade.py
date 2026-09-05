"""A 1.12 flow using the legacy Google loaders must still open cleanly.

``fixtures/flows/gmail_loader_1.12.json`` was recorded from the component
definitions as they stood *before* this change (generated against the PR's base
ref), so it carries the real pre-INT-10 template and code string rather than a
hand-written approximation.

What is pinned here is the classification the release owner accepted for INT-10:
the saved nodes are ``outdated_safe`` — never ``blocked`` and never
``outdated_breaking``. The optional connection field is additive by every
structural rule in ``lfx.upgrade.checker``; what makes the nodes outdated at all
is only that the components' code string changed, which is true of any component
edit. An earlier revision of this branch suppressed even that by adding both
classes to ``COMPONENTS_TO_IGNORE_UPDATE``; that was reverted, because the
exemption is checked *before* the registry lookup in ``_classify_node`` and would
therefore also mask ``blocked`` (component missing from the registry) and any
future genuinely breaking change to these two classes, permanently. The banner is
the cheaper of the two, and ``outdated_safe`` is the accepted answer for INT-10
(DECISIONS.md, release-owner decision 2026-09-04).
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


def test_saved_1_12_flow_opens_without_a_blocking_or_breaking_verdict() -> None:
    """The accepted INT-10 outcome: outdated_safe, nothing blocked, nothing breaking."""
    report = check_flow_compatibility(_flow(), {}, registry=_current_registry())

    assert len(report.nodes) == len(LEGACY_CLASSES)
    assert not report.has_blocked
    assert not report.has_breaking
    assert [node.status for node in report.nodes] == ["outdated_safe"] * len(LEGACY_CLASSES)


def test_the_legacy_loaders_are_not_exempted_from_the_upgrade_checker() -> None:
    """The exemption list short-circuits before the registry lookup.

    ``_classify_node`` returns ``ok`` for an exempt type before it checks whether the
    component is in the registry at all, so listing these classes would also hide a
    ``blocked`` verdict (bundle uninstalled) and every future breaking change to them.
    INT-10 accepts the update banner instead.
    """
    assert not (LEGACY_CLASSES.keys() & COMPONENTS_TO_IGNORE_UPDATE)


def test_an_absent_registry_entry_is_still_reported_as_blocked() -> None:
    """The property the exemption would have destroyed, pinned directly."""
    report = check_flow_compatibility(_flow(), {}, registry={})

    assert report.has_blocked
    assert [node.status for node in report.nodes] == ["blocked"] * len(LEGACY_CLASSES)


def test_the_added_field_is_structurally_non_breaking() -> None:
    """The connection field itself trips none of the breaking-change rules.

    ``outdated_safe`` above already implies this, so this test isolates the reason:
    strip the code-string difference (the only thing making the node outdated) and
    the very same templates classify as ``ok``.
    """
    registry = _current_registry()
    flow = _flow()
    for node in flow["nodes"]:
        registry_code = registry[node["data"]["type"]]["template"]["code"]["value"]
        node["data"]["node"]["template"]["code"]["value"] = registry_code

    report = check_flow_compatibility(flow, {}, registry=registry)

    assert [node.status for node in report.nodes] == ["ok"] * len(LEGACY_CLASSES)


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


async def test_a_padded_connection_handle_still_resolves(resolver, monkeypatch) -> None:
    """A pasted handle with surrounding whitespace resolves instead of failing late.

    The either/or guard and ``resolve_connection`` must agree about the handle: the
    guard used to trim into a local while ``resolve_connection`` re-read the raw field,
    so ``" google/work "`` passed the "is set" check and then died inside
    ``ConnectionRef.parse``.
    """
    from conftest import wire

    monkeypatch.setattr(
        "langchain_google_community.gmail.loader.GMailLoader.__init__",
        lambda _self, _creds, _n=100, _raise_error=False: None,
    )
    monkeypatch.setattr("langchain_google_community.gmail.loader.GMailLoader.load", lambda _self: [])

    component = GmailLoaderComponent(json_string="", label_ids="INBOX", max_results="5")
    wire(component, [], connection="  google/work  ")

    await component.load_emails()

    assert resolver.requests[0].ref.to_handle() == "google/work"
