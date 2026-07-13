"""Service tiers, capabilities, and declared dependencies.

This module holds the small vocabulary the service manager uses to reason about
*wiring* — which service implementations are registered and whether they can
satisfy each other — **before** any service is instantiated.

Three concepts:

- ``Tier`` — the layering position of a service. ``INFRASTRUCTURE`` (Tier 1)
  services integrate one external component and speak generic primitives
  (sessions, bytes, key/value, spans). ``COMPOSED`` (Tier 2) services own domain
  behavior over lfx-owned models and delegate the actual commit/read to Tier 1
  services. The layering invariant is one-way: a Tier 1 service may only depend
  on ``settings`` or other Tier 1 services; a Tier 1 that requires a Tier 2 is a
  layering violation.

- ``Capability`` — a quality attribute an implementation provides (e.g. does its
  state survive a restart, is it visible across processes). Capabilities are the
  unit of comparison for "does dependency X satisfy dependent Y" and for the
  builder-vs-production wiring fingerprint. They are deliberately coarse: they
  describe *what an implementation guarantees*, never *which class provides it*.

- ``Requires`` — a declared dependency edge from a dependent service onto another
  ``ServiceType``, optionally constrained to require certain capabilities of the
  resolved implementation.

All three are declared as **class attributes** on services (see
``lfx.services.base.Service``) so the manager can resolve and validate the whole
dependency graph without constructing anything (no DB connections, no side
effects). See ``ServiceManager.validate_wiring``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.services.schema import ServiceType


class Tier(IntEnum):
    """Layering position of a service.

    ``INFRASTRUCTURE`` (1) services are leaf integrations over external
    components. ``COMPOSED`` (2) services compose Tier 1 services plus domain
    logic. The numeric ordering encodes the allowed dependency direction:
    a service may only depend on services at the same or a lower tier.
    """

    INFRASTRUCTURE = 1
    COMPOSED = 2


class Capability(str, Enum):
    """A quality attribute an implementation guarantees.

    Kept deliberately small and coarse. These describe behavior, not
    implementation — two different classes that both persist to a shared
    Postgres advertise the same ``{PERSISTENT, SHARED}`` set, and the wiring
    fingerprint treats them as equivalent.
    """

    # State survives a process restart (backed by durable storage).
    PERSISTENT = "persistent"
    # State is visible across processes/pods (safe for a disaggregated,
    # multi-replica worker-plane), not just within one process.
    SHARED = "shared"
    # Supports filtered/ordered reads, not just fire-and-forget writes.
    QUERYABLE = "queryable"


@dataclass(frozen=True)
class Requires:
    """A declared dependency of one service on another ``ServiceType``.

    Args:
        service: The ``ServiceType`` this service depends on.
        capabilities: Capabilities the *resolved* implementation of ``service``
            must provide. Empty (the default) means "any registered
            implementation will do" — i.e. the dependency is required to be
            *present*, but no quality attribute is demanded of it.
    """

    service: ServiceType
    capabilities: frozenset[Capability] = field(default_factory=frozenset)


class ServiceWiringError(RuntimeError):
    """Raised when the registered services cannot satisfy a declared requirement.

    Raised eagerly at ``validate_wiring()`` (boot) rather than lazily on first
    service access, so a misconfigured deployment fails before it accepts
    traffic instead of mid-request. Causes include: a required dependency has no
    registered implementation, a dependency's implementation lacks a required
    capability, a Tier 1 service declares a dependency on a Tier 2 service
    (layering violation), or a dependency cycle.
    """


@dataclass(frozen=True)
class WiringManifestEntry:
    """One resolved service in a wiring manifest.

    Records the concrete implementation chosen for a ``ServiceType`` without
    instantiating it. ``capabilities`` is the load-bearing field for the
    fingerprint; ``impl_class`` and ``package`` are for humans and are
    deliberately excluded from the fingerprint (see
    ``ServiceManager.wiring_fingerprint``).
    """

    service_type: str
    impl_class: str
    package: str
    tier: int
    capabilities: frozenset[Capability]
