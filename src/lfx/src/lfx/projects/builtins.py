"""The project types that ship with Langflow.

Every field's default is the default the runtime already uses, so a harness created and left
alone behaves exactly like an Agent component dropped on a blank canvas. That is what makes
the form safe to save with nothing filled in.
"""

from __future__ import annotations

from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE
from lfx.inputs.inputs import DropdownInput, IntInput, ModelInput, MultilineInput, StrInput
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
                # No write-through target on purpose. The Agent's ``tools`` input holds tool
                # objects built from what the graph connects to it, so putting flow ids there
                # would break the run rather than configure it. Turning the picked flows into
                # tool nodes wired to the agent is graph surgery, and it is not this field's
                # job; the picked ids are recorded in project_config until that lands.
                input=StrInput(
                    name="tools",
                    display_name="Tools",
                    info="Flows in this project the agent can call.",
                    list=True,
                    value=[],
                ),
            ),
            ProjectTypeField(
                name="n_messages",
                section="Runtime",
                writes_to=FieldTarget("Agent", "n_messages"),
                input=IntInput(
                    name="n_messages",
                    display_name="Memory",
                    info="How many past messages the agent sees.",
                    value=100,
                ),
            ),
            ProjectTypeField(
                name="compaction",
                section="Runtime",
                # No write-through target: nothing in the runtime consumes this yet.
                # langchain ships SummarizationMiddleware unused, so the only honest option
                # today is off. See the harness notes in the design docs.
                input=DropdownInput(
                    name="compaction",
                    display_name="Compaction",
                    info="Summarise old turns when the conversation grows. Not wired up yet.",
                    options=["off"],
                    value="off",
                ),
            ),
        ),
    )
)

__all__ = ["AGENT_HARNESS", "DEFAULT_PROJECT_TYPE", "FLOWS"]
