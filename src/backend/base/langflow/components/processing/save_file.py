import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import orjson
import pandas as pd
from fastapi import UploadFile
from fastapi.encoders import jsonable_encoder

from langflow.api.v2.files import upload_user_file
from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, StrInput
from langflow.schema import Data, DataFrame, Message
from langflow.services.auth.utils import create_user_longterm_token
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_session, get_settings_service, get_storage_service
from langflow.template.field.base import Output


class SaveToFileComponent(Component):
    display_name = "Save File"
    description = "Save data to a local file in the selected format."
    icon = "save"
    name = "SaveToFile"

    # File format options for different types
    DATA_FORMAT_CHOICES = ["csv", "excel", "json", "markdown"]
    MESSAGE_FORMAT_CHOICES = ["txt", "json", "markdown"]

    inputs = [
        HandleInput(
            name="input",
            display_name="Input",
            info="The input to save.",
            dynamic=True,
            input_types=["Data", "DataFrame", "Message"],
            required=True,
        ),
        StrInput(
            name="file_name",
            display_name="File Name",
            info="Name file will be saved as (without extension).",
            required=True,
        ),
        DropdownInput(
            name="file_format",
            display_name="File Format",
            options=DATA_FORMAT_CHOICES + MESSAGE_FORMAT_CHOICES,
            info="Select the file format to save the input. If not provided, the default format will be used.",
            value="",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="File Path", name="result", method="save_to_file")]

    async def save_to_file(self) -> Message:
        """Save the input to a file and upload it, returning a confirmation message."""
        # Validate inputs
        if not self.file_name:
            msg = "File name must be provided."
            raise ValueError(msg)
        if not self._get_input_type():
            msg = "Input type is not set."
            raise ValueError(msg)

        # Validate file format based on input type
        file_format = self.file_format or self._get_default_format()
        allowed_formats = (
            self.MESSAGE_FORMAT_CHOICES if self._get_input_type() == "Message" else self.DATA_FORMAT_CHOICES
        )
        if file_format not in allowed_formats:
            msg = f"Invalid file format '{file_format}' for {self._get_input_type()}. Allowed: {allowed_formats}"
            raise ValueError(msg)

        # Prepare file path
        file_path = Path(self.file_name).expanduser()
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = self._adjust_file_path_with_format(file_path, file_format)

        # Save the input to file based on type
        if self._get_input_type() == "DataFrame":
            confirmation = self._save_dataframe(self.input, file_path, file_format)
        elif self._get_input_type() == "Data":
            confirmation = self._save_data(self.input, file_path, file_format)
        elif self._get_input_type() == "Message":
            confirmation = await self._save_message(self.input, file_path, file_format)
        else:
            msg = f"Unsupported input type: {self._get_input_type()}"
            raise ValueError(msg)

        # Upload the saved file
        await self._upload_file(file_path)

        # Return the final file path and confirmation message
        final_path = Path.cwd() / file_path if not file_path.is_absolute() else file_path

        return Message(text=f"{confirmation} at {final_path}")

    def _get_input_type(self) -> str:
        """Determine the input type based on the provided input."""
        if isinstance(self.input, DataFrame):
            return "DataFrame"
        if isinstance(self.input, Data):
            return "Data"
        if isinstance(self.input, Message):
            return "Message"

        msg = f"Unsupported input type: {type(self.input)}"
        raise ValueError(msg)

    def _get_default_format(self) -> str:
        """Return the default file format based on input type."""
        if self._get_input_type() == "DataFrame":
            return "csv"
        if self._get_input_type() == "Data":
            return "json"
        if self._get_input_type() == "Message":
            return "markdown"
        return "json"  # Fallback

    def _adjust_file_path_with_format(self, path: Path, fmt: str) -> Path:
        """Adjust the file path to include the correct extension."""
        file_extension = path.suffix.lower().lstrip(".")
        if fmt == "excel":
            return Path(f"{path}.xlsx").expanduser() if file_extension not in ["xlsx", "xls"] else path
        return Path(f"{path}.{fmt}").expanduser() if file_extension != fmt else path

    async def _upload_file(self, file_path: Path) -> None:
        """Upload the saved file using the upload_user_file service."""
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        with file_path.open("rb") as f:
            async for db in get_session():
                user_id, _ = await create_user_longterm_token(db)
                current_user = await get_user_by_id(db, user_id)

                await upload_user_file(
                    file=UploadFile(filename=file_path.name, file=f, size=file_path.stat().st_size),
                    session=db,
                    current_user=current_user,
                    storage_service=get_storage_service(),
                    settings_service=get_settings_service(),
                )

    def _save_dataframe(self, dataframe: DataFrame, path: Path, fmt: str) -> str:
        """Save a DataFrame to the specified file format."""
        if fmt == "csv":
            dataframe.to_csv(path, index=False)
        elif fmt == "excel":
            dataframe.to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            dataframe.to_json(path, orient="records", indent=2)
        elif fmt == "markdown":
            path.write_text(dataframe.to_markdown(index=False), encoding="utf-8")
        else:
            msg = f"Unsupported DataFrame format: {fmt}"
            raise ValueError(msg)
        return f"DataFrame saved successfully as '{path}'"

    def _save_data(self, data: Data, path: Path, fmt: str) -> str:
        """Save a Data object to the specified file format."""
        if fmt == "csv":
            pd.DataFrame(data.data).to_csv(path, index=False)
        elif fmt == "excel":
            pd.DataFrame(data.data).to_excel(path, index=False, engine="openpyxl")
        elif fmt == "json":
            path.write_text(
                orjson.dumps(jsonable_encoder(data.data), option=orjson.OPT_INDENT_2).decode("utf-8"), encoding="utf-8"
            )
        elif fmt == "markdown":
            path.write_text(pd.DataFrame(data.data).to_markdown(index=False), encoding="utf-8")
        else:
            msg = f"Unsupported Data format: {fmt}"
            raise ValueError(msg)
        return f"Data saved successfully as '{path}'"

    async def _save_message(self, message: Message, path: Path, fmt: str) -> str:
        """Save a Message to the specified file format, handling async iterators."""
        content = ""
        if message.text is None:
            content = ""
        elif isinstance(message.text, AsyncIterator):
            async for item in message.text:
                content += str(item) + " "
            content = content.strip()
        elif isinstance(message.text, Iterator):
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
            msg = f"Unsupported Message format: {fmt}"
            raise ValueError(msg)
        return f"Message saved successfully as '{path}'"
