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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.inputs.inputs import InputTypes


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
