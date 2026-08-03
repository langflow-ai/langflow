"""Catalog-policy contract tests."""

from dataclasses import FrozenInstanceError

import pytest
from lfx.services.catalog_policy import BaseCatalogPolicyService, CatalogPolicyService, CatalogPolicySnapshot
from lfx.services.schema import ServiceType


def test_empty_default_is_fail_open_for_single_and_batch_decisions():
    service = CatalogPolicyService()

    assert service.ready is True
    assert service.external_policy_snapshot is None
    assert service.enabled is False
    assert service.is_component_blocked("OpenAIModel") is False
    assert service.is_template_blocked("starter-template") is False
    assert service.is_component_allowed("OpenAIModel") is True
    assert service.is_template_allowed("starter-template") is True
    assert service.blocked_component_keys(["OpenAIModel", "Agent"]) == frozenset()
    assert service.blocked_template_keys(["starter-template"]) == frozenset()


def test_snapshot_is_immutable_and_supports_batch_decisions():
    snapshot = CatalogPolicySnapshot(
        blocked_component_keys=frozenset({"OpenAIModel", "Agent"}),
        blocked_template_keys=frozenset({"starter-template"}),
    )

    assert snapshot.enabled is True
    assert snapshot.is_component_blocked("Agent") is True
    assert snapshot.is_component_blocked("agent") is False
    assert snapshot.is_template_blocked("starter-template") is True
    assert snapshot.blocked_components(["Agent", "Agent", "Other"]) == frozenset({"Agent"})
    assert snapshot.blocked_templates(["other", "starter-template"]) == frozenset({"starter-template"})
    with pytest.raises(FrozenInstanceError):
        snapshot.blocked_component_keys = frozenset()  # type: ignore[misc]


def test_dependency_installs_stable_fail_open_fallback_for_broken_plugin(monkeypatch):
    from lfx.services import deps
    from lfx.services import manager as manager_module
    from lfx.services.manager import ServiceManager

    class BrokenCatalogPolicyService(BaseCatalogPolicyService):
        attempts = 0

        def __init__(self) -> None:
            type(self).attempts += 1
            message = "broken catalog policy plugin"
            raise RuntimeError(message)

        @property
        def snapshot(self) -> CatalogPolicySnapshot:
            return CatalogPolicySnapshot()

    manager = ServiceManager()
    manager._plugins_discovered = True
    manager.register_service_class(
        ServiceType.CATALOG_POLICY_SERVICE,
        BrokenCatalogPolicyService,
        override=True,
    )
    monkeypatch.setattr(manager_module, "_service_manager", manager)
    monkeypatch.setattr(deps, "_catalog_policy_fallback", None)

    first = deps.get_catalog_policy_service()
    second = deps.get_catalog_policy_service()

    assert first is second
    assert isinstance(first, CatalogPolicyService)
    assert first.is_component_allowed("anything") is True
    assert first.is_template_allowed("anything") is True
    assert manager.services[ServiceType.CATALOG_POLICY_SERVICE] is first
    assert BrokenCatalogPolicyService.attempts == 1
