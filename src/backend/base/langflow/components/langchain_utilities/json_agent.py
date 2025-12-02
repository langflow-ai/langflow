import tempfile
from pathlib import Path

import yaml
from langchain.agents import AgentExecutor
from langchain_community.agent_toolkits import create_json_agent
from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
from langchain_community.tools.json.tool import JsonSpec

from langflow.base.agents.agent import LCAgentComponent
from langflow.inputs.inputs import FileInput, HandleInput
from langflow.utils.async_helpers import run_until_complete


class JsonAgentComponent(LCAgentComponent):
    display_name = "JsonAgent"
    description = "Construct a json agent from an LLM and tools."
    name = "JsonAgent"
    legacy: bool = True

    inputs = [
        *LCAgentComponent._base_inputs,
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
        from langflow.services.deps import get_settings_service

        file_path = self.path
        settings = get_settings_service().settings

        # If using S3 storage, download the file to temp
        if settings.storage_type == "s3":
            from langflow.base.data.storage_utils import read_file_bytes

            try:
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
            except Exception:  # noqa: BLE001, S110
                # If S3 download fails, fall back to treating it as a local path
                pass

        # Local storage or fallback - return as Path
        return Path(file_path)

    def _cleanup_temp_file(self) -> None:
        """Clean up temporary file if one was created."""
        if hasattr(self, "_temp_file_path"):
            try:  # noqa: SIM105
                Path(self._temp_file_path).unlink()
            except Exception:  # noqa: BLE001, S110
                pass  # Ignore cleanup errors

    def build_agent(self) -> AgentExecutor:
        """Build the JSON agent executor."""
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

            # Clean up temp file after agent is created
            self._cleanup_temp_file()
        except Exception:
            # Make sure to clean up temp file on error
            self._cleanup_temp_file()
            raise
        else:
            return agent
