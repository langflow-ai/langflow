import shutil
from pathlib import Path
from typing import TYPE_CHECKING, cast

from toolguard.buildtime import (
    ToolGuardsCodeGenerationResult,
    ToolGuardSpec,
    generate_guard_specs,
    generate_guards_code,
)
from toolguard.runtime import load_toolguards

from lfx.base.models import LCModelComponent
from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.components.policies.guarded_tool import GuardedTool
from lfx.components.policies.llm_wrapper import LangchainModelWrapper
from lfx.components.policies.models import BUILDTIME_MODELS
from lfx.components.policies.module_utils import unload_module
from lfx.field_typing import LanguageModel, Tool
from lfx.io import BoolInput, HandleInput, ModelInput, Output, SecretStrInput, StrInput, TabInput
from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.inputs.inputs import InputTypes


TOOLGUARD_WORK_DIR = Path("tmp_toolguard")
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

    inputs = cast(
        "list[InputTypes]",
        [
            BoolInput(
                name="active",
                display_name="Active",
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
                name="project",
                display_name="ToolGuard Project",
                info="Automatically generated ToolGuards code",
                value="my_project",
            ),
            HandleInput(
                name="in_tools",
                display_name="Tools",
                input_types=["Tool"],
                is_list=True,
                required=False,
                info="These are the tools that the agent can use to help with tasks.",
            ),
            StrInput(
                name="policies",
                display_name="Policies",
                info="One or more clear, well-defined and self-contained business policies",
                is_list=True,
                tool_mode=True,
                placeholder="Add business policy...",
                list_add_label="Add Policy",
                input_types=[],
            ),
            ModelInput(
                name="model",
                display_name="Language Model",
                info="Select your model provider",
                options=BUILDTIME_MODELS,
                required=True,
            ),
            SecretStrInput(
                name="api_key",
                display_name="API Key",
                info="Model Provider API key",
                required=False,
                advanced=True,
            ),
        ],
    )
    outputs = [
        Output(
            display_name="Guarded Tools",
            type_=Tool,
            name="guard_code",
            method="build_guards",
            group_outputs=True,
        ),
    ]

    @property
    def work_dir(self) -> Path:
        return TOOLGUARD_WORK_DIR / str(self.user_id) / _to_snake_case(self.project)

    def build_model(self) -> LanguageModel:
        llm_model = get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=self.api_key,
            stream=False,
        )
        if llm_model is None:
            msg = "No language model selected. Please choose a model to proceed."
            raise ValueError(msg)
        return llm_model

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

    async def _generate_guard_specs(self) -> list[ToolGuardSpec]:
        logger.info("🔒️ToolGuard: Starting step 1")
        logger.info(f"model = {self.model}")
        llm = LangchainModelWrapper(self.build_model())
        out_dir = self.work_dir / STEP1
        if out_dir.exists():
            shutil.rmtree(out_dir)
        policy_text = "\n".join(self.policies)
        specs = await generate_guard_specs(
            policy_text=policy_text, tools=self.in_tools, llm=llm, work_dir=out_dir, short=True
        )
        logger.info("🔒️ToolGuard: Step 1 Done")
        return specs

    async def _generate_guard_code(self, specs: list[ToolGuardSpec]) -> ToolGuardsCodeGenerationResult:
        logger.info("🔒️ToolGuard: Starting step 2")
        out_dir = self.work_dir / STEP2
        if out_dir.exists():
            shutil.rmtree(out_dir)
        llm = LangchainModelWrapper(self.build_model())
        app_name = _to_snake_case(self.project)
        gen_result = await generate_guards_code(
            tools=self.in_tools, tool_specs=specs, work_dir=out_dir, llm=llm, app_name=app_name
        )
        logger.info("🔒️ToolGuard: Step 2 Done")
        return gen_result

    async def generate(self):
        # Validate required inputs
        validations = [
            (not self.project, "project cannot be empty!"),
            (not any(self.policies), "policies cannot be empty!"),
            (not self.in_tools, "in_tools cannot be empty!"),
            (not self.model or not self.api_key, "model or api_key cannot be empty!"),
        ]

        for condition, error_msg in validations:
            if condition:
                msg = f"🔒️ToolGuard: {error_msg}"
                raise ValueError(msg)

        self.log(
            f"🔒️ToolGuard: Start generating. Please review the generated guard code at {self.work_dir}", name="info"
        )

        specs = await self._generate_guard_specs()
        res = await self._generate_guard_code(specs)

        # if there was a previous version of the guard, remove it from python cache
        unload_module(res.domain.app_name)

    def _verify_cached_guards(self, code_dir: Path) -> None:
        # Validate cache exists before attempting to load
        if not code_dir.exists():
            msg = (
                f"🔒️ToolGuard: Cache directory not found at '{code_dir}'. "
                f"Please run in 'Generate' mode first to create the guard code, "
                f"or verify the project name is correct."
            )
            raise ValueError(msg)

        try:
            load_toolguards(code_dir)
        except FileNotFoundError as exc:
            msg = (
                f"🔒️ToolGuard: Required guard code files missing in '{code_dir}'. "
                f"Please run in 'Generate' mode to create the guard code."
            )
            raise ValueError(msg) from exc
        except Exception as exc:
            msg = (
                f"🔒️ToolGuard: Failed to load guard code from '{code_dir}'. "
                f"The cached code may be invalid or corrupted. "
                f"Try running in 'Generate' mode to rebuild the guard code. "
                f"Error: {exc!s}"
            )
            raise ValueError(msg) from exc

    async def build_guards(self) -> list[Tool]:
        self.log("🔒️ToolGuard: starting building toolguards...", name="info")
        # self.log(f"🔒️ToolGuard: policies document: {self.policies}", name="info")
        # self.log(f"🔒️ToolGuard: input tools: {self.in_tools}", name="info")
        if self.active:
            build_mode = getattr(self, "build_mode", BUILD_MODE_GENERATE)
            if build_mode == BUILD_MODE_GENERATE:
                await self.generate()
            else:  # build_mode == "use cache"
                self.log("🔒️ToolGuard: run mode (cached code from path)", name="info")

            code_dir = self.work_dir / STEP2
            self._verify_cached_guards(code_dir)
            return cast("list[Tool]", [GuardedTool(tool, self.in_tools, code_dir) for tool in self.in_tools])

        return self.in_tools


def _to_snake_case(human_name: str) -> str:
    return (
        human_name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("'", "_")
        .replace(",", "_")  # ASCII apostrophe
        .replace("’", "_")  # noqa: RUF001 Unicode right single quotation mark
    )
