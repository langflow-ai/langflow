"""Base service classes for lfx package."""

from abc import ABC, abstractmethod
from typing import ClassVar

from lfx.services.capabilities import Capability, Requires, Tier


class Service(ABC):
    """Base service class.

    Subclasses may declare three class attributes that the service manager reads
    *without instantiating the service* to resolve and validate wiring (see
    ``lfx.services.capabilities`` and ``ServiceManager.validate_wiring``):

    - ``tier`` — layering position (Tier 1 infrastructure vs Tier 2 composed).
      ``None`` (the default) opts a service out of the layering check.
    - ``capabilities`` — quality attributes this implementation guarantees.
      Compared against dependents' ``Requires`` and hashed into the wiring
      fingerprint.
    - ``requires`` — declared dependencies on other service types, optionally
      constrained by capability. Resolved before ``__init__`` and injected by
      the manager.

    These are declarations about the *class*, so they are class attributes, not
    instance state — the manager reasons about the whole graph before any
    service is built.
    """

    # Wiring declarations (class-level; read pre-instantiation by the manager).
    tier: ClassVar[Tier | None] = None
    capabilities: ClassVar[frozenset[Capability]] = frozenset()
    requires: ClassVar[tuple[Requires, ...]] = ()

    def __init__(self):
        self._ready = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Service name."""

    def set_ready(self) -> None:
        """Mark service as ready."""
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if service is ready."""
        return self._ready

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the service."""
