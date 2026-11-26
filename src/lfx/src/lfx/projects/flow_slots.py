"""The executable project binding shapes, shared by saves, discovery, and archives."""

from pydantic import BaseModel, ConfigDict, Field

from lfx.base.agents.hooks import HookBinding
from lfx.projects.bindings import FlowBinding, instruction_outputs, validate_instruction_binding
from lfx.projects.hooks import hook_outputs, validate_hook_binding

BINDING_LABELS = {"system_prompt": "Instructions", "hooks": "Hooks"}


class ProjectFlowBindings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    system_prompt: FlowBinding | None = None
    hooks: list[HookBinding] = Field(default_factory=list)

    def entries(self) -> list[tuple[str, FlowBinding]]:
        return ([("system_prompt", self.system_prompt)] if self.system_prompt else []) + [
            ("hooks", binding) for binding in self.hooks
        ]


def binding_outputs(field_name: str, data: dict) -> list[dict]:
    if field_name == "system_prompt":
        return instruction_outputs(data)
    if field_name == "hooks":
        return hook_outputs(data)
    msg = "This field does not yet support flow bindings."
    raise ValueError(msg)


def validate_project_binding(field_name: str, data: dict, binding: FlowBinding) -> None:
    if field_name == "system_prompt":
        validate_instruction_binding(data, binding)
    elif field_name == "hooks" and isinstance(binding, HookBinding):
        validate_hook_binding(data, binding)
    else:
        msg = "This field does not yet support flow bindings."
        raise ValueError(msg)
