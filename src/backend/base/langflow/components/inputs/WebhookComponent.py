import json
import uuid
from typing import Any, Optional

from langflow.custom import CustomComponent
from langflow.schema.dotdict import dotdict
from langflow.schema.schema import Record


class WebhookComponent(CustomComponent):
    display_name = "Webhook Input"
    description = "Defines a webhook input for the flow."

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "webhook_id":
            build_config["webhook_id"]["value"] = uuid.uuid4().hex
        return build_config

    def build_config(self):
        return {
            "data": {
                "display_name": "Data",
                "info": "Use this field to quickly test the webhook component by providing a JSON payload.",
                "multiline": True,
            }
        }

    def build(self, data: Optional[str] = "") -> Record:
        try:
            body = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON data provided.")
        record = Record(data=body)
        self.status = record
        return record
