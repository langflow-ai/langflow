import uuid

from langflow import CustomComponent


class UUIDGeneratorComponent(CustomComponent):
    documentation: str = "http://docs.langflow.org/components/custom"
    display_name = "Unique ID Generator"
    description = "Generates a unique ID."

    def generate(self, *args, **kwargs):
        return str(uuid.uuid4().hex)

    def build_config(self):
        return {"unique_id": {"display_name": "Value", "value": self.generate}}

    def build(self, unique_id: str) -> str:
        return unique_id
