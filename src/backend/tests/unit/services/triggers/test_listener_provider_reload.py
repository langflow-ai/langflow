"""Listener discovery follows the current trusted provider descriptor."""

from dataclasses import replace
from uuid import uuid4

import pytest
from langflow.services.triggers.listeners import adapters
from langflow.services.triggers.providers import registry


@pytest.mark.parametrize("provider_change", ["removed", "replaced", "listener-removed"])
def test_custom_listener_does_not_retain_an_obsolete_factory(monkeypatch, provider_change):
    calls = []

    def make_factory(label):
        # Both closures deliberately have the same module and qualified name.
        # Reloading a provider can replace code without changing either name.
        def factory(_trigger):
            calls.append(label)
            return adapters.SelfTestAdapter(interval_s=30)

        return factory

    original_factory = make_factory("old")
    replacement_factory = make_factory("current")
    kind = registry.TriggerKind(
        kind="pilot.item",
        component="PilotOnItemTriggerComponent",
        display_name="Pilot item",
        config_fields=("connection",),
        listener_mechanism="pilot.socket",
        listener_factory=original_factory,
    )
    provider = registry.TriggerProvider(
        provider_id="pilot", bundle="pilot", kinds=(kind,), normalize_config=lambda _kind, config: config
    )
    available = [provider]
    monkeypatch.setattr(registry, "all_providers", lambda: tuple(available))
    monkeypatch.setattr(adapters, "_REGISTRY", {})
    adapters.register_builtin_adapters()
    trigger = adapters.ListenerTrigger(
        id=uuid4(),
        flow_id=uuid4(),
        user_id=uuid4(),
        kind="pilot.item",
        provider="pilot",
        mechanism_id="pilot.socket",
    )
    assert adapters.build_adapter(trigger) is not None
    previous_spec = adapters.adapter_spec(trigger)
    assert calls == ["old"]

    async def collect(_trigger, _lease):
        pytest.fail("Constructing a listener must not collect a polling source")

    replacement_kind = (
        replace(kind, listener_factory=replacement_factory)
        if provider_change == "replaced"
        else replace(kind, listener_factory=None, listener_mechanism=None, poll_mechanism="pilot.poll")
    )
    available[:] = (
        [] if provider_change == "removed" else [replace(provider, kinds=(replacement_kind,), collect=collect)]
    )
    # No process reboot or second registration pass is required after reload.
    if provider_change == "replaced":
        assert adapters.adapter_spec(trigger) != previous_spec
        assert adapters.is_listener_kind(trigger)
        assert adapters.build_adapter(trigger) is not None
        assert calls == ["old", "current"]
    else:
        assert not adapters.is_listener_kind(trigger)
        assert adapters.build_adapter(trigger) is None
        assert ("pilot.item", "pilot.socket") not in adapters.registered_adapter_keys()
        assert calls == ["old"]
    # A stored kind cannot claim another provider's factory.
    assert adapters.build_adapter(replace(trigger, provider="other")) is None
