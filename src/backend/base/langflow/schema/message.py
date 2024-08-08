import asyncio
from datetime import datetime, timezone
from typing import Annotated, Any, AsyncIterator, Iterator, List, Optional
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from langchain_core.load import load
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompt_values import ImagePromptValue
from langchain_core.prompts import BaseChatPromptTemplate, ChatPromptTemplate, PromptTemplate
from langchain_core.prompts.image import ImagePromptTemplate
from loguru import logger
from pydantic import BeforeValidator, ConfigDict, Field, field_serializer, field_validator

from langflow.base.prompts.utils import dict_values_to_string
from langflow.schema.data import Data
from langflow.schema.image import Image, get_file_paths, is_image_file
from langflow.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_AI,
    MESSAGE_SENDER_NAME_USER,
    MESSAGE_SENDER_USER,
)


def _timestamp_to_str(timestamp: datetime | str) -> str:
    if isinstance(timestamp, str):
        # Just check if the string is a valid datetime
        try:
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            return timestamp
        except ValueError:
            raise ValueError(f"Invalid timestamp: {timestamp}")
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


class Message(Data):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # Helper class to deal with image data
    text_key: str = "text"
    text: Optional[str | AsyncIterator | Iterator] = Field(default="")
    sender: Optional[str] = None
    sender_name: Optional[str] = None
    files: Optional[list[str | Image]] = Field(default=[])
    session_id: Optional[str] = Field(default="")
    timestamp: Annotated[str, BeforeValidator(_timestamp_to_str)] = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    flow_id: Optional[str | UUID] = None

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if isinstance(value, UUID):
            value = str(value)
        return value

    @field_serializer("flow_id")
    def serialize_flow_id(value):
        if isinstance(value, str):
            return UUID(value)
        return value

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, value):
        if not value:
            value = []
        elif not isinstance(value, list):
            value = [value]
        return value

    def model_post_init(self, __context: Any) -> None:
        new_files: List[Any] = []
        for file in self.files or []:
            if is_image_file(file):
                new_files.append(Image(path=file))
            else:
                new_files.append(file)
        self.files = new_files
        if "timestamp" not in self.data:
            self.data["timestamp"] = self.timestamp

    def set_flow_id(self, flow_id: str):
        self.flow_id = flow_id

    def to_lc_message(
        self,
    ) -> BaseMessage:
        """
        Converts the Data to a BaseMessage.

        Returns:
            BaseMessage: The converted BaseMessage.
        """
        # The idea of this function is to be a helper to convert a Data to a BaseMessage
        # It will use the "sender" key to determine if the message is Human or AI
        # If the key is not present, it will default to AI
        # But first we check if all required keys are present in the data dictionary
        # they are: "text", "sender"
        if self.text is None or not self.sender:
            logger.warning("Missing required keys ('text', 'sender') in Message, defaulting to HumanMessage.")
        if not isinstance(self.text, str):
            text = ""
        else:
            text = self.text

        if self.sender == MESSAGE_SENDER_USER or not self.sender:
            if self.files:
                contents = [{"type": "text", "text": text}]
                contents.extend(self.sync_get_file_content_dicts())
                human_message = HumanMessage(content=contents)  # type: ignore
            else:
                human_message = HumanMessage(content=text)
            return human_message

        return AIMessage(content=text)  # type: ignore

    @classmethod
    def from_lc_message(cls, lc_message: BaseMessage) -> "Message":
        if lc_message.type == "human":
            sender = MESSAGE_SENDER_USER
            sender_name = MESSAGE_SENDER_NAME_USER
        elif lc_message.type == "ai":
            sender = MESSAGE_SENDER_AI
            sender_name = MESSAGE_SENDER_NAME_AI
        elif lc_message.type == "system":
            sender = "System"
            sender_name = "System"
        else:
            sender = lc_message.type
            sender_name = lc_message.type

        return cls(text=lc_message.content, sender=sender, sender_name=sender_name)

    @classmethod
    def from_data(cls, data: "Data") -> "Message":
        """
        Converts a BaseMessage to a Data.

        Args:
            record (BaseMessage): The BaseMessage to convert.

        Returns:
            Data: The converted Data.
        """

        return cls(
            text=data.text,
            sender=data.sender,
            sender_name=data.sender_name,
            files=data.files,
            session_id=data.session_id,
            timestamp=data.timestamp,
            flow_id=data.flow_id,
        )

    @field_serializer("text", mode="plain")
    def serialize_text(self, value):
        if isinstance(value, AsyncIterator):
            return ""
        elif isinstance(value, Iterator):
            return ""
        return value

    def sync_get_file_content_dicts(self):
        coro = self.get_file_content_dicts()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    # Keep this async method for backwards compatibility
    async def get_file_content_dicts(self):
        content_dicts = []
        files = await get_file_paths(self.files)

        for file in files:
            if isinstance(file, Image):
                content_dicts.append(file.to_content_dict())
            else:
                image_template = ImagePromptTemplate()
                image_prompt_value: ImagePromptValue = image_template.invoke(input={"path": file})  # type: ignore
                content_dicts.append({"type": "image_url", "image_url": image_prompt_value.image_url})
        return content_dicts

    def load_lc_prompt(self):
        if "prompt" not in self:
            raise ValueError("Prompt is required.")
        # self.prompt was passed through jsonable_encoder
        # so inner messages are not BaseMessage
        # we need to convert them to BaseMessage
        messages = []
        for message in self.prompt.get("kwargs", {}).get("messages", []):
            match message:
                case HumanMessage():
                    messages.append(message)
                case _ if message.get("type") == "human":
                    messages.append(HumanMessage(content=message.get("content")))
                case _ if message.get("type") == "system":
                    messages.append(SystemMessage(content=message.get("content")))
                case _ if message.get("type") == "ai":
                    messages.append(AIMessage(content=message.get("content")))

        self.prompt["kwargs"]["messages"] = messages
        loaded_prompt = load(self.prompt)
        return loaded_prompt

    @classmethod
    def from_lc_prompt(
        cls,
        prompt: BaseChatPromptTemplate,
    ):
        prompt_json = prompt.to_json()
        return cls(prompt=prompt_json)

    def format_text(self):
        prompt_template = PromptTemplate.from_template(self.template)
        variables_with_str_values = dict_values_to_string(self.variables)
        formatted_prompt = prompt_template.format(**variables_with_str_values)
        self.text = formatted_prompt
        return formatted_prompt

    @classmethod
    async def from_template_and_variables(cls, template: str, **variables):
        instance = cls(template=template, variables=variables)
        text = instance.format_text()
        # Get all Message instances from the kwargs
        message = HumanMessage(content=text)
        contents = []
        for value in variables.values():
            if isinstance(value, cls) and value.files:
                content_dicts = await value.get_file_content_dicts()
                contents.extend(content_dicts)
        if contents:
            message = HumanMessage(content=[{"type": "text", "text": text}] + contents)

        prompt_template = ChatPromptTemplate(messages=[message])  # type: ignore
        instance.prompt = jsonable_encoder(prompt_template.to_json())
        instance.messages = instance.prompt.get("kwargs", {}).get("messages", [])
        return instance

    @classmethod
    def sync_from_template_and_variables(cls, template: str, **variables):
        # Run the async version in a sync way
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(cls.from_template_and_variables(template, **variables))
        else:
            return loop.run_until_complete(cls.from_template_and_variables(template, **variables))
