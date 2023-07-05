from abc import ABC, abstractmethod
from typing import Optional

from langflow.template.field.base import TemplateField


class FieldFormatter(ABC):
    @abstractmethod
    def format(self, field: TemplateField, name: Optional[str]) -> None:
        pass
