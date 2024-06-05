import enum
from typing import Dict, List, Optional, Union

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, field_validator, model_validator
from typing_extensions import TypedDict

from langflow.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES


class File(TypedDict):
    """File schema."""

    path: str
    name: str
    type: str


class ChatOutputResponse(BaseModel):
    """Chat output response schema."""

    message: Union[str, List[Union[str, Dict]]]
    sender: Optional[str] = "Machine"
    sender_name: Optional[str] = "AI"
    session_id: Optional[str] = None
    stream_url: Optional[str] = None
    component_id: Optional[str] = None
    files: List[File] = []
    type: str

    @field_validator("files", mode="before")
    def validate_files(cls, files):
        """Validate files."""
        if not files:
            return files

        for file in files:
            if not isinstance(file, dict):
                raise ValueError("Files must be a list of dictionaries.")

            if not all(key in file for key in ["path", "name", "type"]):
                # If any of the keys are missing, we should extract the
                # values from the file path
                path = file.get("path")
                if not path:
                    raise ValueError("File path is required.")

                name = file.get("name")
                if not name:
                    name = path.split("/")[-1]
                    file["name"] = name
                _type = file.get("type")
                if not _type:
                    # get the file type from the path
                    extension = path.split(".")[-1]
                    file_types = set(TEXT_FILE_TYPES + IMG_FILE_TYPES)
                    if extension and extension in file_types:
                        _type = extension
                    else:
                        for file_type in file_types:
                            if file_type in path:
                                _type = file_type
                                break
                    if not _type:
                        raise ValueError("File type is required.")
                file["type"] = _type

        return files

    @classmethod
    def from_message(
        cls,
        message: BaseMessage,
        sender: Optional[str] = "Machine",
        sender_name: Optional[str] = "AI",
    ):
        """Build chat output response from message."""
        content = message.content
        return cls(message=content, sender=sender, sender_name=sender_name)

    @model_validator(mode="after")
    def validate_message(self):
        """Validate message."""
        # The idea here is ensure the \n in message
        # is compliant with markdown if sender is machine
        # so, for example:
        # \n\n -> \n\n
        # \n -> \n\n

        if self.sender != "Machine":
            return self

        # We need to make sure we don't duplicate \n
        # in the message
        message = self.message.replace("\n\n", "\n")
        self.message = message.replace("\n", "\n\n")
        return self


class RecordOutputResponse(BaseModel):
    """Record output response schema."""

    records: List[Optional[Dict]]


class ContainsEnumMeta(enum.EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True
