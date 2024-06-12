from pydantic import SecretStr

from langflow.field_typing.constants import NestedDict
from langflow.template.field.base import Input


class StrInput(Input):
    field_type: str | type | None = str


class SecretStrInput(Input):
    field_type: str | type | None = SecretStr
    password = True


class IntInput(Input):
    field_type: str | type | None = int


class FloatInput(Input):
    field_type: str | type | None = float


class BoolInput(Input):
    field_type: str | type | None = bool


class NestedDictInput(Input):
    field_type: str | type | None = NestedDict


class DictInput(Input):
    field_type: str | type | None = dict


class ListInput(Input):
    is_list = True


class DropdownInput(Input):
    field_type: str | type | None = str
    options = []


class FileInput(Input):
    field_type: str | type | None = str
