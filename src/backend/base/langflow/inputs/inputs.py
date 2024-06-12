from typing import Callable, Optional, Union

from pydantic import Field

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


class PromptInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.PROMPT


# Applying mixins to a specific input type
class StrInput(BaseInputMixin, ListableInputMixin):  # noqa: F821
    field_type: Optional[SerializableFieldTypes] = FieldTypes.TEXT
    multiline: bool = Field(default=False)
    """Defines if the field will allow the user to open a text editor. Default is False."""


class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.PASSWORD
    password: bool = Field(default=True)


class IntInput(BaseInputMixin, ListableInputMixin, RangeMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.INTEGER


class FloatInput(BaseInputMixin, ListableInputMixin, RangeMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.FLOAT


class BoolInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.BOOLEAN


class NestedDictInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.NESTED_DICT


class DictInput(BaseInputMixin, ListableInputMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.DICT


class DropdownInput(BaseInputMixin, DropDownMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.TEXT
    options: Optional[Union[list[str], Callable]] = None
    """List of options for the field. Only used when is_list=True. Default is an empty list."""


class FileInput(BaseInputMixin, ListableInputMixin, FileMixin):
    field_type: Optional[SerializableFieldTypes] = FieldTypes.FILE
