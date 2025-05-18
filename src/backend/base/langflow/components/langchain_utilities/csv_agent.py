import tempfile
from pathlib import Path

import chardet
import pandas as pd
from langchain_experimental.agents.agent_toolkits.csv.base import create_csv_agent

from langflow.base.agents.agent import LCAgentComponent
from langflow.field_typing import AgentExecutor
from langflow.inputs import DropdownInput, FileInput, HandleInput
from langflow.inputs.inputs import DictInput, MessageTextInput
from langflow.schema.message import Message
from langflow.template.field.base import Output


class CSVAgentComponent(LCAgentComponent):
    display_name = "CSVAgent"
    description = "Construct a CSV agent from a CSV and tools."
    documentation = "https://python.langchain.com/docs/modules/agents/toolkits/csv"
    name = "CSVAgent"
    icon = "LangChain"

    inputs = [
        *LCAgentComponent._base_inputs,
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

    def _robust_csv_path(self) -> str:
        """Reads the file with auto-detected encoding and returns a cleaned temp CSV path."""
        file_path = Path(self._path())

        # Detect encoding
        with file_path.open("rb") as f:
            raw_data = f.read(10000)
            detected = chardet.detect(raw_data)
            encoding = detected.get("encoding", "utf-8")

        # Read with encoding and skip bad lines
        try:
            data_frame = pd.read_csv(file_path, encoding=encoding, on_bad_lines="skip")
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {e}") from e

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="w", newline="", encoding="utf-8"
        ) as temp_file:
            data_frame.to_csv(temp_file, index=False)
            return temp_file.name

    def _path(self) -> str:
        if isinstance(self.path, Message) and isinstance(self.path.text, str):
            return self.path.text
        return self.path

    def build_agent_response(self) -> Message:
        agent_kwargs = {
            "verbose": self.verbose,
            "allow_dangerous_code": True,
        }

        cleaned_path = self._robust_csv_path()

        agent_csv = create_csv_agent(
            llm=self.llm,
            path=cleaned_path,
            agent_type=self.agent_type,
            handle_parsing_errors=True,
            pandas_kwargs=self.pandas_kwargs,
            **agent_kwargs,
        )

        result = agent_csv.invoke({"input": self.input_value})
        Path(cleaned_path).unlink(missing_ok=True)
        return Message(text=str(result["output"]))

    def build_agent(self) -> AgentExecutor:
        agent_kwargs = {
            "verbose": self.verbose,
            "allow_dangerous_code": True,
        }

        cleaned_path = self._robust_csv_path()

        agent_csv = create_csv_agent(
            llm=self.llm,
            path=cleaned_path,
            agent_type=self.agent_type,
            handle_parsing_errors=True,
            pandas_kwargs=self.pandas_kwargs,
            **agent_kwargs,
        )

        self.status = Message(text=str(agent_csv))

        return agent_csv
