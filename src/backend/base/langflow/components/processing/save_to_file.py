import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pandas as pd

from langflow.custom import Component
from langflow.io import (
    DataFrameInput,
    DataInput,
    DropdownInput,
    MessageInput,
    Output,
    StrInput,
)
from langflow.schema import Data, DataFrame, Message


class SaveToFileComponent(Component):
    display_name = "Save to File"
    description = "Save DataFrames, Data, or Messages to various file formats."
    icon = "save"
    name = "SaveToFile"

    # File format options for different types
    DATA_FORMAT_CHOICES = ["csv", "excel", "json", "markdown"]
    MESSAGE_FORMAT_CHOICES = ["txt", "json", "markdown"]

    inputs = [
        DropdownInput(
            name="input_type",
            display_name="Input Type",
            options=["DataFrame", "Data", "Message"],
            info="Select the type of input to save.",
            value="DataFrame",
            real_time_refresh=True,
        ),
        DataFrameInput(
            name="df",
            display_name="DataFrame",
            info="The DataFrame to save.",
            dynamic=True,
            show=True,
        ),
        DataInput(
            name="data",
            display_name="Data",
            info="The Data object to save.",
            dynamic=True,
            show=False,
        ),
        MessageInput(
            name="message",
            display_name="Message",
            info="The Message to save.",
            dynamic=True,
            show=False,
        ),
        DropdownInput(
            name="file_format",
            display_name="File Format",
            options=DATA_FORMAT_CHOICES,
            info="Select the file format to save the input.",
            real_time_refresh=True,
        ),
        StrInput(
            name="file_path",
            display_name="File Path (including filename)",
            info="The full file path (including filename and extension).",
            value="./output",
        ),
    ]

    outputs = [
        Output(
            name="confirmation",
            display_name="Confirmation",
            method="save_to_file",
            info="Confirmation message after saving the file.",
        ),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        # Hide/show dynamic fields based on the selected input type
        if field_name == "input_type":
            build_config["df"]["show"] = field_value == "DataFrame"
            build_config["data"]["show"] = field_value == "Data"
            build_config["message"]["show"] = field_value == "Message"

            if field_value in {"DataFrame", "Data"}:
                build_config["file_format"]["options"] = self.DATA_FORMAT_CHOICES
            elif field_value == "Message":
                build_config["file_format"]["options"] = self.MESSAGE_FORMAT_CHOICES

        return build_config

    def save_to_file(self) -> str:
        input_type = self.input_type
        file_format = self.file_format
        file_path = Path(self.file_path).expanduser()

        # Ensure the directory exists
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        if input_type == "DataFrame":
            dataframe = self.df
            return self._save_dataframe(dataframe, file_path, file_format)
        if input_type == "Data":
            data = self.data
            return self._save_data(data, file_path, file_format)
        if input_type == "Message":
            message = self.message
            return self._save_message(message, file_path, file_format)

        error_msg = f"Unsupported input type: {input_type}"
        raise ValueError(error_msg)

    def _save_dataframe(self, dataframe: DataFrame, path: Path, fmt: str) -> str:
        if fmt == "csv":
            dataframe.to_csv(path, index=False)
        elif fmt == "excel":
            dataframe.to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            dataframe.to_json(path, orient="records", indent=2)
        elif fmt == "markdown":
            path.write_text(dataframe.to_markdown(index=False), encoding="utf-8")
        else:
            error_msg = f"Unsupported DataFrame format: {fmt}"
            raise ValueError(error_msg)

        return f"DataFrame saved successfully as '{path}'"

    def _save_data(self, data: Data, path: Path, fmt: str) -> str:
        if fmt == "csv":
            pd.DataFrame(data.data).to_csv(path, index=False)
        elif fmt == "excel":
            pd.DataFrame(data.data).to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            path.write_text(json.dumps(data.data, indent=2), encoding="utf-8")
        elif fmt == "markdown":
            path.write_text(pd.DataFrame(data.data).to_markdown(index=False), encoding="utf-8")
        else:
            error_msg = f"Unsupported Data format: {fmt}"
            raise ValueError(error_msg)

        return f"Data saved successfully as '{path}'"

    def _save_message(self, message: Message, path: Path, fmt: str) -> str:
        if message.text is None:
            content = ""
        elif isinstance(message.text, AsyncIterator):
            # AsyncIterator needs to be handled differently
            error_msg = "AsyncIterator not supported"
            raise ValueError(error_msg)
        elif isinstance(message.text, Iterator):
            # Convert iterator to string
            content = " ".join(str(item) for item in message.text)
        else:
            content = str(message.text)

        if fmt == "txt":
            path.write_text(content, encoding="utf-8")
        elif fmt == "json":
            path.write_text(json.dumps({"message": content}, indent=2), encoding="utf-8")
        elif fmt == "markdown":
            path.write_text(f"**Message:**\n\n{content}", encoding="utf-8")
        else:
            error_msg = f"Unsupported Message format: {fmt}"
            raise ValueError(error_msg)

        return f"Message saved successfully as '{path}'"
