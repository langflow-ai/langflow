from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

from langflow.template.field.base import Input


class FieldFormatter(BaseModel, ABC):
    @abstractmethod
    def format(self, field: Input, name: Optional[str]) -> None:
        pass
