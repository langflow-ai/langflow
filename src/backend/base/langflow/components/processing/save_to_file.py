import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Literal

import pandas as pd
from fpdf import FPDF, HTMLMixin

from langflow.custom import Component
from langflow.io import DataFrameInput, DataInput, DropdownInput, MessageInput, Output, StrInput
from langflow.schema import Data, DataFrame, Message


class SaveToFileComponent(Component):
    display_name = "Save to File"
    description = "Save DataFrames, Data, or Messages to various file formats."
    icon = "save"
    name = "SaveToFile"

    # File format options for different types
    DATA_FORMAT_CHOICES = ["csv", "excel", "json", "markdown", "pdf"]
    MESSAGE_FORMAT_CHOICES = ["txt", "json", "markdown", "pdf"]
    SUPPORTED_EXTENSIONS = {
        "txt": ["txt"],
        "excel": ["xlsx", "xls"],
        "csv": ["csv"],
        "json": ["json"],
        "markdown": ["md", "markdown"],
        "pdf": ["pdf"],
    }

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

        file_path = self._adjust_file_path_with_format(file_path, file_format)

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

    def _adjust_file_path_with_format(self, path: Path, fmt: str) -> Path:
        file_extension = path.suffix.lower().lstrip(".")
        return (
            Path(f"{path}.{self.SUPPORTED_EXTENSIONS[fmt][0]}").expanduser()
            if file_extension not in self.SUPPORTED_EXTENSIONS[fmt]
            else path
        )

    def _check_format_supported(self, fmt: str, save_functions: dict, data_type: str) -> None:
        """Check if the format is supported and raise ValueError if not."""
        if fmt not in save_functions:
            error_msg = f"Unsupported {data_type} format: {fmt}"
            raise ValueError(error_msg)

    def _get_save_functions(self, data_type: Literal["dataframe", "data", "message"]):
        """Get the appropriate save functions based on data type."""
        if data_type == "message":
            return {
                "txt": lambda data, path: path.write_text(data, encoding="utf-8"),
                "json": lambda data, path: path.write_text(json.dumps({"message": data}, indent=2), encoding="utf-8"),
                "markdown": lambda data, path: path.write_text(f"**Message:**\n\n{data}", encoding="utf-8"),
                "pdf": lambda data, path: self._save_message_to_pdf(data, path),
            }

        common_functions = {
            "csv": lambda data, path: data.to_csv(path, index=False),
            "excel": lambda data, path: data.to_excel(path, index=False, engine="openpyxl"),
            "markdown": lambda data, path: path.write_text(data.to_markdown(index=False), encoding="utf-8"),
            "pdf": lambda data, path: self._save_dataframe_to_pdf(data, path),
        }

        if data_type == "data":
            common_functions["json"] = lambda data, path: path.write_text(
                json.dumps(data.data, indent=2), encoding="utf-8"
            )
        else:
            common_functions["json"] = lambda data, path: data.to_json(path, orient="records", indent=2)

        return common_functions

    def _save_dataframe(self, dataframe: DataFrame, path: Path, fmt: str) -> str:
        """Save DataFrame to file in the specified format."""
        save_functions = self._get_save_functions("dataframe")
        self._check_format_supported(fmt, save_functions, "DataFrame")
        save_functions[fmt](dataframe, path)
        return f"DataFrame saved successfully as '{path}'"

    def _save_data(self, data: Data, path: Path, fmt: str) -> str:
        """Save Data object to file in the specified format."""
        if isinstance(data, list):
            error_msg = "Data is a list, not a Data object"
            raise TypeError(error_msg)

        save_functions = self._get_save_functions("data")
        self._check_format_supported(fmt, save_functions, "Data")

        # For JSON format, we want to save the original data structure
        formatted_data = data if fmt == "json" else self._handle_single_dict(data)
        save_functions[fmt](formatted_data, path)
        return f"Data saved successfully as '{path}'"

    def _handle_single_dict(self, data: Data) -> pd.DataFrame:
        return pd.DataFrame([data.data]) if isinstance(data.data, dict) else pd.DataFrame(data.data)

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

        save_functions = self._get_save_functions("message")
        self._check_format_supported(fmt, save_functions, "Message")
        save_functions[fmt](content, path)
        return f"Message saved successfully as '{path}'"

    def _save_dataframe_to_pdf(self, dataframe: DataFrame | pd.DataFrame | Data, path: Path) -> None:
        """Save DataFrame to PDF format using FPDF."""
        if not isinstance(dataframe, pd.DataFrame):
            # Handle single row data by wrapping it in a list
            if isinstance(dataframe.data, dict):
                dataframe = pd.DataFrame([dataframe.data])
            else:
                dataframe = pd.DataFrame(dataframe.data)

        # Create PDF document
        pdf = FPDF()
        pdf.add_page()

        # Set font for header
        pdf.set_font("Arial", "B", 14)

        # Get column names and data
        columns = dataframe.columns.tolist()
        data = dataframe.to_numpy().tolist()

        # Calculate column widths
        col_widths = []
        for col in columns:
            # Find the maximum width needed for this column
            max_width = len(str(col)) * 7
            for row in data:
                max_width = max(max_width, len(str(row[columns.index(col)])) * 7)
            col_widths.append(max_width)

        # Adjust column widths to fit page
        total_width = sum(col_widths)
        page_width = pdf.w - 20
        if total_width > page_width:
            ratio = page_width / total_width
            col_widths = [width * ratio for width in col_widths]

        # Add header row
        pdf.set_fill_color(200, 200, 200)  # Light gray background
        pdf.set_text_color(0, 0, 0)  # Black text
        for i, col in enumerate(columns):
            pdf.cell(w=col_widths[i], h=10, text=str(col), border=1, ln=0, align="C", fill=True)
        pdf.ln()

        # Add data rows
        pdf.set_fill_color(245, 245, 220)  # Beige background
        pdf.set_font("Arial", "", 12)
        for row in data:
            for i, cell in enumerate(row):
                pdf.cell(w=col_widths[i], h=10, text=str(cell), border=1, ln=0, align="C", fill=True)
            pdf.ln()

        pdf.output(str(path))

    def _save_message_to_pdf(self, content: str, path: Path) -> None:
        """Save Message content to PDF format using FPDF with HTML support."""

        class MyFPDF(FPDF, HTMLMixin):
            pass

        pdf = MyFPDF()
        pdf.add_page()
        pdf.write_html(content)
        pdf.output(str(path))
