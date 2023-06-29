from abc import ABC, abstractmethod

from langflow.template.field.base import TemplateField


class FieldFormatter(ABC):
    @abstractmethod
    def format(self, field: TemplateField):
        pass
