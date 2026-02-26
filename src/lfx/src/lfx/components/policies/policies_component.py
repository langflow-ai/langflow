import traceback
from typing import Any, Optional, Union, cast, List, override
from cohere import ToolCall
from lfx.io import MessageTextInput
from langflow.inputs import MultilineInput, DropdownInput
from lfx.inputs.inputs import BoolInput, ModelInput
from lfx.base.models.model import LCModelComponent
from lfx.log.logger import logger
from os.path import join

from toolguard.buildtime import (
    ToolGuardsCodeGenerationResult,
    ToolGuardSpec,
    generate_guard_specs,
    generate_guards_code,
)
from toolguard.extra.langchain_to_oas import langchain_tools_to_openapi
from toolguard.runtime import load_toolguards, load_toolguards_from_memory
from toolguard.runtime.runtime import RESULTS_FILENAME

from lfx.base.models import LCModelComponent
from lfx.components.policies.wrapped_tool import LangchainModelWrapper, WrappedTool

from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.field_typing import LanguageModel

from lfx.field_typing import Tool
from lfx.inputs.inputs import BoolInput, MessageTextInput
from lfx.io import HandleInput, MessageTextInput, Output, SecretStrInput

if TYPE_CHECKING:
    from lfx.inputs.inputs import InputTypes


BUILDTIME_MODELS = ["gpt-5.1", "claude-sonnet-4"]
TOOLGUARD_WORK_DIR = Path("tmp_toolguard")
STEP1 = "Step_1"
STEP2 = "Step_2"
BUILD_MODE_GENERATE = "Generate"
BUILD_MODE_CACHE = "Use Cache"
GENERATED_GUARD_INFO_PREFIX = "Auto-generated ToolGuard code for "


