"""What a project type is.

A project type is a folder-level form. Each field is rendered by the same widget the canvas
already uses for a component input, which is why a field carries an ``lfx`` ``Input`` rather
than a bespoke descriptor: the input already serialises to exactly what the frontend's field
renderer reads.

A field may also declare where its value lands in the folder's flows. That is the rule the
whole design rests on: **the form writes through to the flow.** ``project_config`` records
what the user picked, and the value that actually runs is an input on a component in a flow
file, because a flow file is the only artifact both langflow and lfx load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.inputs.inputs import InputTypes


class Cardinality(str, Enum):
    SINGLE = "single"
    MULTI = "multi"


class FireTiming(str, Enum):
    ONCE_AT_SESSION_START = "once_at_session_start"
    ONCE_PER_RUN = "once_per_run"
    PER_LLM_CALL = "per_llm_call"
    ON_THRESHOLD = "on_threshold"
    PER_TOOL_CALL = "per_tool_call"
    ON_LLM_TOOL_CALL = "on_llm_tool_call"
    ON_EVENT = "on_event"
    ORCHESTRATOR = "orchestrator"
    ON_RUN = "on_run"
    ON_RESULT = "on_result"
    LOAD_TIME = "load_time"


@dataclass(frozen=True)
class SlotDefinition:
    """A reusable flow contract, independent of any project's form.

    The same Tool contract can appear on a harness and a tool pack with different labels,
    defaults, and write-through rules. Those belong to ``ProjectTypeField``. Timing describes
    the contract; registering a definition does not install a runtime handler. Output types
    are resolved when binding a flow, never by importing components during registration.
    """

    name: str
    terminal_output_type: str
    fire_timing: FireTiming
    cardinality: Cardinality = Cardinality.SINGLE
    default_flow_ref: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "terminal_output_type": self.terminal_output_type,
            "fire_timing": self.fire_timing.value,
            "cardinality": self.cardinality.value,
            "default_flow_ref": self.default_flow_ref,
        }


@dataclass(frozen=True)
class FieldTarget:
    """Where a form field's value is written inside the project's flows.

    ``component_type`` is matched against a node's ``data.type`` (for example ``"Agent"``),
    and ``input_name`` is the key in that node's template.
    """

    component_type: str
    input_name: str


@dataclass(frozen=True)
class ProjectTypeField:
    """One field on a project type's form.

    ``section`` groups fields on the form. The UI renders one group per distinct section, in the
    order the sections first appear here, so the type decides how its own form reads.

    ``renders`` names a widget the project page supplies instead of the ordinary field renderer.
    A field needs one for either of two reasons: the canvas has no equivalent at all ("which
    flows in this project can the agent call" has no component behind it), or the canvas widget
    is built for a node a couple of hundred pixels wide where the page wants something fuller.
    Leave it empty and the field renders the way it would on the canvas.
    """

    name: str
    input: InputTypes
    writes_to: FieldTarget | None = None
    info: str = ""
    section: str = ""
    renders: str = ""
    slot_definition: SlotDefinition | None = None
    supports_flow_binding: bool = False
    show_when: dict[str, str] = field(default_factory=dict)
    option_labels: dict[str, str] = field(default_factory=dict)

    def to_template(self) -> dict:
        """Serialise for the API, in the shape the frontend field renderer expects."""
        rendered = self.input.model_dump(by_alias=True)
        rendered["name"] = self.name
        if self.info and not rendered.get("info"):
            rendered["info"] = self.info
        if self.section:
            rendered["section"] = self.section
        if self.renders:
            rendered["renders"] = self.renders
        if self.slot_definition is not None:
            rendered["flow_contract"] = self.slot_definition.to_dict()
        if self.show_when:
            rendered["show_when"] = dict(self.show_when)
        if self.option_labels:
            rendered["option_labels"] = dict(self.option_labels)
        if self.supports_flow_binding:
            rendered["supports_flow_binding"] = True
        return rendered


@dataclass(frozen=True)
class ProjectType:
    """A folder type: a name, how to present it, and the form it renders."""

    name: str
    display_name: str
    icon: str
    description: str = ""
    fields: tuple[ProjectTypeField, ...] = field(default_factory=tuple)

    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def sections(self) -> tuple[str, ...]:
        """The form's sections, in the order their first field declares them."""
        seen: dict[str, None] = {}
        for f in self.fields:
            seen.setdefault(f.section, None)
        return tuple(seen)

    def to_template(self) -> dict[str, dict]:
        """The whole form, keyed by field name."""
        return {f.name: f.to_template() for f in self.fields}
