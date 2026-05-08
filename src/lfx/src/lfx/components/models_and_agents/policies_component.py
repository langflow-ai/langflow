import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, cast

from toolguard.buildtime import (
    PolicySpecOptions,
    ToolGuardsCodeGenerationResult,
    ToolGuardSpec,
    generate_guard_specs,
    generate_guards_code,
)
from toolguard.extra.langchain_to_oas import langchain_tools_to_openapi
from toolguard.runtime import load_toolguards, load_toolguards_from_memory
from toolguard.runtime.runtime import RESULTS_FILENAME

from lfx.base.models import LCModelComponent
from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.components.models_and_agents.policies.guard_sync_utils import sync_generated_guard_code_inputs
from lfx.components.models_and_agents.policies.guarded_tool import GuardedTool
from lfx.components.models_and_agents.policies.llm_wrapper import LangchainModelWrapper
from lfx.components.models_and_agents.policies.module_utils import unload_module
from lfx.field_typing import LanguageModel, Tool
from lfx.io import (
    BoolInput,
    HandleInput,
    ModelInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
    TabInput,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.inputs.inputs import InputTypes


TOOLGUARD_WORK_DIR = Path(os.getenv("TOOLGUARD_WORK_DIR") or "tmp_toolguard")
BUILDTIME_MODELS = ["gpt-5", "claude-sonnet"]  # currently inactive, we recommend but do not enforce
STEP1 = "Step_1"
STEP2 = "Step_2"
MODE_GENERATE = "🛠️ Generate"
MODE_GUARD = "🛡️ Guard"
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
    icon = "shield-check"
    name = "policies"
    beta = True

    inputs = cast(
        "list[InputTypes]",
        [
            BoolInput(
                name="enabled",
                display_name="Enabled",
                info="If `true` - guards tool calls. If `false`, skip policy validation.",
                value=True,
            ),
            TabInput(
                name="mode",
                display_name="Activity",
                options=[MODE_GENERATE, MODE_GUARD],
                info=(
                    "Generate new guard code or apply existing guard. "
                    "Review generated files in the details panel on the right."
                ),
                value=MODE_GENERATE,
                real_time_refresh=True,
                tool_mode=True,
            ),
            MultilineInput(
                name="project",
                display_name="Policies Project",
                info="Folder name of the generated code",
                value="my_project",
                # required=True,
            ),
            HandleInput(
                name="in_tools",
                display_name="Tools",
                input_types=["Tool"],
                is_list=True,
                required=True,
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
                # input_types=[],
            ),
            ModelInput(
                name="model",
                display_name="Language Model",
                info=(
                    "Select LLM for Policies buildtime. We recommend using "
                    "Anthropic Claude-Sonnet series for this task."
                ),
                real_time_refresh=True,
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
            name="guarded_tools",
            method="guard_tools",
            # group_outputs=True,
        ),
    ]

    @property
    def work_dir(self) -> Path:
        return TOOLGUARD_WORK_DIR / self._to_snake_case(self.project)

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
        updated_build_config = update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )
        py_module = self._to_snake_case(self.project)
        return sync_generated_guard_code_inputs(
            build_config=updated_build_config,
            work_dir=self.work_dir,
            step2_subdir=STEP2,
            project_name=py_module,
        )

    async def _generate_guard_specs(self) -> list[ToolGuardSpec]:
        logger.debug("Starting step 1")
        logger.debug(f"model = {self.model}")
        llm = LangchainModelWrapper(self.build_model())
        out_dir = self.work_dir / STEP1
        if out_dir.exists():
            shutil.rmtree(out_dir)
        policy_text = "\n * ".join(self.policies)
        open_api = langchain_tools_to_openapi(self.in_tools)

        options = PolicySpecOptions(example_number=4)
        specs = await generate_guard_specs(
            policy_text=policy_text, tools=open_api, llm=llm, work_dir=out_dir, options=options
        )
        logger.debug("Step 1 Done")
        return specs

    async def _generate_guard_code(self, specs: list[ToolGuardSpec]) -> ToolGuardsCodeGenerationResult:
        logger.debug("Starting step 2")
        out_dir = self.work_dir / STEP2
        if out_dir.exists():
            shutil.rmtree(out_dir)
        llm = LangchainModelWrapper(self.build_model())
        app_name = self._to_snake_case(self.project)
        open_api = langchain_tools_to_openapi(self.in_tools)

        gen_result = await generate_guards_code(
            tools=open_api, tool_specs=specs, work_dir=out_dir, llm=llm, app_name=app_name
        )
        logger.debug("Step 2 Done")
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

        # uncomment if willing to enforce certain models for buildtime
        # if not self.in_recommended_models(self.model[0]["name"]):
        #     msg = f"Policies: model {self.model[0]['name']} is not in recommended models: {BUILDTIME_MODELS}"
        #     raise ValueError(msg)

    async def generate(self):
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

        try:
            load_toolguards(code_dir)
        except FileNotFoundError as exc:
            msg = (
                f"Policies: Required guard code files missing in '{code_dir}'. "
                f"Please run in 'Generate' mode to create the guard code."
            )
            raise ValueError(msg) from exc
        except Exception as exc:
            msg = (
                f"Policies: Failed to load guard code from '{code_dir}'. "
                f"The cached code may be invalid or corrupted. "
                f"Try running in 'Generate' mode to rebuild the guard code. "
                f"Error: {exc!s}"
            )
            raise ValueError(msg) from exc

    def _validate_before_using_cache(self, code_dir: Path) -> None:
        if not self.in_tools:
            msg = "Policies: in_tools cannot be empty!"
            raise ValueError(msg)

        self._verify_cached_guards(code_dir)

    def make_toolguard_result(self) -> ToolGuardsCodeGenerationResult:
        attrs = self.get_vertex().data["node"]["template"]
        if not attrs:
            raise ValueError

        result_str = attrs[str(RESULTS_FILENAME)]["value"]
        result = ToolGuardsCodeGenerationResult.model_validate_json(result_str)

        result.domain.app_types.content = attrs.get(str(result.domain.app_types.file_name))["value"]
        result.domain.app_api.content = attrs.get(str(result.domain.app_api.file_name))["value"]
        result.domain.app_api_impl.content = attrs.get(str(result.domain.app_api_impl.file_name))["value"]

        for tool in result.tools.values():
            tool.guard_file.content = attrs.get(str(tool.guard_file.file_name))["value"]
            for tool_item in tool.item_guard_files:
                tool_item.content = attrs.get(str(tool_item.file_name))["value"]

        return result

    async def guard_tools(self) -> list[Tool]:
        if self.enabled:
            mode = getattr(self, "mode", MODE_GENERATE)
            if mode == MODE_GENERATE:
                self.log(f"Start generating guard code at {self.work_dir}", name="info")
                self.validate_before_generate()
                await self.generate()
                self.log(f"Policies code generation saved to {self.work_dir}", name="info")
                self.log("Review the generated files in the details panel on the right.", name="info")

            else:  # mode == "guard"
                self.log(f"using cache from {self.work_dir}", name="info")
                code_dir = self.work_dir / STEP2
                self._validate_before_using_cache(code_dir)
                try:
                    tg_result = self.make_toolguard_result()
                    tg_runtime = load_toolguards_from_memory(tg_result)
                    guarded_tools = [GuardedTool(tool, self.in_tools, tg_runtime) for tool in self.in_tools]
                    return cast("list[Tool]", guarded_tools)
                except Exception as e:
                    logger.exception(e)
                    raise

        return self.in_tools

    @staticmethod
    def _to_snake_case(human_name: str) -> str:
        """Convert human-readable name to snake_case, sanitizing path traversal attempts."""
        # Convert to lowercase
        result = human_name.lower()

        # Replace any non-alphanumeric character (including path traversal chars) with underscore
        result = re.sub(r"[^a-z0-9]+", "_", result)

        # Strip leading/trailing underscores
        result = result.strip("_")

        # Ensure the result contains at least one alphanumeric character
        if not result or not re.search(r"[a-z0-9]", result):
            msg = "Project name must contain at least one alphanumeric character"
            raise ValueError(msg)

        return result
