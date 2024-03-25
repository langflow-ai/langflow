from abc import ABC, abstractmethod
from typing import Optional

from langflow_base.template.field.base import TemplateField
from pydantic import BaseModel


class FieldFormatter(BaseModel, ABC):
    @abstractmethod
    def format(self, field: TemplateField, name: Optional[str]) -> None:
        pass
