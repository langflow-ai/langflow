"""Canonical port (base class) for each pluggable ``ServiceType``.

A *port* is the abstract base every implementation of a service type must
subclass. Registering a class that is not a subclass of the declared port is
rejected at registration time, for **all** discovery sources (decorator, config
file, entry point) — not just entry points. This prevents an unrelated class
(e.g. one from a third-party package that happens to reuse a service key) from
silently replacing a built-in service.

Only service types with a formalized port are listed. Types absent from this map
are not validated (back-compat for services that predate the port model); the
map is intended to grow to cover every ``ServiceType`` as each port is written.

Ports are stored as ``"module:ClassName"`` strings and imported lazily on first
use, so importing this module stays cheap and free of import cycles.
"""

from __future__ import annotations

from lfx.services.config_discovery import load_object_from_import_path
from lfx.services.schema import ServiceType

# ServiceType -> "module:ClassName" of the abstract port each implementation
# must subclass. Grows one entry per port as services are formalized.
SERVICE_PORTS: dict[ServiceType, str] = {
    ServiceType.MEMORY_SERVICE: "lfx.services.memory.base:MemoryService",
    ServiceType.AUTHORIZATION_SERVICE: "lfx.services.authorization.base:BaseAuthorizationService",
}


def get_expected_port(service_type: ServiceType) -> type | None:
    """Return the port base class for ``service_type``, or ``None`` if unlisted.

    Import failures are treated as "no port declared" (returns ``None``) so a
    missing optional dependency degrades to no validation rather than blocking
    registration entirely — the same lenient stance the manager already took for
    the authorization port.
    """
    import_path = SERVICE_PORTS.get(service_type)
    if import_path is None:
        return None
    port = load_object_from_import_path(import_path, object_kind="port", object_key=service_type.value)
    return port if isinstance(port, type) else None
