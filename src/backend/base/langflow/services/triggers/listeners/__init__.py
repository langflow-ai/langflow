"""The supervised listener process (TRG-3).

``langflow listeners`` is the Track B half of the triggers design: Langflow
dials out to a provider and holds the connection, so an instance with no public
ingress still fires triggers. It is a separate process by decision, not by
accident - see ``design/dedicated-integrations-triggers/decisions/process-model.md``.

The pieces, in the order a connection travels through them:

``supervisor``
    Reconciles the trigger table against the connections this replica holds,
    claims a lease per connection, and owns backoff and failure reporting.
``connection_leases``
    One ``trigger_listener_lease`` row per connection, so exactly one replica
    holds each one.
``adapters``
    The ``start``/``stop``/``healthy`` seam a provider source implements, the
    generic poll loop, and the self-test adapter TRG-3 ships.
``health``
    ``/health`` and ``/healthz``, served without a FastAPI app.
``runtime``
    The process entry point: boot services, supervise, shut down on SIGTERM.
``subprocess_host``
    The API-lifespan child for the single-container and Desktop shapes.
``guard``
    The flag that makes "no HTTP app in this process" enforceable.
"""

from langflow.services.triggers.listeners.adapters import (
    ListenerAdapter,
    ListenerContext,
    ListenerTrigger,
    PollingListenerAdapter,
    register_adapter,
    register_builtin_adapters,
)
from langflow.services.triggers.listeners.guard import is_listener_process, mark_listener_process
from langflow.services.triggers.listeners.health import ListenerHealthServer
from langflow.services.triggers.listeners.runtime import run_listeners
from langflow.services.triggers.listeners.subprocess_host import (
    ListenerSubprocess,
    start_listener_subprocess_if_enabled,
)
from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

__all__ = [
    "ListenerAdapter",
    "ListenerContext",
    "ListenerHealthServer",
    "ListenerSubprocess",
    "ListenerSupervisor",
    "ListenerTrigger",
    "PollingListenerAdapter",
    "is_listener_process",
    "mark_listener_process",
    "register_adapter",
    "register_builtin_adapters",
    "run_listeners",
    "start_listener_subprocess_if_enabled",
]
