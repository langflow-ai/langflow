from os.path import join


from lfx.base.models import LCModelComponent
from lfx.components.policies.guarded_tool import GuardedTool
from lfx.components.policies.llm_wrapper import LangchainModelWrapper
from lfx.components.policies.models import BUILDTIME_MODELS

from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.field_typing import LanguageModel

from lfx.field_typing import Tool
from lfx.inputs.inputs import BoolInput, MessageTextInput
from lfx.io import HandleInput, MessageTextInput, Output, SecretStrInput, TabInput
from toolguard import ToolGuardsCodeGenerationResult, ToolGuardSpec
from toolguard.buildtime import generate_guard_specs, generate_guards_from_specs

from lfx.io import ModelInput
from lfx.log.logger import logger

from langflow.inputs import DropdownInput, MultilineInput
from lfx.schema.table import EditMode

STEP1 = "Step_1"
STEP2 = "Step_2"
BUILD_MODE_GENERATE = "Generate"
BUILD_MODE_CACHE = "Use Cache"


class PoliciesComponent(LCModelComponent):
    display_name = "Policies"
    description = """Component for building tool protection code from textual business policies and instructions.
Powered by [ToolGuard](https://github.com/AgentToolkit/toolguard )"""
    documentation: str = "https://github.com/AgentToolkit/toolguard"
    icon = "clipboard-check"  # consider also file-text
    name = "policies"
    beta = True

    inputs = [
        BoolInput(
            name="bypass_policies",
            display_name="Bypass",
            info="If `true` - skip policy validation. If `false`, invokes ToolGuard code prior to tool execution, ensuring that tool-related policies are enforced.",
            value=False,
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
        # TableInput(
        #     name="build_mode",
        #     display_name="policies build mode",
        #     info="...",
        #     table_schema=[
        #         {
        #             "name": "mode",
        #             "display_name": "policies build mode",
        #             "type": "str",
        #             "description": "...",
        #         },
        #         {
        #             "name": "active",
        #             "display_name": "active?",
        #             "type": "boolean",
        #             "edit_mode": EditMode.INLINE,
        #             "options": ["False", "True"],
        #             "default": "False",
        #             "description": "...",
        #         },
        #     ],
        #     value=[{"mode": "Generate", "active": "False"}, {"mode": "Use Cache", "active": "False"}],
        #     #advanced=True,
        #     input_types=["DataFrame"],
        # ),
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
            value='tmp',  # todo: decide on the path
            advanced=True,
        ),
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            options=BUILDTIME_MODELS,
            required=True
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
        Output(display_name="Guarded Tools", type_=Tool, name="guard_code", method="build_guards"),
    ]

    def build_model(self) -> LanguageModel:
        return get_llm(
            model=self.model,
            user_id=None,
            api_key=self.api_key,
            # temperature=self.temperature,
            stream=False,
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
        logger.info(f"🔒️ToolGuard: Starting step 1")
        logger.info(f"model = {self.model}")
        llm = LangchainModelWrapper(self.build_model())
        toolguard_step1_dir = join(self.guard_code_path, STEP1)
        policy_text = "\n".join(self.policies)
        specs = await generate_guard_specs(
            policy_text=policy_text,
            tools=self.in_tools,
            llm=llm, 
            work_dir=toolguard_step1_dir,
            short=True
        )
        logger.info(f"🔒️ToolGuard: Step 1 Done")
        return specs
    
    async def _build_guards(self, specs: list[ToolGuardSpec]) -> ToolGuardsCodeGenerationResult:
        logger.info(f"🔒️ToolGuard: Starting step 2")
        out_dir = join(self.guard_code_path, STEP2)
        llm = LangchainModelWrapper(self.build_model())
        gen_result = await generate_guards_from_specs(
            tools=self.in_tools,
            tool_specs=specs,
            work_dir=out_dir,
            llm=llm
        )
        logger.info(f"🔒️ToolGuard: Step 2 Done")
        return gen_result

    async def build_guards(self) -> list[Tool]:
        assert self.policies, "🔒️ToolGuard: policies cannot be empty!"

        self.log("🔒️ToolGuard: starting building toolguards...", name="info")
        self.log(f"🔒️ToolGuard: policies document: {self.policies}", name="info")
        self.log(f"🔒️ToolGuard: input tools: {self.in_tools}", name="info")

        self.log("🔒️ToolGuard: please review the generated guard code at ...", name="info")

        if not self.bypass_policies:
            build_mode = getattr(self, "build_mode", BUILD_MODE_GENERATE)
            if build_mode == BUILD_MODE_GENERATE:  # run buildtime steps
                logger.info("🔒️ToolGuard: execution (build) mode")
                specs  = await self._build_guard_specs()
                guards = await self._build_guards(specs)
                self.guard_code_path = guards.out_dir
            else:  # build_mode == "use cache"
                self.log("🔒️ToolGuard: run mode (cached code from path)", name="info")
                # make sure self.guard_code_path contains the path to pre-built guards
                # assert self.guard_code_path, "🔒️ToolGuard: guard path should be a valid code path!"
            code_dir = join(self.guard_code_path, STEP2)
            guarded_tools = [GuardedTool(tool, self.in_tools, code_dir) for tool in self.in_tools]
            return guarded_tools  # type: ignore

        return self.in_tools
