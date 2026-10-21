"""A 1.12 flow using the legacy Google loaders must still open cleanly.

The fixture contains the original templates and source before this release changed
the loaders: the Drive loader gained an optional managed connection, and both loaders
changed code. Those changes should classify saved nodes as ``outdated_safe``, while a
missing component or incompatible input must still produce a blocked or breaking
verdict. The Gmail loader deliberately gained no connection (see
``decisions/google-restricted-scopes.md``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lfx.upgrade.checker import COMPONENTS_TO_IGNORE_UPDATE, check_flow_compatibility
from lfx_google.components.google import GmailLoaderComponent, GoogleDriveComponent

FLOW_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "flows" / "gmail_loader_1.12.json"

# Authorized-user token JSON with obviously fake values; google-auth only checks the keys.
AUTHORIZED_USER_JSON = json.dumps(
    {
        "client_id": "fake-client-id",
        "client_secret": "fake-client-secret",  # pragma: allowlist secret
        "refresh_token": "fake-refresh-token",  # pragma: allowlist secret
        "token": "fake-access-token",  # pragma: allowlist secret
    }
)

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
    assert "connection" in GoogleDriveComponent().to_frontend_node()["data"]["node"]["template"]


def test_gmail_loader_offers_no_managed_connection() -> None:
    """gmail.readonly is restricted; a self-managed restricted profile is deferred to 1.14.

    decisions/google-restricted-scopes.md keeps Option C out of 1.13, and a connection
    field here would ship it outside capabilities.v1.json, beyond action-level policy.
    """
    template = GmailLoaderComponent().to_frontend_node()["data"]["node"]["template"]

    assert not any(field.get("type") == "connection_ref" for field in template.values() if isinstance(field, dict))
    assert template["json_string"]["required"] is True


def test_saved_1_12_flow_opens_without_a_blocking_or_breaking_verdict() -> None:
    """Optional connections are a safe update for saved loader nodes."""
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
    A safe-update banner preserves these compatibility checks.
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
    entry = _current_registry()["GoogleDriveComponent"]
    connection = entry["template"]["connection"]
    assert connection["type"] == "connection_ref"
    assert connection["required"] is False
    # json_string was relaxed so a connection-only configuration is valid.
    assert entry["template"]["json_string"]["required"] is False


async def test_gmail_loader_requires_token_json() -> None:
    component = GmailLoaderComponent(json_string="", label_ids="INBOX", max_results="5")

    with pytest.raises(ValueError, match="needs a token JSON string"):
        await component.load_emails()


async def test_drive_loader_requires_exactly_one_credential_source() -> None:
    component = GoogleDriveComponent(connection="", json_string="", document_id="doc-1")

    with pytest.raises(ValueError, match="either a managed Google connection or a token JSON"):
        await component.load_documents()

    both = GoogleDriveComponent(connection="google/work", json_string='{"token": "x"}', document_id="doc-1")
    with pytest.raises(ValueError, match="not both"):
        await both.load_documents()


async def test_a_padded_connection_handle_still_resolves(resolver, monkeypatch) -> None:
    """A pasted handle with surrounding whitespace resolves instead of failing late.

    The either/or guard and ``resolve_connection`` must agree about the handle: the
    guard used to trim into a local while ``resolve_connection`` re-read the raw field,
    so ``" google/work "`` passed the "is set" check and then died inside
    ``ConnectionRef.parse``.
    """
    from conftest import wire

    monkeypatch.setattr("langchain_google_community.GoogleDriveLoader.load", lambda _self: [object()])
    monkeypatch.setattr(
        "lfx_google.components.google.google_drive.docs_to_data", lambda docs: [{"text": "doc"} for _ in docs]
    )

    component = GoogleDriveComponent(json_string="", document_id="doc-1")
    wire(component, [], connection="  google/work  ")

    await component.load_documents()

    assert resolver.requests[0].ref.to_handle() == "google/work"


@pytest.mark.usefixtures("resolver")
@pytest.mark.parametrize("auth_failure", [False, True])
@pytest.mark.parametrize(
    ("component_class", "operation", "loader_path", "kwargs"),
    [
        (
            GmailLoaderComponent,
            "load_emails",
            "langchain_google_community.gmail.loader.GMailLoader.load",
            {"json_string": AUTHORIZED_USER_JSON},
        ),
        (
            GoogleDriveComponent,
            "load_documents",
            "langchain_google_community.GoogleDriveLoader.load",
            {"connection": "google/work", "document_id": "doc-1"},
        ),
    ],
)
async def test_loader_failures_log_context_without_provider_payload(
    monkeypatch, component_class, operation, loader_path, kwargs, auth_failure
):
    from unittest.mock import MagicMock

    from conftest import wire
    from google.auth.exceptions import RefreshError

    payload = "private-provider-payload"
    failure = RefreshError(payload) if auth_failure else RuntimeError(payload)

    def fail(_self):
        raise failure

    monkeypatch.setattr(loader_path, fail)
    log = MagicMock()
    monkeypatch.setattr(f"{component_class.__module__}.logger", log)
    component = component_class(**kwargs)
    if "connection" in kwargs:
        wire(component, [], connection=kwargs["connection"])

    with pytest.raises(ValueError, match=r"Authentication error|Error loading documents") as caught:
        await getattr(component, operation)()

    assert payload not in str(caught.value)
    log.warning.assert_called_once()
    assert component.display_name in str(log.warning.call_args)
    assert "load failed" in str(log.warning.call_args)
    assert payload not in str(log.warning.call_args)
