from typing import cast, List
from lfx.io import MessageTextInput
from langflow.inputs import MultilineInput, DropdownInput
from lfx.inputs.inputs import BoolInput, ModelInput
from lfx.base.models.model import LCModelComponent
from lfx.log.logger import logger
from os.path import join
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output, HandleInput, SecretStrInput
from lfx.field_typing import Tool
from toolguard import IToolInvoker, ToolGuardSpec, ToolFunctionsInvoker, ToolGuardsCodeGenerationResult, \
    ToolMethodsInvoker, load_toolguard_code_result, load_toolguards
from toolguard import LitellmModel
from toolguard.buildtime import generate_guard_specs, generate_guards_from_specs
from toolguard.data_types import MeleaSessionData
from toolguard.runtime import LangchainToolInvoker


MODEL_PROVIDERS_LIST = ["Anthropic", "OpenAI"]
MODEL = "gpt-4o-2024-08-06"
STEP1 = "Step_1"
STEP2 = "Step_2"


class PoliciesComponent(Component):
    display_name = "Policies"
    description = "Component for building tool protection code from textual business policies and instructions."
    documentation: str = "https://github.com/IBM/toolguard"
    icon = "clipboard-check"  # consider also file-text
    name = "policies"
    beta = True

    inputs = [
        BoolInput(
            name="enabled",
            display_name="Enable ToolGuard Execution",
            info="If true, invokes ToolGuard code prior to tool execution, ensuring that tool-related policies are enforced.",
            value=True,
        ),
        MultilineInput(
            name="policies",
            display_name="Business Policies",
            info="Company business policies: concise, well-defined, self-contained policies, one in a line.",
            value="<example: division by zero is prohibited>",
        ),
        MessageTextInput(
            name="guard_code_path",
            display_name="ToolGuards Generated Code Path",
            info="Automatically generated ToolGuards code",
            # show_if={"enable_tool_guard": True},
            advanced=True,
        ),
        DropdownInput(
            name="model_provider",
            display_name="Model Provider",
            info="The provider of the language model that will be used to generate ToolGuards code.",
            options=[*MODEL_PROVIDERS_LIST],
            value=MODEL_PROVIDERS_LIST[0],
            #real_time_refresh=True,
            #refresh_button=False,
            required=True,
            input_types=[],
            ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            placeholder="model provider API key",
            required=True,
            #real_time_refresh=True,
            advanced=False,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=False,
            info="These are the tools that the agent can use to help with tasks.",
        ),
    ]
    outputs = [
        Output(display_name="Guarded Tools", type_=Tool, name="guard_code", method="build_guards"),
    ]

    async def _build_guard_specs(self) ->List[ToolGuardSpec]:
        model = "gpt-4o-2024-08-06" #FIXME
        llm_provider = "azure" #FIXME
        llm = LitellmModel(model, llm_provider)

        toolguard_step1_dir = join(self.guard_code_path, STEP1)
        specs = await generate_guard_specs(
            policy_text = self.policies,
            tools= self.tools,
            llm= llm,
            work_dir = toolguard_step1_dir
        )
        return specs

    async def _build_guards(self, specs: List[ToolGuardSpec])->ToolGuardsCodeGenerationResult:
        out_dir = join(self.guard_code_path, STEP2)
        gen_result = await generate_guards_from_specs(
            tools=self.tools,
            tool_specs = specs,
            work_dir=out_dir,
            llm_data=MeleaSessionData(), #FIXME
        )
        return gen_result

    def wrap_tools(self, tools:List[Tool], guard_gen_result: ToolGuardsCodeGenerationResult) -> List[Tool]:
        if self.enabled:
            return tools #FIXME
        return tools
    
    async def build_guards(self) -> List[Tool]:
        assert self.policies, "🔒️ToolGuard: policies cannot be empty!"

        self.log(f"🔒️ToolGuard: starting building toolguards...", name="info")
        self.log(f"🔒️ToolGuard: policies document: {self.policies}", name="info")
        self.log(f"🔒️ToolGuard: input tools: {self.tools}", name="info")

        self.log(f"🔒️ToolGuard: model provider: {self.model_provider}, using model: <model name>", name="info")

        # if self.enabled:
        #     specs = await self._build_guard_specs()
        #     guards = await self._build_guards(specs)
        #
        #     guarded_tools = self.wrap_tools(self.tools, guards)
        #     return guarded_tools

        self.log(f"🔒️ToolGuard: please review the generated guard code at ...", name="info")

        return self.tools
