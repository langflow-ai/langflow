"""Tests for langflow's MEMORY_SERVICE wiring (converged on the lfx Tier 2 service).

Langflow no longer defines its own memory service or sniffs the database backend
at call time. It *selects* lfx's ``DatabaseMemoryService`` and the service manager
injects langflow's Tier 1 ``DatabaseService`` (Option B). These tests assert the
registration/wiring; behavioral equivalence across backends is covered by the
shared contract suite in lfx (``lfx.services.memory.contract``).
"""

import pytest
from langflow.services.memory import DatabaseMemoryService
from lfx.services.capabilities import Capability, ServiceWiringError, Tier
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType


def test_langflow_selects_lfx_database_memory_service():
    """After registration, MEMORY_SERVICE resolves to the lfx DatabaseMemoryService class."""
    from langflow.services.utils import register_all_service_factories

    register_all_service_factories()
    manager = get_service_manager()

    # The registered class (no instantiation needed) is the converged lfx impl —
    # langflow authors no memory subclass of its own.
    assert manager.service_classes[ServiceType.MEMORY_SERVICE] is DatabaseMemoryService


def test_memory_is_tier2_requiring_database():
    """DatabaseMemoryService is Tier 2 and declares a dependency on the database service."""
    assert DatabaseMemoryService.tier == Tier.COMPOSED
    assert Capability.PERSISTENT in DatabaseMemoryService.capabilities
    required = {req.service for req in DatabaseMemoryService.requires}
    assert ServiceType.DATABASE_SERVICE in required


def test_memory_requires_database_presence_only():
    """The requirement is presence, not a capability — so any DB backend satisfies it."""
    db_reqs = [req for req in DatabaseMemoryService.requires if req.service is ServiceType.DATABASE_SERVICE]
    assert db_reqs, "expected a database_service requirement"
    # Empty capability set => presence-only (bare lfx run over an ephemeral DB is fine).
    assert all(req.capabilities == frozenset() for req in db_reqs)


def test_manifest_reports_langflow_wiring():
    """The wiring manifest reports memory (Tier 2) and database (Tier 1) after registration."""
    from langflow.services.utils import register_all_service_factories

    register_all_service_factories()
    manager = get_service_manager()
    manifest = manager.wiring_manifest(discover=False)

    memory_entry = manifest[ServiceType.MEMORY_SERVICE]
    assert memory_entry.impl_class == "DatabaseMemoryService"
    assert memory_entry.tier == int(Tier.COMPOSED)

    db_entry = manifest[ServiceType.DATABASE_SERVICE]
    assert db_entry.tier == int(Tier.INFRASTRUCTURE)
    assert Capability.PERSISTENT in db_entry.capabilities


def test_validate_wiring_passes_for_langflow_stack():
    """The full langflow registration validates without raising (deps + capabilities satisfied)."""
    from langflow.services.utils import register_all_service_factories

    register_all_service_factories()
    manager = get_service_manager()
    # Should not raise: memory (Tier 2) requires database (Tier 1) presence, which is registered.
    try:
        manager.validate_wiring(discover=False)
    except ServiceWiringError as exc:  # pragma: no cover - failure path
        pytest.fail(f"langflow wiring failed validation: {exc}")
