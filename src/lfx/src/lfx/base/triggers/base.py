"""The shape every trigger component shares.

A trigger node is a *declaration*, not a runtime: it never listens, polls, or
calls a provider. It describes a trigger the server reconciles into a ``trigger``
row on every flow save, and at run time it hands the firing event to the rest of
the flow as ``Data``.

That split is what lets one schedule fire correctly across three replicas: the
canvas holds the configuration, the database holds the state, and the leased
dispatcher holds the work. A component that opened its own connection would put
one listener in every worker process.

**How the event arrives.** The dispatcher puts the firing event on the run
request's ``tweaks``, keyed by this node's canvas id, under
:data:`TRIGGER_EVENT_FIELD` and serialized as JSON — the same mechanism the
Webhook component's payload rides. The tweak lands on this component's template
before the graph is built, so by the time :meth:`build_event` runs the value is
simply an input. Two consequences worth knowing:

* a run nobody triggered (canvas Play, a plain API run) leaves the field empty
  and yields an empty ``Data`` rather than failing, so an owner can build the
  downstream flow before arming anything;
* under a non-permissive ``tweaks_policy`` the deployment refuses caller-supplied
  tweaks and the event does not arrive — the same exposure the Webhook component
  already has. Triggers are unusable on such a deployment until the policy grows
  a notion of runtime-injected fields; TRG-7 tracks it.

Provider trigger components (TRG-5 Slack, TRG-6 Microsoft and Google) subclass
this, declare their ``trigger_kind``/``provider``, and add their own inputs; the
event field is prepended for them automatically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output
from lfx.schema.data import Data

#: Template field the server writes the firing event into. Equal, character for
#: character, to ``langflow.services.triggers.constants.TRIGGER_EVENT_FIELD``
#: (lfx must not import langflow, so the contract is a shared literal pinned by
#: a test on the backend side).
TRIGGER_EVENT_FIELD = "event_payload"


def _event_payload_input() -> MultilineInput:
    """A fresh input instance for one trigger class.

    Fresh rather than shared: every subclass gets its own template entry, and a
    shared ``Input`` object would be mutated by whichever class touched it last.
    """
    return MultilineInput(
        name=TRIGGER_EVENT_FIELD,
        display_name="Event",
        info=(
            "Set by the server when this trigger fires: the JSON event the run was started with. "
            "Leave it empty; a manual run simply reports that no trigger event was present. "
            "Paste an event here to rehearse the downstream flow by hand."
        ),
        input_types=[],
        advanced=True,
    )


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
    implement :meth:`trigger_config`. Everything else — the event input, the
    event output, the definition the reconciler reads — is shared.
    """

    #: Registry key for this trigger, matching the ``kind`` column on ``trigger``.
    trigger_kind: str = ""
    #: Provider id for provider-backed triggers; None for core triggers.
    provider: str | None = None
    #: True when the trigger cannot arm without a connection (TRG-5/TRG-6).
    needs_connection: bool = False

    inputs = [_event_payload_input()]

    outputs = [
        Output(display_name="Event", name="trigger_event", method="build_event"),
    ]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Prepend the event input to every subclass that declares its own inputs.

        ``Component`` reads ``inputs`` off the class, so a subclass that sets its
        own list replaces this one wholesale. Rather than asking every provider
        trigger to remember the shared field — a thing that fails silently, by
        the trigger firing into an empty flow — it is added here.
        """
        super().__init_subclass__(**kwargs)
        declared = getattr(cls, "inputs", None)
        if not isinstance(declared, list):
            return
        if any(getattr(entry, "name", None) == TRIGGER_EVENT_FIELD for entry in declared):
            return
        cls.inputs = [_event_payload_input(), *declared]

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

        A manual run (canvas Play, no trigger event on the request) yields an
        empty ``Data`` rather than failing, so an owner can build and test the
        downstream flow before arming anything. An event that will not parse is
        reported the same way: the payload comes from a provider, and a run that
        dies before the flow starts tells the owner less than one that says the
        event could not be read.
        """
        event, problem = self._firing_event()
        if problem is not None:
            self.status = problem
            return Data(data={})
        if not event:
            self.status = "No trigger event: this run was not started by a trigger."
            return Data(data={})
        self.status = f"{event.get('kind', self.trigger_kind)} event {event.get('event_id', '')}"
        return Data(data=event)

    def _firing_event(self) -> tuple[dict[str, Any], str | None]:
        """Read the event the dispatcher attached to this run.

        Returns ``(event, problem)``: an empty event and no problem when this
        run was not triggered, and an empty event with a message when one was
        attached but could not be read.
        """
        raw = getattr(self, TRIGGER_EVENT_FIELD, None)
        if isinstance(raw, dict):
            return raw, None
        if not isinstance(raw, str) or not raw or raw.isspace():
            return {}, None
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return {}, "The trigger event could not be read: it is not valid JSON."
        if not isinstance(event, dict):
            return {}, "The trigger event could not be read: it is not a JSON object."
        return event, None