class PoliciesComponent(LCModelComponent):
    """Component for building tool protection code from textual business policies and instructions.

    This component uses ToolGuard to generate and apply policy-based guards to tools,
    ensuring that tool execution complies with defined business policies.
    Powered by ALTK ToolGuard (https://github.com/AgentToolkit/toolguard).
    """

    display_name = "Policies"
    description = """Component for building tool protection code from textual business policies and instructions.
Powered by [ALTK ToolGuard](https://github.com/AgentToolkit/toolguard )"""
    documentation: str = "https://github.com/AgentToolkit/toolguard"
    icon = "clipboard-check"  # consider also file-text
    name = "policies"
    beta = True

    inputs = [
        BoolInput(
            name="activate_policies",
            display_name="Activate",
            info="If `true` - invokes ToolGuard code prior to tool execution. If `false`, skip policy validation.",
            value=True,
        ),
        TabInput(
            name="build_mode",
            display_name="Policies Build Mode",
            options=[BUILD_MODE_GENERATE, BUILD_MODE_CACHE],
            info="Indicates whether to invoke buildtime (Generate), or use a cached code (Use Cache)",
            value=BUILD_MODE_GENERATE,
            real_time_refresh=True,
            tool_mode=True,
        ),
        StrInput(
            name="policies",
            display_name="Policies",
            info="Enter one or more clear, well-defined and self-contained business policies, Using the '+' button.",
            is_list=True,
            tool_mode=True,
            placeholder="Add business policy...",
            list_add_label="Add Policy",
            input_types=[],
        ),
        StrInput(
            name="project",
            display_name="ToolGuard Project",
            info="Automatically generated ToolGuards code",
            # show_if={"enable_tool_guard": True},
            value="my_project",
            # advanced=True,
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
            options=[
                {
                    "name": "gpt-4o",
                    "icon": "OpenAI",
                    "category": "OpenAI",
                    "provider": "OpenAI",
                    "metadata": {
                        "context_length": 128000,
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                        "reasoning_models": ["gpt-4o"]
                    }
                },
                {
                    "name": "claude-sonnet-4",
                    "icon": "Anthropic",
                    "category": "Anthropic",
                    "provider": "Anthropic",
                    "metadata": {
                        "context_length": 128000,
                        "model_class": "ChatAnthropic",
                        "model_name_param": "model",
                        "api_key_param": "api_key"
                    }
                }
            ]
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
            name="in_tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=False,
            info="These are the tools that the agent can use to help with tasks.",
        ),
    ]
    outputs = [
        Output(
            display_name="Guarded Tools",
            type_=Tool,
            name="guarded_tools",
            method="guard_tools",
            # group_outputs=True,
        ),
    ]

    async def _build_guard_specs(self) ->List[ToolGuardSpec]:
        model = "gpt-4o-2024-08-06" #FIXME
        llm_provider = "azure" #FIXME
        llm = LitellmModel(model, llm_provider)

        toolguard_step1_dir = join(self.guard_code_path, STEP1)
        policy_text = "\n".join(self.policies)
        open_api = langchain_tools_to_openapi(self.in_tools)
        specs = await generate_guard_specs(policy_text=policy_text, tools=open_api, llm=llm, work_dir=out_dir)
        logger.info("Step 1 Done")
        return specs

    async def _generate_guard_code(self, specs: list[ToolGuardSpec]) -> ToolGuardsCodeGenerationResult:
        logger.info("Starting step 2")
        out_dir = self.work_dir / STEP2
        if out_dir.exists():
            shutil.rmtree(out_dir)
        llm = LangchainModelWrapper(self.build_model())
        app_name = self._to_snake_case(self.project)
        open_api = langchain_tools_to_openapi(self.in_tools)

        gen_result = await generate_guards_code(
            tools=open_api, tool_specs=specs, work_dir=out_dir, llm=llm, app_name=app_name
        )
        logger.info("Step 2 Done")
        return gen_result

    def in_recommended_models(self, model_name: str):
        return any(recommended in model_name for recommended in BUILDTIME_MODELS)

    def validate_before_generate(self) -> None:
        """Validate required inputs before generating guard code."""
        if not self.project:
            msg = "Policies: project cannot be empty!"
            raise ValueError(msg)

        if not any(self.policies):
            msg = "Policies: policies cannot be empty!"
            raise ValueError(msg)

        if not self.in_tools:
            msg = "Policies: in_tools cannot be empty!"
            raise ValueError(msg)

        if not self.model or not self.api_key:
            msg = "Policies: model or api_key cannot be empty!"
            raise ValueError(msg)

        if not self.in_recommended_models(self.model[0]["name"]):
            msg = f"Policies: model {self.model[0]['name']} is not in recommended models: {BUILDTIME_MODELS}"
            raise ValueError(msg)

    async def generate(self):
        self.log(f"Start generating. Please review the generated guard code at {self.work_dir}", name="info")

        specs = await self._generate_guard_specs()
        res = await self._generate_guard_code(specs)

        # if there was a previous version of the guard, remove it from python cache
        unload_module(res.domain.app_name)

    def _verify_cached_guards(self, code_dir: Path) -> None:
        # Validate cache exists before attempting to load
        if not code_dir.exists():
            msg = (
                f"Policies: Cache directory not found at '{code_dir}'. "
                f"Please run in 'Generate' mode first to create the guard code, "
                f"or verify the project name is correct."
            )
            raise ValueError(msg)

        if self.enabled:
            # specs = await self._build_guard_specs()
            # guards = await self._build_guards(specs)
            self.guard_code_path = "/Users/davidboaz/Documents/GitHub/ToolGuardAgent/output/step2_claude4sonnet"
            guarded_tools = [WrappedTool(tool, self.tools, self.guard_code_path) for tool in self.tools]
            print(f"tool0={guarded_tools[0]}")
            return guarded_tools # type: ignore
        
        return self.tools
    
from langchain_core.runnables import RunnableConfig
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
            from rt_toolguard.data_types import PolicyViolationException
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
            from rt_toolguard.data_types import PolicyViolationException
            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return await self._call_wrapped_async(args, config=config, run_manager=run_manager, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"
            except Exception as ex:
                logger.exception("Unhandled exception in WrappedTool._arun", exc_info=ex)