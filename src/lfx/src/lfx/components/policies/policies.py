from typing import Any, Optional, Union, cast, List, override
from cohere import ToolCall
from lfx.io import MessageTextInput
from langflow.inputs import MultilineInput, BoolInput
from lfx.log.logger import logger
from os.path import join
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output, HandleInput
from lfx.field_typing import Tool
from toolguard import IToolInvoker, ToolGuardSpec, ToolFunctionsInvoker, ToolGuardsCodeGenerationResult, ToolMethodsInvoker, load_toolguard_code_result, load_toolguards
from toolguard import LitellmModel
from toolguard.buildtime import generate_guard_specs, generate_guards_from_specs
from toolguard.data_types import MeleaSessionData
from toolguard.runtime import LangchainToolInvoker


MODEL = "gpt-4o-2024-08-06"
STEP1 = "Step_1"
STEP2 = "Step_2"

class PoliciesComponent(Component):
    display_name = "Policies"
    description = "Policy tool guards"
    documentation: str = "..."  # once we have a URL or alike
    icon = "clipboard-check"  # consider also file-text
    name = "policies"
    beta = True

    inputs = [
        MultilineInput(
            name="policies",
            display_name="Business Policies",
            info="Company business policies: concise, well-defined, self-contained policies, one in a line.",
            value="<example: division by zero is prohibited>",
            # advanced=True,
        ),
        MessageTextInput(
            name="guard_code_path",
            display_name="ToolGuards Generated Code Path",
            info="Automatically generated ToolGuards code",
            # show_if={"enable_tool_guard": True},  # conditional visibility  # check how to do that
            advanced=True,
        ),
        BoolInput(
            name="enabled"
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

    async def build_guards(self) -> List[Tool]:
        assert self.policies, "🔒️ToolGuard: Policies cannot be empty!"

        # logger.info(f"🔒️ToolGuard: Building guards for {self.policies}")
        # logger.info(f"🔒️ToolGuard: Using the following tools {self.tools}")

        if self.enabled:
            # specs = await self._build_guard_specs()
            # guards = await self._build_guards(specs)
            guards = None
            guarded_tools = [WrappedTool(tool, self.tools, self.guard_code_path) for tool in self.tools]
            return guarded_tools # type: ignore
        
        return self.tools
    
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import CallbackManagerForToolRun
class WrappedTool(Tool):
    def __init__(self, tool: Tool, all_tools: List[Tool], tg_dir:str):
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
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Any:
        with load_toolguards(self._tg_dir) as toolguard:
            from rt_toolguard.data_types import PolicyViolationException
            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return self._wrapped._run(args = args, config=config, run_manager=run_manager, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"

    async def _arun(
        self,
        args: Any,
        config: RunnableConfig,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Any:
        print(f"args={args}")
        with load_toolguards(self._tg_dir) as toolguard:
            from rt_toolguard.data_types import PolicyViolationException
            try:
                toolguard.check_toolcall(self.name, *args, delegate=self._tool_invoker)
                return await self._wrapped._arun(*args, config=config, run_manager=run_manager, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"