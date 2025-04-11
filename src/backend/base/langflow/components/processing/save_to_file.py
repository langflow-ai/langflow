import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

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

        file_path = self._check_file_format(file_path, file_format)

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

    def _check_file_format(self, path: Path, fmt: str) -> Path:
        file_extension = path.suffix.lower().lstrip(".")

        if fmt == "excel":
            return Path(f"{path}.xlsx").expanduser() if file_extension not in ["xlsx", "xls"] else path

        return Path(f"{path}.{fmt}").expanduser() if file_extension != fmt else path

    def _save_dataframe(self, dataframe: DataFrame, path: Path, fmt: str) -> str:
        # Mapping of format to save function
        save_functions = {
            "csv": lambda: dataframe.to_csv(path, index=False),
            "excel": lambda: dataframe.to_excel(path, index=False, engine="openpyxl"),
            "json": lambda: dataframe.to_json(path, orient="records", indent=2),
            "markdown": lambda: path.write_text(dataframe.to_markdown(index=False), encoding="utf-8"),
            "pdf": lambda: self._save_dataframe_to_pdf(dataframe, path),
        }

        if fmt not in save_functions:
            error_msg = f"Unsupported DataFrame format: {fmt}"
            raise ValueError(error_msg)

        # Execute the save function
        save_functions[fmt]()

        return f"DataFrame saved successfully as '{path}'"

    def _save_data(self, data: Data, path: Path, fmt: str) -> str:
        if isinstance(data, list):
            error_msg = "Data is a list, not a Data object"
            raise TypeError(error_msg)

        # Handle single dictionary case
        dataframe = pd.DataFrame([data.data]) if isinstance(data.data, dict) else pd.DataFrame(data.data)

        # Mapping of format to save function
        save_functions = {
            "csv": lambda: dataframe.to_csv(path, index=False),
            "excel": lambda: dataframe.to_excel(path, index=False, engine="openpyxl"),
            "json": lambda: path.write_text(json.dumps(data.data, indent=2), encoding="utf-8"),
            "markdown": lambda: path.write_text(dataframe.to_markdown(index=False), encoding="utf-8"),
            "pdf": lambda: self._save_dataframe_to_pdf(data, path),
        }

        if fmt not in save_functions:
            error_msg = f"Unsupported Data format: {fmt}"
            raise ValueError(error_msg)

        # Execute the save function
        save_functions[fmt]()

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

        # Mapping of format to save function
        save_functions = {
            "txt": lambda: path.write_text(content, encoding="utf-8"),
            "json": lambda: path.write_text(json.dumps({"message": content}, indent=2), encoding="utf-8"),
            "markdown": lambda: path.write_text(f"**Message:**\n\n{content}", encoding="utf-8"),
            "pdf": lambda: self._save_message_to_pdf(content, path),
        }

        if fmt not in save_functions:
            error_msg = f"Unsupported Message format: {fmt}"
            raise ValueError(error_msg)

        save_functions[fmt]()

        return f"Message saved successfully as '{path}'"

    def _save_dataframe_to_pdf(self, dataframe: DataFrame | pd.DataFrame | Data, path: Path) -> None:
        """Save DataFrame to PDF format."""
        doc = SimpleDocTemplate(str(path), pagesize=letter)
        elements = []

        if not isinstance(dataframe, pd.DataFrame):
            # Handle single row data by wrapping it in a list
            if isinstance(dataframe.data, dict):
                dataframe = pd.DataFrame([dataframe.data])
            else:
                dataframe = pd.DataFrame(dataframe.data)

        # Convert DataFrame to a list of lists for the table
        data = [dataframe.columns.tolist()] + dataframe.values.tolist()

        # Create the table
        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        elements.append(table)
        doc.build(elements)

    def _save_message_to_pdf(self, content: str, path: Path) -> None:
        """Save Message content to PDF format."""
        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            leftMargin=1 * inch,
            rightMargin=1 * inch,
            topMargin=1 * inch,
            bottomMargin=1 * inch,
        )
        elements = []

        styles = getSampleStyleSheet()
        message_style = ParagraphStyle(
            "MessageStyle",
            parent=styles["Normal"],
            fontSize=12,
            leading=14,  # Line spacing
            spaceBefore=20,
            spaceAfter=20,
            textColor=colors.black,
            fontName="Helvetica",
        )

        # Process content with XML-like markups
        # Add message content with proper wrapping and markup support
        message = Paragraph(content, message_style)
        elements.append(message)

        doc.build(elements)
