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
from lfx.io import HandleInput, MessageTextInput, Output, SecretStrInput, TabInput, SliderInput
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
    description = "Component for building tool protection code from textual business policies and instructions. " \
                  "Powered by [ToolGuard](https://github.com/IBM/toolguard)."
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
            options=["Generate", "Use Cache"],
            info="Indicates whether to invoke buildtime (build), or use a cached code (use cache)",
            value="Generate",
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

    async def build_guards(self) -> list[Tool]:
        assert self.policies, "🔒️ToolGuard: policies cannot be empty!"

        self.log("🔒️ToolGuard: starting building toolguards...", name="info")
        self.log(f"🔒️ToolGuard: policies document: {self.policies}", name="info")
        self.log(f"🔒️ToolGuard: input tools: {self.tools}", name="info")

        self.log("🔒️ToolGuard: please review the generated guard code at ...", name="info")

        if not self.bypass_policies:
            build_mode = getattr(self, "build_mode", "Generate")
            if build_mode == "Generate":  # run buildtime steps
                self.log("🔒️ToolGuard: execution (build) mode", name="info")
                # specs  = await self._build_guard_specs()
                # guards = await self._build_guards(specs)
            else:  # build_mode == "use cache"
                self.log("🔒️ToolGuard: run mode (cached code from path)", name="info")
                # make sure self.guard_code_path contains the path to pre-built guards
                # assert self.guard_code_path, "🔒️ToolGuard: guard path should be a valid code path!"

            guards = None
            guarded_tools = [WrappedTool(tool, self.tools, self.guard_code_path) for tool in self.tools]
            return guarded_tools  # type: ignore

        return self.tools


from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.runnables import RunnableConfig


class WrappedTool(Tool):
    def __init__(self, tool: Tool, all_tools: list[Tool], tg_dir: str):
        super().__init__(name=tool.name, func=tool.func, description=tool.description)
        self._wrapped = tool
        self._tool_invoker = LangchainToolInvoker(all_tools)
        self._tg_dir = tg_dir

    @property
    def args(self) -> dict:
        return self._wrapped.args

    def _run(
        self,
        args: Any,
        config: RunnableConfig,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        with load_toolguards(self._tg_dir) as toolguard:
            from rt_toolguard.data_types import PolicyViolationException  # type: ignore

            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return self._wrapped._run(args=args, config=config, run_manager=run_manager, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"

    async def _arun(
        self,
        args: Any,
        config: RunnableConfig,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        print(f"args={args}")
        with load_toolguards(self._tg_dir) as toolguard:
            from rt_toolguard.data_types import PolicyViolationException  # type: ignore

            try:
                toolguard.check_toolcall(self.name, *args, delegate=self._tool_invoker)
                return await self._wrapped._arun(*args, config=config, run_manager=run_manager, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"
