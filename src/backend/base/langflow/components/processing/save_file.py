import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import orjson
import pandas as pd
from fastapi import UploadFile
from fastapi.encoders import jsonable_encoder

from langflow.api.v2.files import upload_user_file
from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, MessageTextInput
from langflow.schema import Data, DataFrame, Message
from langflow.services.auth.utils import create_user_longterm_token
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_session, get_settings_service, get_storage_service
from langflow.template.field.base import Output


class SaveToFileComponent(Component):
    display_name = "Save File"
    description = "Save data to a local file in the selected format."
    documentation: str = "https://docs.langflow.org/components-processing#save-file"
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
        MessageTextInput(
            name="file_name",
            display_name="File Name",
            info="Name file will be saved as (without extension). Can be a string or Message node.",
            required=True,
        ),
        MessageTextInput(
            name="directory_path",
            display_name="Directory Path",
            info="Directory where the file will be saved. Leave empty to use current working directory.",
            required=False,
        ),
        DropdownInput(
            name="file_format",
            display_name="File Format",
            options=list(dict.fromkeys(DATA_FORMAT_CHOICES + MESSAGE_FORMAT_CHOICES)),
            info="Select the file format to save the input.",
            value="",
            required=True,
        ),
    ]

    outputs = [Output(display_name="File Path", name="result", method="save_to_file")]

    async def save_to_file(self) -> Message:
        """Save the input to a file and upload it, returning the file path."""
        # Validate inputs
        if not self.file_name:
            msg = "File name must be provided"
            raise ValueError(msg)

        # Extract file name from input (handle both string and Message types)
        file_name = self._extract_file_name(self.file_name)
        if not file_name:
            msg = "File name must be provided and cannot be empty"
            raise ValueError(msg)

        # Get and validate file format based on input type
        input_type = self._get_input_type()
        file_format = self.file_format
        
        # Determine allowed formats based on input type
        if input_type == "Message":
            allowed_formats = self.MESSAGE_FORMAT_CHOICES
        elif input_type == "DataFrame":
            allowed_formats = self.DATA_FORMAT_CHOICES
        elif input_type == "Data":
            allowed_formats = self.DATA_FORMAT_CHOICES  # Now Excel is supported for Data objects
        else:
            allowed_formats = self.DATA_FORMAT_CHOICES
        
        if not file_format:
            msg = f"File format must be selected for {input_type} input"
            raise ValueError(msg)
        
        if file_format not in allowed_formats:
            msg = f"Invalid file format '{file_format}' for {input_type} input"
            raise ValueError(msg)

        # Prepare file path with custom directory if specified
        if self.directory_path:
            directory = self._extract_directory_path(self.directory_path)
            if directory:
                # Create directory if it doesn't exist
                directory_path = Path(directory).expanduser().resolve()
                directory_path.mkdir(parents=True, exist_ok=True)
                file_path = directory_path / file_name
            else:
                # Fallback to current directory
                file_path = Path(file_name).expanduser()
        else:
            # Use current working directory
            file_path = Path(file_name).expanduser()
        
        # Ensure parent directory exists
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_path = self._adjust_file_path_with_format(file_path, file_format)

        # Save the input to file based on type
        if input_type == "DataFrame":
            if isinstance(self.input, list):
                # Handle list of DataFrames
                self._save_dataframe_list(self.input, file_path, file_format)
            else:
                self._save_dataframe(self.input, file_path, file_format)
        elif input_type == "Data":
            if isinstance(self.input, list):
                # Handle list of Data objects
                self._save_data_list(self.input, file_path, file_format)
            else:
                self._save_data(self.input, file_path, file_format)
        elif input_type == "Message":
            if isinstance(self.input, list):
                # Handle list of Messages
                await self._save_message_list(self.input, file_path, file_format)
            else:
                await self._save_message(self.input, file_path, file_format)
        else:
            msg = f"Unsupported input type: {input_type}"
            raise ValueError(msg)

        # Upload the saved file
        await self._upload_file(file_path)

        # Return only the file path
        final_path = file_path.resolve()
        return Message(text=str(final_path))

    def _extract_file_name(self, file_name_input) -> str:
        """Extract file name from input, handling both string and Message types."""
        if file_name_input is None:
            return ""
        return str(file_name_input).strip()

    def _extract_directory_path(self, directory_input) -> str:
        """Extract directory path from input, handling both string and Message types."""
        if directory_input is None:
            return ""
        directory_str = str(directory_input).strip()
        
        # Handle common directory patterns
        if directory_str:
            # Remove trailing slashes for consistency
            directory_str = directory_str.rstrip('/\\')
            # Handle relative paths
            if directory_str.startswith('./'):
                directory_str = directory_str[2:]
            elif directory_str.startswith('../'):
                # Keep relative paths as is
                pass
            elif not directory_str.startswith('/') and not directory_str.startswith('\\') and ':' not in directory_str:
                # If it's not an absolute path and not a Windows drive path, treat as relative
                pass
        
        return directory_str

    def _get_input_type(self) -> str:
        """Determine the input type based on the provided input."""
        # Handle list inputs (e.g., list of Data objects)
        if isinstance(self.input, list):
            if not self.input:
                msg = "Input list is empty"
                raise ValueError(msg)
            # Check the first item to determine the type
            first_item = self.input[0]
            if type(first_item) is DataFrame:
                return "DataFrame"
            elif type(first_item) is Message:
                return "Message"
            elif type(first_item) is Data:
                return "Data"
            else:
                msg = f"Unsupported list item type: {type(first_item)}"
                raise ValueError(msg)
        
        # Use exact type checking (type() is) instead of isinstance() to avoid inheritance issues.
        # Since Message inherits from Data, isinstance(message, Data) would return True for Message objects,
        # causing Message inputs to be incorrectly identified as Data type.
        if type(self.input) is DataFrame:
            return "DataFrame"
        if type(self.input) is Message:
            return "Message"
        if type(self.input) is Data:
            return "Data"
        msg = f"Unsupported input type: {type(self.input)}"
        raise ValueError(msg)

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

    def _create_dataframe_from_data(self, data) -> pd.DataFrame:
        """Create a DataFrame from data, handling different data structures properly."""
        try:
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], dict):
                    # List of dictionaries - perfect for DataFrame
                    return pd.DataFrame(data)
                else:
                    # List of other types - try to convert directly
                    return pd.DataFrame(data)
            elif isinstance(data, dict):
                # Single dictionary - convert to DataFrame with one row
                return pd.DataFrame([data])
            else:
                # Other data types - try to convert directly
                return pd.DataFrame(data)
        except Exception as e:
            msg = f"Error creating DataFrame from data: {str(e)}"
            raise ValueError(msg)

    def _save_dataframe(self, dataframe: DataFrame, path: Path, fmt: str) -> None:
        """Save a DataFrame to the specified file format."""
        if fmt == "csv":
            dataframe.to_csv(path, index=False)
        elif fmt == "excel":
            try:
                if dataframe.empty:
                    msg = "Cannot save empty DataFrame to Excel format"
                    raise ValueError(msg)
                
                if len(dataframe.columns) == 0:
                    msg = "Cannot save DataFrame with no columns to Excel format"
                    raise ValueError(msg)
                
                dataframe.to_excel(path, index=False, engine="openpyxl")
            except ImportError:
                msg = "Excel format requires the 'openpyxl' library"
                raise ImportError(msg)
            except Exception as e:
                msg = f"Error saving DataFrame to Excel: {str(e)}"
                raise ValueError(msg)
        elif fmt == "json":
            dataframe.to_json(path, orient="records", indent=2)
        elif fmt == "markdown":
            path.write_text(dataframe.to_markdown(index=False), encoding="utf-8")
        else:
            msg = f"Unsupported DataFrame format: {fmt}"
            raise ValueError(msg)

    def _save_dataframe_list(self, dataframes: list, path: Path, fmt: str) -> None:
        """Save a list of DataFrames to the specified file format."""
        if fmt == "csv":
            # Combine all DataFrames and save as one CSV
            combined_df = pd.concat(dataframes, ignore_index=True)
            combined_df.to_csv(path, index=False)
        elif fmt == "excel":
            try:
                # Validate DataFrames before saving
                for i, df in enumerate(dataframes):
                    if df.empty:
                        msg = f"DataFrame at index {i} is empty and cannot be saved to Excel"
                        raise ValueError(msg)
                    if len(df.columns) == 0:
                        msg = f"DataFrame at index {i} has no columns and cannot be saved to Excel"
                        raise ValueError(msg)
                
                # Save each DataFrame to a separate sheet
                with pd.ExcelWriter(path, engine="openpyxl") as writer:
                    for i, df in enumerate(dataframes):
                        sheet_name = f"Sheet{i+1}" if len(dataframes) > 1 else "Sheet1"
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
            except ImportError:
                msg = "Excel format requires the 'openpyxl' library"
                raise ImportError(msg)
            except Exception as e:
                msg = f"Error saving DataFrames to Excel: {str(e)}"
                raise ValueError(msg)
        elif fmt == "json":
            # Save as a list of records
            all_records = []
            for df in dataframes:
                all_records.extend(df.to_dict("records"))
            path.write_text(json.dumps(all_records, indent=2), encoding="utf-8")
        elif fmt == "markdown":
            # Combine all DataFrames and save as markdown
            combined_df = pd.concat(dataframes, ignore_index=True)
            path.write_text(combined_df.to_markdown(index=False), encoding="utf-8")
        else:
            msg = f"Unsupported DataFrame list format: {fmt}"
            raise ValueError(msg)

    def _save_data(self, data: Data, path: Path, fmt: str) -> None:
        """Save a Data object to the specified file format."""
        if fmt == "csv":
            df = self._create_dataframe_from_data(data.data)
            df.to_csv(path, index=False)
        elif fmt == "excel":
            try:
                df = self._create_dataframe_from_data(data.data)
                
                if df.empty:
                    msg = "Cannot save empty data to Excel format"
                    raise ValueError(msg)
                if len(df.columns) == 0:
                    msg = "Cannot save data with no columns to Excel format"
                    raise ValueError(msg)
                
                df.to_excel(path, index=False, engine="openpyxl")
            except ImportError:
                msg = "Excel format requires the 'openpyxl' library"
                raise ImportError(msg)
            except Exception as e:
                msg = f"Error saving data to Excel: {str(e)}"
                raise ValueError(msg)
        elif fmt == "json":
            path.write_text(
                orjson.dumps(jsonable_encoder(data.data), option=orjson.OPT_INDENT_2).decode("utf-8"), encoding="utf-8"
            )
        elif fmt == "markdown":
            df = self._create_dataframe_from_data(data.data)
            path.write_text(df.to_markdown(index=False), encoding="utf-8")
        else:
            msg = f"Unsupported Data format: {fmt}"
            raise ValueError(msg)

    def _save_data_list(self, data_list: list, path: Path, fmt: str) -> None:
        """Save a list of Data objects to the specified file format."""
        if fmt == "csv":
            # Convert all Data objects to DataFrames and combine
            dataframes = [self._create_dataframe_from_data(data.data) for data in data_list]
            combined_df = pd.concat(dataframes, ignore_index=True)
            combined_df.to_csv(path, index=False)
        elif fmt == "excel":
            try:
                # Validate Data objects before saving
                dataframes = []
                for i, data in enumerate(data_list):
                    df = self._create_dataframe_from_data(data.data)
                    
                    if df.empty:
                        msg = f"Data object at index {i} is empty and cannot be saved to Excel"
                        raise ValueError(msg)
                    if len(df.columns) == 0:
                        msg = f"Data object at index {i} has no columns and cannot be saved to Excel"
                        raise ValueError(msg)
                    
                    dataframes.append(df)
                
                # Save each Data object to a separate sheet
                with pd.ExcelWriter(path, engine="openpyxl") as writer:
                    for i, df in enumerate(dataframes):
                        sheet_name = f"Sheet{i+1}" if len(dataframes) > 1 else "Sheet1"
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
            except ImportError:
                msg = "Excel format requires the 'openpyxl' library"
                raise ImportError(msg)
            except Exception as e:
                msg = f"Error saving data to Excel: {str(e)}"
                raise ValueError(msg)
        elif fmt == "json":
            # Save as a list of data objects
            all_data = [data.data for data in data_list]
            path.write_text(
                orjson.dumps(jsonable_encoder(all_data), option=orjson.OPT_INDENT_2).decode("utf-8"), encoding="utf-8"
            )
        elif fmt == "markdown":
            # Convert all Data objects to DataFrames and combine
            dataframes = [self._create_dataframe_from_data(data.data) for data in data_list]
            combined_df = pd.concat(dataframes, ignore_index=True)
            path.write_text(combined_df.to_markdown(index=False), encoding="utf-8")
        else:
            msg = f"Unsupported Data list format: {fmt}"
            raise ValueError(msg)

    async def _save_message(self, message: Message, path: Path, fmt: str) -> None:
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

    async def _save_message_list(self, messages: list, path: Path, fmt: str) -> None:
        """Save a list of Message objects to the specified file format."""
        # Extract content from all messages
        all_contents = []
        for message in messages:
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
            all_contents.append(content)

        if fmt == "txt":
            # Save all messages as separate lines
            path.write_text("\n\n".join(all_contents), encoding="utf-8")
        elif fmt == "json":
            # Save as a list of message objects
            message_data = [{"message": content} for content in all_contents]
            path.write_text(json.dumps(message_data, indent=2), encoding="utf-8")
        elif fmt == "markdown":
            # Save as markdown with each message as a section
            markdown_content = ""
            for i, content in enumerate(all_contents):
                markdown_content += f"**Message {i+1}:**\n\n{content}\n\n"
            path.write_text(markdown_content.strip(), encoding="utf-8")
        else:
            msg = f"Unsupported Message format: {fmt}"
            raise ValueError(msg)
