"""Typed trigger failures.

Every error here is a *contract* failure the caller can act on. Provider and
credential failures are not modelled here: they surface through the connection
resolver's sanitized ``IntegrationError`` family so a trigger run leaks no more
than an interactive run does.
"""

from __future__ import annotations


class TriggerError(Exception):
    """Base class for trigger contract failures."""


class TriggerNotFoundError(TriggerError):
    """No trigger with that id is visible to the caller.

    Raised (and rendered as 404) for both "does not exist" and "not yours" so a
    trigger id is not an existence oracle.
    """


class TriggerEventNotFoundError(TriggerError):
    """No ledger row with that id belongs to the trigger."""


class BindingUnsupportedError(TriggerError):
    """The trigger's binding target cannot be dispatched by this release.

    1.13 dispatches ``flow`` targets (saved flow, or the pinned ``flow_version``)
    through the background execution service. Deployments execute through
    provider adapters as an external data plane with a different principal and no
    ``Job`` row, so a ``deployment`` binding is stored and reported, never
    silently rewritten into a flow run.
    """

    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(
            f"Trigger binding target {target!r} is stored but not dispatched in this release; "
            "re-bind the trigger to its flow to run it."
        )


class ReplayWindowExpiredError(TriggerError):
    """The event is older than the configured replay window."""

    def __init__(self, retention_days: int) -> None:
        self.retention_days = retention_days
        super().__init__(f"Event is outside the {retention_days}-day replay window.")


class TriggerConflictError(TriggerError):
    """A trigger already exists for that flow node."""
