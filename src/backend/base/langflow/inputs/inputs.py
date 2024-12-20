import warnings
from collections.abc import AsyncIterator, Iterator
from typing import Any, TypeAlias, get_args

from pandas import DataFrame
from pydantic import Field, field_validator

from langflow.inputs.validators import CoalesceBool
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.database.models.message.model import MessageBase
from langflow.template.field.base import Input

from .input_mixin import (
    BaseInputMixin,
    DatabaseLoadMixin,
    DropDownMixin,
    FieldTypes,
    FileMixin,
    InputTraceMixin,
    LinkMixin,
    ListableInputMixin,
    MetadataTraceMixin,
    MultilineMixin,
    RangeMixin,
    SerializableFieldTypes,
    SliderMixin,
    TableMixin,
    ToolModeMixin,
)


class TableInput(BaseInputMixin, MetadataTraceMixin, TableMixin, ListableInputMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.TABLE
    is_list: bool = True

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, _info):
        # Check if value is a list of dicts
        if isinstance(v, DataFrame):
            v = v.to_dict(orient="records")
        if not isinstance(v, list):
            msg = f"TableInput value must be a list of dictionaries or Data. Value '{v}' is not a list."
            raise ValueError(msg)  # noqa: TRY004

        for item in v:
            if not isinstance(item, dict | Data):
                msg = (
                    "TableInput value must be a list of dictionaries or Data. "
                    f"Item '{item}' is not a dictionary or Data."
                )
                raise ValueError(msg)  # noqa: TRY004
        return v


class HandleInput(BaseInputMixin, ListableInputMixin, MetadataTraceMixin):
    """Represents an Input that has a Handle to a specific type (e.g. BaseLanguageModel, BaseRetriever, etc.).

    This class inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        input_types (list[str]): A list of input types.
        field_type (SerializableFieldTypes): The field type of the input.
    """

    input_types: list[str] = Field(default_factory=list)
    field_type: SerializableFieldTypes = FieldTypes.OTHER


class DataInput(HandleInput, InputTraceMixin, ListableInputMixin, ToolModeMixin):
    """Represents an Input that has a Handle that receives a Data object.

    Attributes:
        input_types (list[str]): A list of input types supported by this data input.
    """

    input_types: list[str] = ["Data"]


class DataFrameInput(HandleInput, InputTraceMixin, ListableInputMixin, ToolModeMixin):
    input_types: list[str] = ["DataFrame"]


