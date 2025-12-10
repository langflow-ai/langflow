from os.path import join
from typing import Any

from langflow.inputs import DropdownInput, MultilineInput
from toolguard import IToolInvoker, LitellmModel, ToolGuardsCodeGenerationResult, ToolGuardSpec, load_toolguards
from toolguard.buildtime import generate_guard_specs, generate_guards_from_specs
from toolguard.data_types import MeleaSessionData
from toolguard.runtime import LangchainToolInvoker

from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.inputs.inputs import BoolInput, MessageTextInput
from lfx.io import HandleInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger

MODEL_PROVIDERS_LIST = ["azure", "Anthropic", "OpenAI"]
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
            name="enabled",  # type: ignore
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
        MessageTextInput(
            name="model",
            display_name="Model",
            info="",
            # show_if={"enable_tool_guard": True},
            advanced=True,
            value="gpt-4o-2024-08-06",
        ),
        DropdownInput(
            name="model_provider",
            display_name="Model Provider",
            info="The provider of the language model that will be used to generate ToolGuards code.",
            options=[*MODEL_PROVIDERS_LIST],
            value=MODEL_PROVIDERS_LIST[0],
            # real_time_refresh=True,
            # refresh_button=False,
            required=True,
            input_types=[],
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            placeholder="model provider API key",
            # required=True,
            # real_time_refresh=True,
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

    async def _build_guard_specs(self) -> list[ToolGuardSpec]:
        llm = LitellmModel(self.model, self.llm_provider)

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
            llm_data=MeleaSessionData(),  # FIXME
        )
        return gen_result

    async def build_guards(self) -> list[Tool]:
        assert self.policies, "🔒️ToolGuard: policies cannot be empty!"

        self.log("🔒️ToolGuard: starting building toolguards...", name="info")
        self.log(f"🔒️ToolGuard: policies document: {self.policies}", name="info")
        self.log(f"🔒️ToolGuard: model provider: {self.model_provider}, using model: <model name>", name="info")
        self.log(f"🔒️ToolGuard: input tools: {self.tools}", name="info")

        self.log("🔒️ToolGuard: please review the generated guard code at ...", name="info")

        if self.enabled:
            # specs = await self._build_guard_specs()
            # guards = await self._build_guards(specs)
            self.guard_code_path = "/Users/davidboaz/Documents/GitHub/ToolGuardAgent/output/step2_claude4sonnet"
            guarded_tools = [WrappedTool(tool, self.tools, self.guard_code_path) for tool in self.tools]
            print(f"tool0={type(guarded_tools[0])}")
            return guarded_tools  # type: ignore

        return self.tools


from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.runnables import RunnableConfig


class WrappedTool(Tool):
    _wrapped: Tool
    _tool_invoker: IToolInvoker
    _tg_dir: str

    def __init__(self, tool: Tool, all_tools: list[Tool], tg_dir: str):
        super().__init__(
            name=tool.name,
            description=tool.description,
            args_schema=getattr(tool, "args_schema", None),
            return_direct=getattr(tool, "return_direct", False),
            func=self._run,
            coroutine=self._arun,
            tags=tool.tags,
            metadata=tool.metadata,
            verbose=True,
        )
        self._wrapped = tool
        self._tool_invoker = LangchainToolInvoker(all_tools)
        self._tg_dir = tg_dir

    @property
    def args(self) -> dict:
        return self._wrapped.args

    def _call_wrapped_sync(self, args, config, run_manager, **kwargs):
        if getattr(self._wrapped, "args_schema", None):
            return self._wrapped._run(
                **args,
                config=config,
                run_manager=run_manager,
                **kwargs,
            )
        return self._wrapped._run(
            args,
            config=config,
            run_manager=run_manager,
            **kwargs,
        )

    async def _call_wrapped_async(self, args, config, run_manager, **kwargs):
        if getattr(self._wrapped, "args_schema", None):
            return await self._wrapped._arun(
                **args,
                config=config,
                run_manager=run_manager,
                **kwargs,
            )
        return await self._wrapped._arun(
            args,
            config=config,
            run_manager=run_manager,
            **kwargs,
        )

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
                return self._call_wrapped_sync(args, config=config, run_manager=run_manager, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"

    async def _arun(
        self,
        args: Any,
        config: RunnableConfig,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        print(f"tool={self.name}, args={args}, config={config}, kwargs={kwargs}")
        with load_toolguards(self._tg_dir) as toolguard:
            from rt_toolguard.data_types import PolicyViolationException  # type: ignore

            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return await self._call_wrapped_async(args, config=config, run_manager=run_manager, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"
            except Exception as ex:
                logger.exception("Unhandled exception in WrappedTool._arun", exc_info=ex)
