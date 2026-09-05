"""The shape every trigger component shares.

A trigger node is a *declaration*, not a runtime: it never listens, polls, or
calls a provider. It describes a trigger the server reconciles into a ``trigger``
row on every flow save, and at run time it hands the firing event to the rest of
the flow as ``Data``.

That split is what lets one schedule fire correctly across three replicas: the
canvas holds the configuration, the database holds the state, and the leased
dispatcher holds the work. A component that opened its own connection would put
one listener in every worker process.

Provider trigger components (TRG-5 Slack, TRG-6 Microsoft and Google) subclass
this, declare their ``trigger_kind``/``provider``, and add their own inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

#: The key the server puts the firing event under in the run's payload.
TRIGGER_EVENT_KEY = "trigger_event"


@dataclass(frozen=True)
class TriggerDefinition:
    """What a trigger node asks the server to reconcile into a trigger row.

    Deliberately small and JSON-shaped: it crosses from the canvas into the
    database and back, and later tickets add provider fields to ``config``
    without changing this contract.
    """

    kind: str
    name: str
    provider: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    needs_connection: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "provider": self.provider,
            "config": dict(self.config),
            "needs_connection": self.needs_connection,
        }


class BaseTriggerComponent(Component):
    """Base class for trigger nodes.

    Subclasses set ``trigger_kind`` (and ``provider`` where one applies) and
    implement :meth:`trigger_config`. Everything else — the event output, the
    definition the reconciler reads — is shared.
    """

    #: Registry key for this trigger, matching the ``kind`` column on ``trigger``.
    trigger_kind: str = ""
    #: Provider id for provider-backed triggers; None for core triggers.
    provider: str | None = None
    #: True when the trigger cannot arm without a connection (TRG-5/TRG-6).
    needs_connection: bool = False

    outputs = [
        Output(display_name="Event", name="trigger_event", method="build_event"),
    ]

    def trigger_config(self) -> dict[str, Any]:
        """Return the JSON configuration the server stores on the trigger row."""
        return {}

    def trigger_definition(self) -> TriggerDefinition:
        """The full declaration the flow-save reconciler turns into a row."""
        if not self.trigger_kind:
            msg = f"{type(self).__name__} must set trigger_kind"
            raise ValueError(msg)
        return TriggerDefinition(
            kind=self.trigger_kind,
            name=self.display_name or self.trigger_kind,
            provider=self.provider,
            config=self.trigger_config(),
            needs_connection=self.needs_connection,
        )

    def build_event(self) -> Data:
        """Hand the firing event to the rest of the flow.

        A manual run (canvas Play, no trigger event in the payload) yields an
        empty ``Data`` rather than failing, so an owner can build and test the
        downstream flow before arming anything.
        """
        event = self._firing_event()
        if not event:
            self.status = "No trigger event: this run was not started by a trigger."
            return Data(data={})
        self.status = f"{event.get('kind', self.trigger_kind)} event {event.get('event_id', '')}"
        return Data(data=event)

    def _firing_event(self) -> dict[str, Any]:
        """Read the event the dispatcher attached to this run, if any."""
        graph = getattr(self, "graph", None)
        for source in (getattr(graph, "context", None), getattr(self, "_attributes", None)):
            if isinstance(source, dict):
                event = source.get(TRIGGER_EVENT_KEY)
                if isinstance(event, dict):
                    return event
        return {}
