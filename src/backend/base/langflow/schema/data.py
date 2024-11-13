import copy
import json
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from loguru import logger
from pydantic import BaseModel, model_serializer, model_validator

from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER
from langflow.utils.image import create_data_url


class Data(BaseModel):
    """Represents a record with text and optional data.

    Attributes:
        data (dict, optional): Additional data associated with the record.
    """

    text_key: str = "text"
    data: dict = {}
    default_value: str | None = ""

    @model_validator(mode="before")
    @classmethod
    def validate_data(cls, values):
        if not isinstance(values, dict):
            msg = "Data must be a dictionary"
            raise ValueError(msg)  # noqa: TRY004
        if not values.get("data"):
            values["data"] = {}
        # Any other keyword should be added to the data dictionary
        for key in values:
            if key not in values["data"] and key not in {"text_key", "data", "default_value"}:
                values["data"][key] = values[key]
        return values

    @model_serializer(mode="plain", when_used="json")
    def serialize_model(self):
        return {k: v.to_json() if hasattr(v, "to_json") else v for k, v in self.data.items()}

    def get_text(self):
        """Retrieves the text value from the data dictionary.

        If the text key is present in the data dictionary, the corresponding value is returned.
        Otherwise, the default value is returned.

        Returns:
            The text value from the data dictionary or the default value.
        """
        return self.data.get(self.text_key, self.default_value)

    @classmethod
    def from_document(cls, document: Document) -> "Data":
        """Converts a Document to a Data.

        Args:
            document (Document): The Document to convert.

        Returns:
            Data: The converted Data.
        """
        data = document.metadata
        data["text"] = document.page_content
        return cls(data=data, text_key="text")

    @classmethod
    def from_lc_message(cls, message: BaseMessage) -> "Data":
        """Converts a BaseMessage to a Data.

        Args:
            message (BaseMessage): The BaseMessage to convert.

        Returns:
            Data: The converted Data.
        """
        data: dict = {"text": message.content}
        data["metadata"] = cast(dict, message.to_json())
        return cls(data=data, text_key="text")

    def __add__(self, other: "Data") -> "Data":
        """Combines the data of two data by attempting to add values for overlapping keys.

        Combines the data of two data by attempting to add values for overlapping keys
        for all types that support the addition operation. Falls back to the value from 'other'
        record when addition is not supported.
        """
        combined_data = self.data.copy()
        for key, value in other.data.items():
            # If the key exists in both data and both values support the addition operation
            if key in combined_data:
                try:
                    combined_data[key] += value
                except TypeError:
                    # Fallback: Use the value from 'other' record if addition is not supported
                    combined_data[key] = value
            else:
                # If the key is not in the first record, simply add it
                combined_data[key] = value

        return Data(data=combined_data)

    def to_lc_document(self) -> Document:
        """Converts the Data to a Document.

        Returns:
            Document: The converted Document.
        """
        data_copy = self.data.copy()
        text = data_copy.pop(self.text_key, self.default_value)
        return Document(page_content=text, metadata=data_copy)

    def to_lc_message(
        self,
    ) -> BaseMessage:
        """Converts the Data to a BaseMessage.

        Returns:
            BaseMessage: The converted BaseMessage.
        """
        # The idea of this function is to be a helper to convert a Data to a BaseMessage
        # It will use the "sender" key to determine if the message is Human or AI
        # If the key is not present, it will default to AI
        # But first we check if all required keys are present in the data dictionary
        # they are: "text", "sender"
        if not all(key in self.data for key in ["text", "sender"]):
            msg = f"Missing required keys ('text', 'sender') in Data: {self.data}"
            raise ValueError(msg)
        sender = self.data.get("sender", MESSAGE_SENDER_AI)
        text = self.data.get("text", "")
        files = self.data.get("files", [])
        if sender == MESSAGE_SENDER_USER:
            if files:
                contents = [{"type": "text", "text": text}]
                for file_path in files:
                    image_url = create_data_url(file_path)
                    contents.append({"type": "image_url", "image_url": {"url": image_url}})
                human_message = HumanMessage(content=contents)
            else:
                human_message = HumanMessage(
                    content=[{"type": "text", "text": text}],
                )

            return human_message

        return AIMessage(content=text)

    def __getattr__(self, key):
        """Allows attribute-like access to the data dictionary."""
        try:
            if key.startswith("__"):
                return self.__getattribute__(key)
            if key in {"data", "text_key"} or key.startswith("_"):
                return super().__getattr__(key)
            return self.data[key]
        except KeyError as e:
            # Fallback to default behavior to raise AttributeError for undefined attributes
            msg = f"'{type(self).__name__}' object has no attribute '{key}'"
            raise AttributeError(msg) from e

    def __setattr__(self, key, value) -> None:
        """Set attribute-like values in the data dictionary.

        Allows attribute-like setting of values in the data dictionary.
        while still allowing direct assignment to class attributes.
        """
        if key in {"data", "text_key"} or key.startswith("_"):
            super().__setattr__(key, value)
        elif key in self.model_fields:
            self.data[key] = value
            super().__setattr__(key, value)
        else:
            self.data[key] = value

    def __delattr__(self, key) -> None:
        """Allows attribute-like deletion from the data dictionary."""
        if key in {"data", "text_key"} or key.startswith("_"):
            super().__delattr__(key)
        else:
            del self.data[key]

    def __deepcopy__(self, memo):
        """Custom deepcopy implementation to handle copying of the Data object."""
        # Create a new Data object with a deep copy of the data dictionary
        return Data(data=copy.deepcopy(self.data, memo), text_key=self.text_key, default_value=self.default_value)

    # check which attributes the Data has by checking the keys in the data dictionary
    def __dir__(self):
        return super().__dir__() + list(self.data.keys())

    def __str__(self) -> str:
        # return a JSON string representation of the Data atributes
        try:
            data = {k: v.to_json() if hasattr(v, "to_json") else v for k, v in self.data.items()}
            return serialize_data(data)  # use the custom serializer
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Error converting Data to JSON")
            return str(self.data)

    def __contains__(self, key) -> bool:
        return key in self.data

    def __eq__(self, other):
        return isinstance(other, Data) and self.data == other.data


def custom_serializer(obj):
    if isinstance(obj, datetime):
        return obj.astimezone().isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    # Add more custom serialization rules as needed
    msg = f"Type {type(obj)} not serializable"
    raise TypeError(msg)


def serialize_data(data):
    return json.dumps(data, indent=4, default=custom_serializer)
