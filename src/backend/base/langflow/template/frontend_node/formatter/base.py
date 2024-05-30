from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from langflow.template.field.base import InputField


class FieldFormatter(BaseModel, ABC):
    @abstractmethod
    def format(self, field: InputField, name: Optional[str]) -> None:
        pass
