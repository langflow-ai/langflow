import contextlib
import tempfile
from pathlib import Path

import yaml
from langchain.agents import AgentExecutor

from lfx.base.agents.agent import LCAgentComponent
from lfx.base.data.storage_utils import read_file_bytes
from lfx.inputs.inputs import FileInput, HandleInput
from lfx.services.deps import get_settings_service
from lfx.utils.async_helpers import run_until_complete


class JsonAgentComponent(LCAgentComponent):
    display_name = "JsonAgent"
    description = "Construct a json agent from an LLM and tools."
    name = "JsonAgent"
    legacy: bool = True

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
        """Get a local file path, downloading from S3 storage if necessary.

        Returns:
            Path: Local file path that can be used by LangChain
        """
        file_path = self.path
        settings = get_settings_service().settings

        # If using S3 storage, download the file to temp
        if settings.storage_type == "s3":
            # Download from S3 to temp file
            file_bytes = run_until_complete(read_file_bytes(file_path))

            # Create temp file with appropriate extension
            suffix = Path(file_path.split("/")[-1]).suffix or ".json"
            with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                temp_path = tmp_file.name

            # Store temp path for cleanup
            self._temp_file_path = temp_path
            return Path(temp_path)

        # Local storage - return as Path
        return Path(file_path)

    def _cleanup_temp_file(self) -> None:
        """Clean up temporary file if one was created."""
        if hasattr(self, "_temp_file_path"):
            with contextlib.suppress(Exception):
                Path(self._temp_file_path).unlink()  # Ignore cleanup errors

    def build_agent(self) -> AgentExecutor:
        """Build the JSON agent executor."""
        try:
            from langchain_community.agent_toolkits import create_json_agent
            from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
            from langchain_community.tools.json.tool import JsonSpec
        except ImportError as e:
            msg = "langchain-community is not installed. Please install it with `pip install langchain-community`."
            raise ImportError(msg) from e

        try:
            # Get local path (downloads from S3 if needed)
            path = self._get_local_path()

            if path.suffix in {".yaml", ".yml"}:
                with path.open(encoding="utf-8") as file:
                    yaml_dict = yaml.safe_load(file)
                spec = JsonSpec(dict_=yaml_dict)
            else:
                spec = JsonSpec.from_file(str(path))
            toolkit = JsonToolkit(spec=spec)

            agent = create_json_agent(llm=self.llm, toolkit=toolkit, **self.get_agent_kwargs())
        except Exception:
            # Make sure to clean up temp file on error
            self._cleanup_temp_file()
            raise
        else:
            # Clean up temp file after agent is created
            self._cleanup_temp_file()
            return agent
