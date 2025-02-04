from pathlib import Path
import json
import pandas as pd
from langflow.custom import Component
from langflow.io import (
    DataInput,
    MessageInput,
    DataFrameInput,
    DropdownInput,
    StrInput,
    Output,
)
from langflow.schema import Data, Message, DataFrame


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
            build_config["df"]["show"] = (field_value == "DataFrame")
            build_config["data"]["show"] = (field_value == "Data")
            build_config["message"]["show"] = (field_value == "Message")

            if field_value in ["DataFrame", "Data"]:
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
            df = self.df
            return self._save_dataframe(df, file_path, file_format)
        elif input_type == "Data":
            data = self.data
            return self._save_data(data, file_path, file_format)
        elif input_type == "Message":
            message = self.message
            return self._save_message(message, file_path, file_format)
        else:
            raise ValueError(f"Unsupported input type: {input_type}")

    def _save_dataframe(self, df: DataFrame, path: Path, fmt: str) -> str:
        if fmt == "csv":
            df.to_csv(path, index=False)
        elif fmt == "excel":
            df.to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            df.to_json(path, orient="records", indent=2)
        elif fmt == "markdown":
            with open(path, "w", encoding="utf-8") as f:
                f.write(df.to_markdown(index=False))
        else:
            raise ValueError(f"Unsupported DataFrame format: {fmt}")

        return f"DataFrame saved successfully as '{path}'"

    def _save_data(self, data: Data, path: Path, fmt: str) -> str:
        if fmt == "csv":
            pd.DataFrame(data.data).to_csv(path, index=False)
        elif fmt == "excel":
            pd.DataFrame(data.data).to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data.data, f, indent=2)
        elif fmt == "markdown":
            with open(path, "w", encoding="utf-8") as f:
                f.write(pd.DataFrame(data.data).to_markdown(index=False))
        else:
            raise ValueError(f"Unsupported Data format: {fmt}")

        return f"Data saved successfully as '{path}'"

    def _save_message(self, message: Message, path: Path, fmt: str) -> str:
        content = message.text

        if fmt == "txt":
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        elif fmt == "json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"message": content}, f, indent=2)
        elif fmt == "markdown":
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"**Message:**\n\n{content}")
        else:
            raise ValueError(f"Unsupported Message format: {fmt}")

        return f"Message saved successfully as '{path}'"


