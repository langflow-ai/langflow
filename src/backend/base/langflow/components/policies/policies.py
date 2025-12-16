from typing import cast, List
from lfx.io import MessageTextInput
from langflow.inputs import MultilineInput, DropdownInput
from lfx.inputs.inputs import BoolInput, ModelInput
from lfx.base.models.model import LCModelComponent
from lfx.log.logger import logger
from os.path import join
from typing import Any

from lfx.base.models import LCModelComponent
from lfx.custom.custom_component.component import Component

from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.field_typing import LanguageModel

from lfx.field_typing import Tool
from lfx.inputs.inputs import BoolInput, MessageTextInput
from lfx.io import HandleInput, MessageTextInput, Output, SecretStrInput
from toolguard import LitellmModel, ToolGuardsCodeGenerationResult, ToolGuardSpec, load_toolguards
from toolguard.buildtime import generate_guard_specs, generate_guards_from_specs
from lfx.field_typing.range_spec import RangeSpec

from toolguard.data_types import MelleaSessionData
from toolguard.runtime import LangchainToolInvoker

from lfx.io import ModelInput

from langflow.inputs import DropdownInput, MultilineInput

MODEL_PROVIDERS_LIST = ["Anthropic", "OpenAI"]
MODEL = "gpt-4o-2024-08-06"
STEP1 = "Step_1"
STEP2 = "Step_2"


class PoliciesComponent(LCModelComponent):
    display_name = "Policies"
    description = "Component for building tool protection code from textual business policies and instructions."
    documentation: str = "https://github.com/IBM/toolguard"
    icon = "clipboard-check"  # consider also file-text
    name = "policies"
    beta = True

    inputs = [
        BoolInput(
            name="bypass_policies",
            display_name="Bypass",
            info="If false, invokes ToolGuard code prior to tool execution, ensuring that tool-related policies are enforced.",
            value=False,
        ),
        TabInput(
            name="build_mode",
            display_name="Policies Build Mode",
            options=["Build", "Use Cache"],
            info="Indicates whether to invoke buildtime (build), or use a cached code (use cache)",
            value="Build",
            real_time_refresh=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="policies",
            display_name="Policies",
            info="Enter one or more clear, well-defined and self-contained business policies, by clicking the '+' button.",
            is_list=True,
            tool_mode=True,
            placeholder="Add business policy...",
            list_add_label="Add Policy",
            input_types=[],
        ),
        MessageTextInput(
            name="guard_code_path",
            display_name="ToolGuards Generated Code Path",
            info="Automatically generated ToolGuards code",
            # show_if={"enable_tool_guard": True},
            value='',  # todo: decide on the path
            advanced=True,
        ),
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            required=False,
            show=True,
            real_time_refresh=True,
            advanced=True,
        ),
        BoolInput(
            name="stream",
            display_name="Stream",
            info="Whether to stream the response",
            value=False,
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Controls randomness in responses",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
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

    def build_model(self) -> LanguageModel:
        return get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=self.api_key,
            temperature=self.temperature,
            stream=self.stream,
        )

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        return update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )

    async def _build_guard_specs(self) -> list[ToolGuardSpec]:
        model = "gpt-4o-2024-08-06"  # FIXME
        llm_provider = "azure"  # FIXME
        llm = LitellmModel(model, llm_provider)

        toolguard_step1_dir = join(self.guard_code_path, STEP1)
        specs = await generate_guard_specs(
            policy_text=self.policies, tools=self.tools, llm=llm, work_dir=toolguard_step1_dir
        )
        return specs

    async def _build_guards(self, specs: list[ToolGuardSpec]) -> ToolGuardsCodeGenerationResult:
        out_dir = join(self.guard_code_path, STEP2)
        gen_result = await generate_guards_from_specs(
            tools=self.tools,
            tool_specs=specs,
            work_dir=out_dir,
            llm_data=MelleaSessionData(),  # FIXME
        )
        return gen_result

    def wrap_tools(self, tools:List[Tool], guard_gen_result: ToolGuardsCodeGenerationResult) -> List[Tool]:
        if self.enabled:
            return tools #FIXME
        return tools
    
    async def build_guards(self) -> List[Tool]:
        assert self.policies, "🔒️ToolGuard: policies cannot be empty!"

        self.log("🔒️ToolGuard: starting building toolguards...", name="info")
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
