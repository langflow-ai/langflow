from typing import Callable, Optional, Union

from pydantic import Field

from langflow.template.field.input_mixin import (
    BaseInputMixin,
    DatabaseLoadMixin,
    DropDownMixin,
    FieldTypes,
    FileMixin,
    ListableInputMixin,
    RangeMixin,
)


class PromptInput(BaseInputMixin, ListableInputMixin):
    field_type = FieldTypes.PROMPT


# Applying mixins to a specific input type
class StrInput(BaseInputMixin, ListableInputMixin):  # noqa: F821
    field_type = FieldTypes.TEXT
    multiline: bool = Field(default=False)
    """Defines if the field will allow the user to open a text editor. Default is False."""


class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):
    field_type = FieldTypes.PASSWORD
    password: bool = Field(default=True)


class IntInput(BaseInputMixin, ListableInputMixin, RangeMixin):
    field_type = FieldTypes.INTEGER


class FloatInput(BaseInputMixin, ListableInputMixin, RangeMixin):
    field_type = FieldTypes.FLOAT


class BoolInput(BaseInputMixin, ListableInputMixin):
    field_type = FieldTypes.BOOLEAN


class NestedDictInput(BaseInputMixin, ListableInputMixin):
    field_type = FieldTypes.NESTED_DICT


class DictInput(BaseInputMixin, ListableInputMixin):
    field_type = FieldTypes.DICT


class DropdownInput(BaseInputMixin, DropDownMixin):
    field_type = FieldTypes.TEXT
    options: Optional[Union[list[str], Callable]] = None
    """List of options for the field. Only used when is_list=True. Default is an empty list."""


class FileInput(BaseInputMixin, ListableInputMixin, FileMixin):
    field_type = FieldTypes.FILE
