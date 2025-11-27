import contextlib
import tempfile
from pathlib import Path

from lfx.base.agents.agent import LCAgentComponent
from lfx.base.data.storage_utils import read_file_bytes
from lfx.field_typing import AgentExecutor
from lfx.inputs.inputs import (
    DictInput,
    DropdownInput,
    FileInput,
    HandleInput,
    MessageTextInput,
)
from lfx.schema.message import Message
from lfx.services.deps import get_settings_service
from lfx.template.field.base import Output
from lfx.utils.async_helpers import run_until_complete


class CSVAgentComponent(LCAgentComponent):
    display_name = "CSV Agent"
    description = "Construct a CSV agent from a CSV and tools."
    documentation = "https://python.langchain.com/docs/modules/agents/toolkits/csv"
    name = "CSVAgent"
    icon = "LangChain"

    inputs = [
        *LCAgentComponent.get_base_inputs(),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
            info="An LLM Model Object (It can be found in any LLM Component).",
        ),
        FileInput(
            name="path",
            display_name="File Path",
            file_types=["csv"],
            input_types=["str", "Message"],
            required=True,
            info="A CSV File or File Path.",
        ),
        DropdownInput(
            name="agent_type",
            display_name="Agent Type",
            advanced=True,
            options=["zero-shot-react-description", "openai-functions", "openai-tools"],
            value="openai-tools",
        ),
        MessageTextInput(
            name="input_value",
            display_name="Text",
            info="Text to be passed as input and extract info from the CSV File.",
            required=True,
        ),
        DictInput(
            name="pandas_kwargs",
            display_name="Pandas Kwargs",
            info="Pandas Kwargs to be passed to the agent.",
            advanced=True,
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="build_agent_response"),
        Output(display_name="Agent", name="agent", method="build_agent", hidden=True, tool_mode=False),
    ]

    def _path(self) -> str:
        if isinstance(self.path, Message) and isinstance(self.path.text, str):
            return self.path.text
        return self.path

    def build_agent_response(self) -> Message:
        """Build and execute the CSV agent, returning the response."""
        try:
            from langchain_experimental.agents.agent_toolkits.csv.base import create_csv_agent
        except ImportError as e:
            msg = (
                "langchain-experimental is not installed. Please install it with `pip install langchain-experimental`."
            )
            raise ImportError(msg) from e

        try:
            agent_kwargs = {
                "verbose": self.verbose,
                "allow_dangerous_code": True,
            }

            # Get local path (downloads from S3 if needed)
            local_path = self._get_local_path()

            agent_csv = create_csv_agent(
                llm=self.llm,
                path=local_path,
                agent_type=self.agent_type,
                handle_parsing_errors=self.handle_parsing_errors,
                pandas_kwargs=self.pandas_kwargs,
                **agent_kwargs,
            )

            result = agent_csv.invoke({"input": self.input_value})
            return Message(text=str(result["output"]))

        finally:
            # Clean up temp file if created
            self._cleanup_temp_file()

    def build_agent(self) -> AgentExecutor:
        try:
            from langchain_experimental.agents.agent_toolkits.csv.base import create_csv_agent
        except ImportError as e:
            msg = (
                "langchain-experimental is not installed. Please install it with `pip install langchain-experimental`."
            )
            raise ImportError(msg) from e

        agent_kwargs = {
            "verbose": self.verbose,
            "allow_dangerous_code": True,
        }

        # Get local path (downloads from S3 if needed)
        local_path = self._get_local_path()

        agent_csv = create_csv_agent(
            llm=self.llm,
            path=local_path,
            agent_type=self.agent_type,
            handle_parsing_errors=self.handle_parsing_errors,
            pandas_kwargs=self.pandas_kwargs,
            **agent_kwargs,
        )

        self.status = Message(text=str(agent_csv))

        # Note: Temp file will be cleaned up when the component is destroyed or
        # when build_agent_response is called
        return agent_csv

    def _get_local_path(self) -> str:
        """Get a local file path, downloading from S3 storage if necessary.

        Returns:
            str: Local file path that can be used by LangChain
        """
        file_path = self._path()
        settings = get_settings_service().settings

        # If using S3 storage, download the file to temp
        if settings.storage_type == "s3":
            # Download from S3 to temp file
            csv_bytes = run_until_complete(read_file_bytes(file_path))

            # Create temp file with .csv extension
            suffix = Path(file_path.split("/")[-1]).suffix or ".csv"
            with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(csv_bytes)
                temp_path = tmp_file.name

            # Store temp path for cleanup
            self._temp_file_path = temp_path
            return temp_path

        # Local storage - return path as-is
        return file_path

    def _cleanup_temp_file(self) -> None:
        """Clean up temporary file if one was created."""
        if hasattr(self, "_temp_file_path"):
            with contextlib.suppress(Exception):
                Path(self._temp_file_path).unlink()  # Ignore cleanup errors
