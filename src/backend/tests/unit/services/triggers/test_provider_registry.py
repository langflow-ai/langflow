"""Installed integration ownership is required before loading server hooks."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from langflow.services.triggers.providers import registry


def _normalize(_kind, raw):
    return {key: value for key, value in raw.items() if value is not None}


def _verify(*_args, **_kwargs):
    from langflow.services.triggers.ingress.verifiers import Verified

    return Verified()


@pytest.fixture
def provider():
    return registry.TriggerProvider(
        provider_id="pilot",
        bundle="pilot",
        normalize_config=_normalize,
        kinds=(
            registry.TriggerKind(
                kind="pilot.item",
                component="PilotOnItemTriggerComponent",
                display_name="Pilot On Item",
                config_fields=("connection", "repository", "delivery_mode"),
                push_mechanism="pilot.webhook",
                identity="service",
            ),
        ),
        verify=_verify,
    )


@pytest.fixture
def discovery(monkeypatch):
    from lfx.extension import bundle_registry

    snapshot = {}
    entries = []
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_cache_records", ())
    monkeypatch.setattr(registry, "_providers", {})
    monkeypatch.setattr(bundle_registry, "get_default_registry", lambda: SimpleNamespace(snapshot=lambda: snapshot))
    original_entry_points = registry.metadata.entry_points
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: entries
        if kwargs.get("group") == registry.ENTRY_POINT_GROUP
        else original_entry_points(**kwargs),
    )
    return snapshot, entries


def _record(*, component="PilotOnItemTriggerComponent", distribution="lfx-pilot"):
    owner = SimpleNamespace(
        provider_id="pilot",
        bundle="pilot",
        distribution=distribution,
        capability_manifest=SimpleNamespace(capabilities=(SimpleNamespace(component_ref=component),)),
    )
    return SimpleNamespace(integrations=(owner,), class_names=frozenset({component}))


def _entry(provider, *, name="pilot", distribution="lfx-pilot", load=None):
    return SimpleNamespace(
        name=name,
        dist=SimpleNamespace(metadata={"Name": distribution}),
        load=load or (lambda: provider),
    )


def test_absent_manifest_never_imports_an_entry_point(discovery, provider):
    _snapshot, entries = discovery
    entries.append(_entry(provider, load=lambda: pytest.fail("An unowned entry point was loaded")))
    assert registry.get_provider("pilot") is None


def test_loaded_owner_enables_hooks_and_removal_invalidates_cache(discovery, provider):
    snapshot, entries = discovery
    snapshot["pilot"] = _record()
    entries.append(_entry(provider))
    assert registry.get_provider("pilot") is provider
    assert registry.component_kind("pilot", "PilotOnItemTriggerComponent") == "pilot.item"
    assert "pilot.item" in registry.source_kinds()
    assert "pilot.item" not in registry.collecting_kinds()
    assert "pilot.webhook" in registry.push_mechanisms()
    snapshot.clear()
    assert registry.get_provider("pilot") is None
    assert "pilot.item" not in registry.source_kinds()


@pytest.mark.parametrize("reason", ["foreign-distribution", "component", "provider", "duplicate", "broken-import"])
def test_conflicting_or_mismatched_hooks_fail_closed(discovery, provider, reason):
    snapshot, entries = discovery
    snapshot["pilot"] = _record(component="OtherComponent" if reason == "component" else "PilotOnItemTriggerComponent")
    entry = _entry(provider, distribution="unrelated-package" if reason == "foreign-distribution" else "lfx-pilot")
    if reason == "provider":
        entry = _entry(
            replace(
                provider,
                provider_id="other",
                kinds=(replace(provider.kinds[0], kind="other.item", push_mechanism="other.webhook"),),
            )
        )
    if reason == "broken-import":

        def broken():
            msg = "Unavailable optional dependency"
            raise RuntimeError(msg)

        entry = _entry(provider, load=broken)
    entries.append(entry)
    if reason == "duplicate":
        entries.append(_entry(provider))
    assert registry.get_provider("pilot") is None


@pytest.mark.parametrize(
    "field",
    [
        "bot_token",
        "private_key",
        "privatekey",
        "password",
        "access_token",
        "signing_secret",
        "api_key",
        "apikey",
    ],
)
def test_credentials_cannot_be_canvas_configuration(provider, field):
    with pytest.raises(ValueError, match="invalid or duplicate"):
        replace(provider, kinds=(replace(provider.kinds[0], config_fields=("connection", field)),))


@pytest.mark.parametrize("mechanism", ["google.poll", "pilot.bad space", "pilot.bad\n"])
def test_provider_cannot_claim_foreign_or_malformed_mechanisms(provider, mechanism):
    with pytest.raises(ValueError, match="invalid or duplicate"):
        replace(provider, kinds=(replace(provider.kinds[0], push_mechanism=mechanism),))


def test_push_and_poll_hooks_are_required_for_their_declared_transports(provider):
    with pytest.raises(ValueError, match="signature verifier"):
        replace(provider, verify=None)
    with pytest.raises(ValueError, match="collector"):
        replace(provider, kinds=(replace(provider.kinds[0], poll_mechanism="pilot.poll"),))


def test_reloaded_bundle_cannot_keep_a_removed_component(discovery, provider):
    snapshot, entries = discovery
    snapshot["pilot"] = _record()
    entries.append(_entry(provider))
    assert registry.get_provider("pilot") is provider
    snapshot["pilot"] = _record(component="RemovedComponent")
    assert registry.get_provider("pilot") is None
