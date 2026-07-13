"""Tests for the two-tier service wiring machinery on the ServiceManager.

Covers the mechanisms that make the pluggable service seam safe:
port validation (all sources), declared ``requires`` with capability
enforcement, the tier layering invariant, dependency-cycle detection, and the
capability-based wiring manifest / fingerprint.
"""

from __future__ import annotations

import pytest
from lfx.services.base import Service
from lfx.services.capabilities import Capability, Requires, ServiceWiringError, Tier
from lfx.services.manager import ServiceManager
from lfx.services.schema import ServiceType


class _Svc(Service):
    """Minimal concrete Service for building synthetic graphs."""

    _name = "cache_service"

    @property
    def name(self) -> str:
        return self._name

    async def teardown(self) -> None:
        return None


def _service(name, *, tier=None, capabilities=frozenset(), requires=(), init=None):
    """Build a Service subclass with the given wiring declarations."""
    ns = {
        "name": name,
        "tier": tier,
        "capabilities": capabilities,
        "requires": requires,
        "teardown": _Svc.teardown,
    }
    if init is not None:
        ns["__init__"] = init
    return type(f"Svc_{name}", (Service,), ns)


# --------------------------------------------------------------------------
# Port validation
# --------------------------------------------------------------------------


def test_port_validation_rejects_non_subclass():
    """A class that is not a MemoryService subclass is refused for MEMORY_SERVICE."""
    mgr = ServiceManager()

    class NotAMemoryService:
        name = "memory_service"

    mgr.register_service_class(ServiceType.MEMORY_SERVICE, NotAMemoryService, override=True)
    assert ServiceType.MEMORY_SERVICE not in mgr.service_classes


def test_port_validation_accepts_real_subclass():
    """The real InMemoryMemoryService passes port validation."""
    from lfx.services.memory.service import InMemoryMemoryService

    mgr = ServiceManager()
    mgr.register_service_class(ServiceType.MEMORY_SERVICE, InMemoryMemoryService, override=True)
    assert mgr.service_classes[ServiceType.MEMORY_SERVICE] is InMemoryMemoryService


def test_unlisted_service_type_skips_port_validation():
    """A service type with no declared port registers without validation."""
    mgr = ServiceManager()

    class AnyCache(Service):
        name = "cache_service"

        async def teardown(self) -> None:
            return None

    mgr.register_service_class(ServiceType.CACHE_SERVICE, AnyCache, override=True)
    assert mgr.service_classes[ServiceType.CACHE_SERVICE] is AnyCache


# --------------------------------------------------------------------------
# Capability enforcement
# --------------------------------------------------------------------------


def test_missing_capability_raises_wiring_error():
    """A dependent requiring PERSISTENT fails against a capability-less dependency."""
    weak_db = _service("database_service", tier=Tier.INFRASTRUCTURE, capabilities=frozenset())
    mem = _service(
        "memory_service",
        tier=Tier.COMPOSED,
        requires=(Requires(ServiceType.DATABASE_SERVICE, frozenset({Capability.PERSISTENT})),),
    )
    mgr = ServiceManager()
    mgr.service_classes[ServiceType.DATABASE_SERVICE] = weak_db
    mgr.service_classes[ServiceType.MEMORY_SERVICE] = mem

    with pytest.raises(ServiceWiringError, match="persistent"):
        mgr.validate_wiring(discover=False)


def test_satisfied_capability_passes():
    """The same requirement passes against a PERSISTENT-capable dependency."""
    strong_db = _service("database_service", tier=Tier.INFRASTRUCTURE, capabilities=frozenset({Capability.PERSISTENT}))
    mem = _service(
        "memory_service",
        tier=Tier.COMPOSED,
        requires=(Requires(ServiceType.DATABASE_SERVICE, frozenset({Capability.PERSISTENT})),),
    )
    mgr = ServiceManager()
    mgr.service_classes[ServiceType.DATABASE_SERVICE] = strong_db
    mgr.service_classes[ServiceType.MEMORY_SERVICE] = mem

    manifest = mgr.validate_wiring(discover=False)
    assert manifest[ServiceType.MEMORY_SERVICE].impl_class == mem.__name__


def test_presence_only_requirement_passes_against_capability_less_dep():
    """A presence-only Requires (empty capability set) accepts any implementation."""
    noop_db = _service("database_service", tier=Tier.INFRASTRUCTURE, capabilities=frozenset())
    mem = _service("memory_service", tier=Tier.COMPOSED, requires=(Requires(ServiceType.DATABASE_SERVICE),))
    mgr = ServiceManager()
    mgr.service_classes[ServiceType.DATABASE_SERVICE] = noop_db
    mgr.service_classes[ServiceType.MEMORY_SERVICE] = mem

    # No raise: memory requires the DB to be present, not persistent.
    mgr.validate_wiring(discover=False)


