from typing import Any, Callable, Optional, Union

from pydantic import Field, field_validator

from langflow.inputs.validators import CoalesceBool
from langflow.schema.data import Data
from langflow.schema.message import Message

from .input_mixin import (
    BaseInputMixin,
    DatabaseLoadMixin,
    DropDownMixin,
    FieldTypes,
    FileMixin,
    ListableInputMixin,
    RangeMixin,
    SerializableFieldTypes,
)


class HandleInput(BaseInputMixin, ListableInputMixin):
    input_types: list[str] = Field(default_factory=list)
    field_type: Optional[SerializableFieldTypes] = FieldTypes.OTHER


class DataInput(HandleInput):
    input_types: list[str] = ["Data"]


class PromptInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.PROMPT


# Applying mixins to a specific input type
class StrInput(BaseInputMixin, ListableInputMixin, DatabaseLoadMixin):  # noqa: F821
    field_type: Optional[SerializableFieldTypes] = FieldTypes.TEXT
    load_from_db: CoalesceBool = False
    input_types: list[str] = ["Text"]
    """Defines if the field will allow the user to open a text editor. Default is False."""


class MessageInput(StrInput):
    input_types: list[str] = ["Message"]

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, _info):
        # If v is a instance of Message, then its fine
        if isinstance(v, Message):
            return v
        if isinstance(v, str):
            return Message(text=v)
        raise ValueError(f"Invalid value type {type(v)}")


class TextInput(StrInput):
    input_types: list[str] = ["Message"]

    @staticmethod
    def _validate_value(v: Any, _info):
        value = None
        if isinstance(v, str):
            value = v
        elif isinstance(v, Message):
            value = v.text
        elif isinstance(v, Data):
            if v.text_key in v.data:
                value = v.data[v.text_key]
            else:
                keys = ", ".join(v.data.keys())
                input_name = _info.data["name"]
                raise ValueError(
                    f"The input to '{input_name}' must contain the key '{v.text_key}'."
                    f"You can set `text_key` to one of the following keys: {keys} or set the value using another Component."
                )
        else:
            raise ValueError(f"Invalid value type {type(v)}")
        return value

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, _info):
        is_list = _info.data["is_list"]
        value = None
        if is_list:
            value = [cls._validate_value(vv, _info) for vv in v]
        else:
            value = cls._validate_value(v, _info)
        return value


class MultilineInput(BaseInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.TEXT
    multiline: CoalesceBool = True


class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.PASSWORD
    password: CoalesceBool = Field(default=True)
    input_types: list[str] = ["Text"]


class IntInput(BaseInputMixin, ListableInputMixin, RangeMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.INTEGER


class FloatInput(BaseInputMixin, ListableInputMixin, RangeMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.FLOAT


class BoolInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.BOOLEAN
    value: CoalesceBool = False


class NestedDictInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.NESTED_DICT
    value: Optional[dict] = {}


class DictInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.DICT
    value: Optional[dict] = {}


class DropdownInput(BaseInputMixin, DropDownMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.TEXT
    options: Optional[Union[list[str], Callable]] = None
    """List of options for the field. Only used when is_list=True. Default is an empty list."""


class FileInput(BaseInputMixin, ListableInputMixin, FileMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.FILE


InputTypes = Union[
    BoolInput,
    DataInput,
    DictInput,
    DropdownInput,
    FileInput,
    FloatInput,
    HandleInput,
    IntInput,
    MultilineInput,
    NestedDictInput,
    PromptInput,
    SecretStrInput,
    StrInput,
    TextInput,
    MessageInput,
]