class PromptInput(BaseInputMixin, ListableInputMixin, InputTraceMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.PROMPT


class CodeInput(BaseInputMixin, ListableInputMixin, InputTraceMixin):
    field_type: SerializableFieldTypes = FieldTypes.CODE


# Applying mixins to a specific input type
class StrInput(BaseInputMixin, ListableInputMixin, DatabaseLoadMixin, MetadataTraceMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.TEXT
    load_from_db: CoalesceBool = False
    """Defines if the field will allow the user to open a text editor. Default is False."""

    @staticmethod
    def _validate_value(v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        if not isinstance(v, str) and v is not None:
            # Keep the warning for now, but we should change it to an error
            if info.data.get("input_types") and v.__class__.__name__ not in info.data.get("input_types"):
                warnings.warn(
                    f"Invalid value type {type(v)} for input {info.data.get('name')}. "
                    f"Expected types: {info.data.get('input_types')}",
                    stacklevel=4,
                )
            else:
                warnings.warn(
                    f"Invalid value type {type(v)} for input {info.data.get('name')}.",
                    stacklevel=4,
                )
        return v

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        is_list = info.data["is_list"]
        return [cls._validate_value(vv, info) for vv in v] if is_list else cls._validate_value(v, info)


class MessageInput(StrInput, InputTraceMixin):
    input_types: list[str] = ["Message"]

    @staticmethod
    def _validate_value(v: Any, _info):
        # If v is a instance of Message, then its fine
        if isinstance(v, dict):
            return Message(**v)
        if isinstance(v, Message):
            return v
        if isinstance(v, str | AsyncIterator | Iterator):
            return Message(text=v)
        if isinstance(v, MessageBase):
            return Message(**v.model_dump())
        msg = f"Invalid value type {type(v)}"
        raise ValueError(msg)


class MessageTextInput(StrInput, MetadataTraceMixin, InputTraceMixin, ToolModeMixin):
    """Represents a text input component for the Langflow system.

    This component is used to handle text inputs in the Langflow system.
    It provides methods for validating and processing text values.

    Attributes:
        input_types (list[str]): A list of input types that this component supports.
            In this case, it supports the "Message" input type.
    """

    input_types: list[str] = ["Message"]

    @staticmethod
    def _validate_value(v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        value: str | AsyncIterator | Iterator | None = None
        if isinstance(v, dict):
            v = Message(**v)
        if isinstance(v, str):
            value = v
        elif isinstance(v, Message):
            value = v.text
        elif isinstance(v, Data):
            if v.text_key in v.data:
                value = v.data[v.text_key]
            else:
                keys = ", ".join(v.data.keys())
                input_name = info.data["name"]
                msg = (
                    f"The input to '{input_name}' must contain the key '{v.text_key}'."
                    f"You can set `text_key` to one of the following keys: {keys} "
                    "or set the value using another Component."
                )
                raise ValueError(msg)
        elif isinstance(v, AsyncIterator | Iterator):
            value = v
        else:
            msg = f"Invalid value type {type(v)}"
            raise ValueError(msg)  # noqa: TRY004
        return value


class MultilineInput(MessageTextInput, MultilineMixin, InputTraceMixin, ToolModeMixin):
    """Represents a multiline input field.

    Attributes:
        field_type (SerializableFieldTypes): The type of the field. Defaults to FieldTypes.TEXT.
        multiline (CoalesceBool): Indicates whether the input field should support multiple lines. Defaults to True.
    """

    field_type: SerializableFieldTypes = FieldTypes.TEXT
    multiline: CoalesceBool = True


class MultilineSecretInput(MessageTextInput, MultilineMixin, InputTraceMixin):
    """Represents a multiline input field.

    Attributes:
        field_type (SerializableFieldTypes): The type of the field. Defaults to FieldTypes.TEXT.
        multiline (CoalesceBool): Indicates whether the input field should support multiple lines. Defaults to True.
    """

    field_type: SerializableFieldTypes = FieldTypes.PASSWORD
    multiline: CoalesceBool = True
    password: CoalesceBool = Field(default=True)


class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):
    """Represents a field with password field type.

    This class inherits from `BaseInputMixin` and `DatabaseLoadMixin`.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to `FieldTypes.PASSWORD`.
        password (CoalesceBool): A boolean indicating whether the input is a password. Defaults to `True`.
        input_types (list[str]): A list of input types associated with this input. Defaults to an empty list.
    """

    field_type: SerializableFieldTypes = FieldTypes.PASSWORD
    password: CoalesceBool = Field(default=True)
    input_types: list[str] = ["Message"]
    load_from_db: CoalesceBool = True

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        value: str | AsyncIterator | Iterator | None = None
        if isinstance(v, str):
            value = v
        elif isinstance(v, Message):
            value = v.text
        elif isinstance(v, Data):
            if v.text_key in v.data:
                value = v.data[v.text_key]
            else:
                keys = ", ".join(v.data.keys())
                input_name = info.data["name"]
                msg = (
                    f"The input to '{input_name}' must contain the key '{v.text_key}'."
                    f"You can set `text_key` to one of the following keys: {keys} "
                    "or set the value using another Component."
                )
                raise ValueError(msg)
        elif isinstance(v, AsyncIterator | Iterator):
            value = v
        elif v is None:
            value = None
        else:
            msg = f"Invalid value type `{type(v)}` for input `{info.data['name']}`"
            raise ValueError(msg)
        return value


class IntInput(BaseInputMixin, ListableInputMixin, RangeMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents an integer field.

    This class represents an integer input and provides functionality for handling integer values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin`, and `RangeMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.INTEGER.
    """

    field_type: SerializableFieldTypes = FieldTypes.INTEGER

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        if v and not isinstance(v, int | float):
            msg = f"Invalid value type {type(v)} for input {info.data.get('name')}."
            raise ValueError(msg)
        if isinstance(v, float):
            v = int(v)
        return v


class FloatInput(BaseInputMixin, ListableInputMixin, RangeMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a float field.

    This class represents a float input and provides functionality for handling float values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin`, and `RangeMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.FLOAT.
    """

    field_type: SerializableFieldTypes = FieldTypes.FLOAT

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        if v and not isinstance(v, int | float):
            msg = f"Invalid value type {type(v)} for input {info.data.get('name')}."
            raise ValueError(msg)
        if isinstance(v, int):
            v = float(v)
        return v


class BoolInput(BaseInputMixin, ListableInputMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a boolean field.

    This class represents a boolean input and provides functionality for handling boolean values.
    It inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.BOOLEAN.
        value (CoalesceBool): The value of the boolean input.
    """

    field_type: SerializableFieldTypes = FieldTypes.BOOLEAN
    value: CoalesceBool = False


class NestedDictInput(BaseInputMixin, ListableInputMixin, MetadataTraceMixin, InputTraceMixin, ToolModeMixin):
    """Represents a nested dictionary field.

    This class represents a nested dictionary input and provides functionality for handling dictionary values.
    It inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.NESTED_DICT.
        value (Optional[dict]): The value of the input. Defaults to an empty dictionary.
    """

    field_type: SerializableFieldTypes = FieldTypes.NESTED_DICT
    value: dict | Data | None = {}


class DictInput(BaseInputMixin, ListableInputMixin, InputTraceMixin, ToolModeMixin):
    """Represents a dictionary field.

    This class represents a dictionary input and provides functionality for handling dictionary values.
    It inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.DICT.
        value (Optional[dict]): The value of the dictionary input. Defaults to an empty dictionary.
    """

    field_type: SerializableFieldTypes = FieldTypes.DICT
    value: dict | None = {}


class DropdownInput(BaseInputMixin, DropDownMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a dropdown input field.

    This class represents a dropdown input field and provides functionality for handling dropdown values.
    It inherits from the `BaseInputMixin` and `DropDownMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.TEXT.
        options (Optional[Union[list[str], Callable]]): List of options for the field.
            Default is None.
    """

    field_type: SerializableFieldTypes = FieldTypes.TEXT
    options: list[str] = Field(default_factory=list)
    combobox: CoalesceBool = False


class MultiselectInput(BaseInputMixin, ListableInputMixin, DropDownMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a multiselect input field.

    This class represents a multiselect input field and provides functionality for handling multiselect values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin` and `DropDownMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.TEXT.
        options (Optional[Union[list[str], Callable]]): List of options for the field. Only used when is_list=True.
            Default is None.
    """

    field_type: SerializableFieldTypes = FieldTypes.TEXT
    options: list[str] = Field(default_factory=list)
    is_list: bool = Field(default=True, serialization_alias="list")
    combobox: CoalesceBool = False

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, _info):
        # Check if value is a list of dicts
        if not isinstance(v, list):
            msg = f"MultiselectInput value must be a list. Value: '{v}'"
            raise ValueError(msg)  # noqa: TRY004
        for item in v:
            if not isinstance(item, str):
                msg = f"MultiselectInput value must be a list of strings. Item: '{item}' is not a string"
                raise ValueError(msg)  # noqa: TRY004
        return v


class FileInput(BaseInputMixin, ListableInputMixin, FileMixin, MetadataTraceMixin):
    """Represents a file field.

    This class represents a file input and provides functionality for handling file values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin`, and `FileMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.FILE.
    """

    field_type: SerializableFieldTypes = FieldTypes.FILE


class LinkInput(BaseInputMixin, LinkMixin):
    field_type: SerializableFieldTypes = FieldTypes.LINK


class SliderInput(BaseInputMixin, RangeMixin, SliderMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.SLIDER


DEFAULT_PROMPT_INTUT_TYPES = ["Message", "Text"]


class DefaultPromptField(Input):
    name: str
    display_name: str | None = None
    field_type: str = "str"
    advanced: bool = False
    multiline: bool = True
    input_types: list[str] = DEFAULT_PROMPT_INTUT_TYPES
    value: Any = ""  # Set the value to empty string


InputTypes: TypeAlias = (
    Input
    | DefaultPromptField
    | BoolInput
    | DataInput
    | DictInput
    | DropdownInput
    | MultiselectInput
    | FileInput
    | FloatInput
    | HandleInput
    | IntInput
    | MultilineInput
    | MultilineSecretInput
    | NestedDictInput
    | PromptInput
    | CodeInput
    | SecretStrInput
    | StrInput
    | MessageTextInput
    | MessageInput
    | TableInput
    | LinkInput
    | SliderInput
    | DataFrameInput
)

InputTypesMap: dict[str, type[InputTypes]] = {t.__name__: t for t in get_args(InputTypes)}


def instantiate_input(input_type: str, data: dict) -> InputTypes:
    input_type_class = InputTypesMap.get(input_type)
    if "type" in data:
        # Replate with field_type
        data["field_type"] = data.pop("type")
    if input_type_class:
        return input_type_class(**data)
    msg = f"Invalid input type: {input_type}"
    raise ValueError(msg)
