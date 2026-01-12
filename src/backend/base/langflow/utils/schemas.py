import enum

from langchain_core.messages import BaseMessage
from lfx.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI
from pydantic import BaseModel, field_validator, model_validator
from typing_extensions import TypedDict


class File(TypedDict):
    """File schema."""

    path: str
    name: str
    type: str


class ChatOutputResponse(BaseModel):
    """Chat output response schema."""

    message: str | list[str | dict]
    sender: str | None = MESSAGE_SENDER_AI
    sender_name: str | None = MESSAGE_SENDER_NAME_AI
    session_id: str | None = None
    stream_url: str | None = None
    component_id: str | None = None
    files: list[File] = []
    type: str

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, files):
        """Validate files."""
        if not files:
            return files

        for file in files:
            if not isinstance(file, dict):
                msg = "Files must be a list of dictionaries."
                raise ValueError(msg)  # noqa: TRY004

            if not all(key in file for key in ["path", "name", "type"]):
                # If any of the keys are missing, we should extract the
                # values from the file path
                path = file.get("path")
                if not path:
                    msg = "File path is required."
                    raise ValueError(msg)

                name = file.get("name")
                if not name:
                    name = path.split("/")[-1]
                    file["name"] = name
                type_ = file.get("type")
                if not type_:
                    # get the file type from the path
                    extension = path.split(".")[-1]
                    file_types = set(TEXT_FILE_TYPES + IMG_FILE_TYPES)
                    if extension and extension in file_types:
                        type_ = extension
                    else:
                        for file_type in file_types:
                            if file_type in path:
                                type_ = file_type
                                break
                    if not type_:
                        msg = "File type is required."
                        raise ValueError(msg)
                file["type"] = type_

        return files

    @classmethod
    def from_message(
        cls,
        message: BaseMessage,
        sender: str | None = MESSAGE_SENDER_AI,
        sender_name: str | None = MESSAGE_SENDER_NAME_AI,
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

        if self.sender != MESSAGE_SENDER_AI:
            return self

        # We need to make sure we don't duplicate \n
        # in the message
        message = self.message.replace("\n\n", "\n")
        self.message = message.replace("\n", "\n\n")
        return self


class DataOutputResponse(BaseModel):
    """Data output response schema."""

    data: list[dict | None]


class ContainsEnumMeta(enum.EnumMeta):
    def __contains__(cls, item) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True