def test_missing_dependency_raises():
    """A required dependency with no registered implementation fails validation."""
    mem = _service("memory_service", tier=Tier.COMPOSED, requires=(Requires(ServiceType.DATABASE_SERVICE),))
    mgr = ServiceManager()
    mgr.service_classes[ServiceType.MEMORY_SERVICE] = mem

    with pytest.raises(ServiceWiringError, match="no implementation is registered"):
        mgr.validate_wiring(discover=False)


# --------------------------------------------------------------------------
# Tier layering invariant
# --------------------------------------------------------------------------


def test_tier1_requiring_tier2_is_a_layering_violation():
    """A Tier 1 service that depends on a Tier 2 service fails validation."""
    bad_infra = _service("database_service", tier=Tier.INFRASTRUCTURE, requires=(Requires(ServiceType.MEMORY_SERVICE),))
    some_mem = _service("memory_service", tier=Tier.COMPOSED)
    mgr = ServiceManager()
    mgr.service_classes[ServiceType.DATABASE_SERVICE] = bad_infra
    mgr.service_classes[ServiceType.MEMORY_SERVICE] = some_mem

    with pytest.raises(ServiceWiringError, match="Layering violation"):
        mgr.validate_wiring(discover=False)


def test_tier2_may_depend_on_tier1():
    """A Tier 2 service depending on a Tier 1 service is allowed."""
    db = _service("database_service", tier=Tier.INFRASTRUCTURE)
    mem = _service("memory_service", tier=Tier.COMPOSED, requires=(Requires(ServiceType.DATABASE_SERVICE),))
    mgr = ServiceManager()
    mgr.service_classes[ServiceType.DATABASE_SERVICE] = db
    mgr.service_classes[ServiceType.MEMORY_SERVICE] = mem
    mgr.validate_wiring(discover=False)


# --------------------------------------------------------------------------
# Cycle detection
# --------------------------------------------------------------------------


def test_dependency_cycle_detected_on_create():
    """A -> B -> A cycle raises ServiceWiringError during creation."""

    def init_a(self, storage_service):
        self.storage_service = storage_service

    def init_b(self, cache_service):
        self.cache_service = cache_service

    svc_a = _service("cache_service", init=init_a)
    svc_b = _service("storage_service", init=init_b)
    mgr = ServiceManager()
    mgr.service_classes[ServiceType.CACHE_SERVICE] = svc_a
    mgr.service_classes[ServiceType.STORAGE_SERVICE] = svc_b

    with pytest.raises(ServiceWiringError, match="cycle"):
        mgr.get(ServiceType.CACHE_SERVICE)


# --------------------------------------------------------------------------
# Manifest and fingerprint
# --------------------------------------------------------------------------


def test_fingerprint_is_capability_based_not_class_based():
    """Two different classes with identical capabilities share a fingerprint."""
    caps = frozenset({Capability.QUERYABLE, Capability.PERSISTENT})
    mem_a = _service("memory_service", tier=Tier.COMPOSED, capabilities=caps)
    mem_b = _service("memory_service", tier=Tier.COMPOSED, capabilities=caps)

    def fp(cls):
        mgr = ServiceManager()
        mgr.service_classes[ServiceType.MEMORY_SERVICE] = cls
        return mgr.wiring_fingerprint(discover=False)

    assert mem_a is not mem_b
    assert fp(mem_a) == fp(mem_b)


def test_fingerprint_changes_when_capabilities_differ():
    """Adding a capability changes the fingerprint (behavioral divergence is caught)."""
    base = frozenset({Capability.QUERYABLE, Capability.PERSISTENT})
    mem_base = _service("memory_service", tier=Tier.COMPOSED, capabilities=base)
    mem_shared = _service("memory_service", tier=Tier.COMPOSED, capabilities=base | {Capability.SHARED})

    def fp(cls):
        mgr = ServiceManager()
        mgr.service_classes[ServiceType.MEMORY_SERVICE] = cls
        return mgr.wiring_fingerprint(discover=False)

    assert fp(mem_base) != fp(mem_shared)


def test_manifest_reports_impl_tier_and_capabilities():
    """The manifest records the resolved class, tier, and capabilities per type."""
    from lfx.services.memory.service import InMemoryMemoryService

    mgr = ServiceManager()
    mgr.service_classes[ServiceType.MEMORY_SERVICE] = InMemoryMemoryService
    manifest = mgr.wiring_manifest(discover=False)

    entry = manifest[ServiceType.MEMORY_SERVICE]
    assert entry.impl_class == "InMemoryMemoryService"
    assert entry.tier == int(Tier.COMPOSED)
    assert Capability.QUERYABLE in entry.capabilities
