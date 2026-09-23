"""The project types that ship with Langflow.

Every field's default is the default the runtime already uses, so a harness created and left
alone behaves exactly like an Agent component dropped on a blank canvas. That is what makes
the form safe to save with nothing filled in.
"""

from __future__ import annotations

from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE
from lfx.base.agents.harness import harness_runtime_inputs
from lfx.inputs.inputs import IntInput, ModelInput, MultilineInput, StrInput
from lfx.projects.builtin_slots import COMPACTOR, CONTEXT_MANAGER, HOOK, INSTRUCTIONS, PERMISSION_GATE, TOOL
from lfx.projects.registry import register_project_type
from lfx.projects.schema import FieldTarget, ProjectType, ProjectTypeField

#: The type every folder has until it is given another one.
DEFAULT_PROJECT_TYPE = "flows"

FLOWS = register_project_type(
    ProjectType(
        name=DEFAULT_PROJECT_TYPE,
        display_name="Flows",
        icon="Folders",
        description="A plain project. Any flow can live here and nothing is composed for you.",
    )
)

AGENT_HARNESS = register_project_type(
    ProjectType(
        name="agent-harness",
        display_name="Agent Harness",
        icon="Bot",
        description=(
            "An agent built from the flows in this project. One flow is the agent; the others "
            "are the tools it can call."
        ),
        fields=(
            ProjectTypeField(
                name="system_prompt",
                section="Instructions",
                slot_definition=INSTRUCTIONS,
                supports_flow_binding=True,
                # The canvas renders a multiline field as one line plus a modal, which suits a
                # node. Instructions are the main thing written here, so the page gives them a
                # real editor instead.
                renders="long_text",
                writes_to=FieldTarget("Agent", "system_prompt"),
                input=MultilineInput(
                    name="system_prompt",
                    display_name="Instructions",
                    info="What the agent is for, and how it should behave.",
                    value=DEFAULT_SYSTEM_PROMPT_TEMPLATE,
                ),
            ),
            ProjectTypeField(
                name="model",
                section="Model",
                writes_to=FieldTarget("Agent", "model"),
                input=ModelInput(
                    name="model",
                    display_name="Model",
                    info="The model the agent reasons with.",
                    # Required on the component, optional on the form: a harness is valid the
                    # moment it is created and only needs a model to run.
                    required=False,
                    filters={"tool_calling": True},
                ),
            ),
            # The agent's tools are the other flows in this project. No canvas widget fits that
            # (they all edit one component's input), so the UI supplies the picker and this field
            # only says which flows were picked.
            ProjectTypeField(
                name="tools",
                section="Tools",
                renders="project_flows",
                slot_definition=TOOL,
                # No write-through target on purpose. The Agent's ``tools`` input holds tool
                # objects built from what the graph connects to it, so putting flow ids there
                # would break the run rather than configure it. The project config writer
                # composes the selected flows through lfx.projects.tools instead.
                input=StrInput(
                    name="tools",
                    display_name="Tools",
                    info="Flows in this project the agent can call.",
                    list=True,
                    value=[],
                ),
            ),
            ProjectTypeField(
                name="tool_packs",
                section="Tools",
                renders="project_refs",
                input=StrInput(
                    name="tool_packs",
                    display_name="Tool packs",
                    info="Reviewed tools from reusable Tool Pack projects.",
                    list=True,
                    value=[],
                    show=False,
                ),
            ),
            ProjectTypeField(
                name="n_messages",
                section="Runtime",
                writes_to=FieldTarget("Agent", "n_messages"),
                input=IntInput(
                    name="n_messages",
                    display_name="History messages",
                    info="Past messages loaded from memory. Context preparation selects what reaches each model call.",
                    value=100,
                ),
            ),
            *(
                ProjectTypeField(
                    name=inp.name,
                    section="Runtime",
                    input=inp,
                    writes_to=FieldTarget("Agent", inp.name),
                    supports_flow_binding=inp.name in {"context_strategy", "compaction", "tool_policy"},
                    option_labels={
                        "context_strategy": {"all": "All loaded messages", "recent_turns": "Recent complete turns"},
                        "compaction": {"off": "Off", "summarize": "Summarize older messages"},
                        "tool_policy": {
                            "tool_defaults": "Use tool settings",
                            "ask": "Ask before each call",
                            "deny": "Block all tools",
                        },
                    }.get(inp.name, {}),
                    show_when={
                        "context_turns": {"context_strategy": "recent_turns"},
                        "compaction_trigger_tokens": {"compaction": "summarize"},
                        "compaction_keep_messages": {"compaction": "summarize"},
                    }.get(inp.name, {}),
                    slot_definition={
                        "context_strategy": CONTEXT_MANAGER,
                        "compaction": COMPACTOR,
                        "tool_policy": PERMISSION_GATE,
                    }.get(inp.name),
                )
                for inp in harness_runtime_inputs()
            ),
            ProjectTypeField(
                name="hooks",
                section="Hooks",
                slot_definition=HOOK,
                supports_flow_binding=True,
                renders="hook_flows",
                input=StrInput(
                    name="hooks",
                    display_name="Hooks",
                    list=True,
                    value=[],
                    info="Ordered flows that observe or control model and tool calls.",
                ),
            ),
        ),
    )
)

TOOL_PACK = register_project_type(
    ProjectType(
        name="tool-pack",
        display_name="Tool Pack",
        icon="Package",
        description="Reusable tools supplied by the flows you select in this project.",
        fields=(
            ProjectTypeField(
                name="tools",
                section="Exported tools",
                renders="project_flows",
                slot_definition=TOOL,
                input=StrInput(
                    name="tools",
                    display_name="Exported tools",
                    info="Choose the flows other projects can use as tools. MCP publication is configured separately.",
                    list=True,
                    value=[],
                ),
            ),
        ),
    )
)

__all__ = ["AGENT_HARNESS", "DEFAULT_PROJECT_TYPE", "FLOWS", "TOOL_PACK"]
