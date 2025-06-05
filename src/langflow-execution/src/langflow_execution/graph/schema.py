from enum import Enum, EnumMeta
from typing import Any, Literal

# from langflow.schema.schema import OutputValue, StreamURL
# from langflow.serialization import serialize
from pydantic import BaseModel, Field, field_serializer, model_serializer, model_validator, field_validator

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from langflow_execution.components.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES
from langflow_execution.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI


# TODO: find where this should live
InputType = Literal["chat", "text", "any"]
OutputType = Literal["chat", "text", "any", "debug"]


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


class ContainsEnumMeta(EnumMeta):
    def __contains__(cls, item) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True


class ResultData(BaseModel):
    results: Any | None = Field(default_factory=dict)
    artifacts: Any | None = Field(default_factory=dict)
    outputs: dict | None = Field(default_factory=dict)
    logs: dict | None = Field(default_factory=dict)
    messages: list[ChatOutputResponse] | None = Field(default_factory=list)
    timedelta: float | None = None
    duration: str | None = None
    component_display_name: str | None = None
    component_id: str | None = None
    used_frozen_result: bool | None = False

    @field_serializer("results")
    def serialize_results(self, value):
        if isinstance(value, dict):
            return {key: serialize(val) for key, val in value.items()}
        return serialize(value)

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, values):
        if not values.get("outputs") and values.get("artifacts"):
            # Build the log from the artifacts

            for key in values["artifacts"]:
                message = values["artifacts"][key]

                # ! Temporary fix
                if message is None:
                    continue

                if "stream_url" in message and "type" in message:
                    stream_url = StreamURL(location=message["stream_url"])
                    values["outputs"].update({key: OutputValue(message=stream_url, type=message["type"])})
                elif "type" in message:
                    values["outputs"].update({key: OutputValue(message=message, type=message["type"])})
        return values


class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
    ChatInput = "ChatInput"
    ChatOutput = "ChatOutput"
    TextInput = "TextInput"
    TextOutput = "TextOutput"
    DataOutput = "DataOutput"
    WebhookInput = "Webhook"


CHAT_COMPONENTS = [InterfaceComponentTypes.ChatInput, InterfaceComponentTypes.ChatOutput]
RECORDS_COMPONENTS = [InterfaceComponentTypes.DataOutput]
INPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatInput,
    InterfaceComponentTypes.WebhookInput,
    InterfaceComponentTypes.TextInput,
]
OUTPUT_COMPONENTS = [
    InterfaceComponentTypes.ChatOutput,
    InterfaceComponentTypes.DataOutput,
    InterfaceComponentTypes.TextOutput,
]


class RunOutputs(BaseModel):
    inputs: dict = Field(default_factory=dict)
    outputs: list[ResultData | None] = Field(default_factory=list)


class RunResponse(BaseModel):
    """Run response schema."""

    outputs: list[RunOutputs] | None = []
    session_id: str | None = None

    @model_serializer(mode="plain")
    def serialize(self):
        # Serialize all the outputs if they are base models
        serialized = {"session_id": self.session_id, "outputs": []}
        if self.outputs:
            serialized_outputs = []
            for output in self.outputs:
                if isinstance(output, BaseModel) and not isinstance(output, RunOutputs):
                    serialized_outputs.append(output.model_dump(exclude_none=True))
                else:
                    serialized_outputs.append(output)
            serialized["outputs"] = serialized_outputs
        return serialized


class InputValue(BaseModel):
    components: list[str] | None = []
    input_value: str | None = None
    type: InputType | None = Field(
        "any",
        description="Defines on which components the input value should be applied. "
        "'any' applies to all input components.",
    )
