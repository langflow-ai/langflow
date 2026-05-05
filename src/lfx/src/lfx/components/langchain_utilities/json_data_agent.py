"""Modern JSON agent built on `langchain.agents.create_agent`.

Replaces the legacy `JsonAgentComponent` (`json_agent.py`) which depended on
`langchain_classic.AgentExecutor` and `langchain_community.create_json_agent`.

Preserves the original S3/local file-loading behavior and the `JSON_PREFIX`
prompt; only the agent factory changes.
"""

import contextlib
import tempfile
from pathlib import Path

import yaml
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware
from langchain_core.runnables import Runnable

from lfx.base.agents.agent import LCAgentComponent
from lfx.base.data.storage_utils import read_file_bytes
from lfx.inputs.inputs import FileInput, HandleInput
from lfx.services.deps import get_settings_service
from lfx.utils.async_helpers import run_until_complete


class JSONDataAgentComponent(LCAgentComponent):
    # display_name matches the legacy JsonAgentComponent so users see the same
    # label in the sidebar and in flows after the swap. Internal `name` is
    # different to avoid a collision in the components dict.
    display_name = "JsonAgent"
    description = "Construct a JSON agent from an LLM and a JSON/YAML document (LangGraph create_agent)."
    name = "JSONDataAgent"
    icon = "LangChain"
    documentation: str = "https://python.langchain.com/docs/integrations/toolkits/json/"

    inputs = [
        *LCAgentComponent.get_base_inputs(),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
        ),
        FileInput(
            name="path",
            display_name="File Path",
            file_types=["json", "yaml", "yml"],
            required=True,
        ),
    ]

    def _get_local_path(self) -> Path:
        """Resolve the source file to a local path, downloading from S3 when needed."""
        file_path = self.path
        settings = get_settings_service().settings

        if settings.storage_type == "s3":
            file_bytes = run_until_complete(read_file_bytes(file_path))

            suffix = Path(file_path.split("/")[-1]).suffix or ".json"
            with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                temp_path = tmp_file.name

            self._temp_file_path = temp_path
            return Path(temp_path)

        return Path(file_path)

    def _cleanup_temp_file(self) -> None:
        """Delete any temporary file allocated by `_get_local_path`."""
        if hasattr(self, "_temp_file_path"):
            with contextlib.suppress(Exception):
                Path(self._temp_file_path).unlink()

    def build_agent(self) -> Runnable:
        try:
            from langchain_community.agent_toolkits.json.prompt import JSON_PREFIX
            from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
            from langchain_community.tools.json.tool import JsonSpec
        except ImportError as e:
            msg = "langchain-community is not installed. Please install it with `pip install langchain-community`."
            raise ImportError(msg) from e

        try:
            path = self._get_local_path()

            if path.suffix in {".yaml", ".yml"}:
                with path.open(encoding="utf-8") as file:
                    yaml_dict = yaml.safe_load(file)
                spec = JsonSpec(dict_=yaml_dict)
            else:
                # JsonSpec.from_file expects a Path (calls .exists() on it).
                spec = JsonSpec.from_file(path)
            toolkit = JsonToolkit(spec=spec)
            tools = list(toolkit.get_tools())

            middleware = []
            max_iterations = getattr(self, "max_iterations", None)
            if max_iterations:
                middleware.append(ModelCallLimitMiddleware(run_limit=int(max_iterations)))
            if getattr(self, "handle_parsing_errors", False):
                middleware.append(ToolRetryMiddleware(max_retries=2))

            agent = create_agent(
                model=self.llm,
                tools=tools,
                system_prompt=JSON_PREFIX,
                middleware=middleware or None,
            )
        except Exception:
            self._cleanup_temp_file()
            raise
        else:
            self._cleanup_temp_file()
            return agent
