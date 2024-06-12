import json
import uuid
from typing import Any, Optional

from langflow.custom import CustomComponent
from langflow.schema import Record
from langflow.schema.dotdict import dotdict


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
        message = ""
        try:
            body = json.loads(data or "{}")
        except json.JSONDecodeError:
            body = {"payload": data}
            message = f"Invalid JSON payload. Please check the format.\n\n{data}"
        record = Record(data=body)
        if not message:
            message = json.dumps(body, indent=2)
        self.status = message
        return record
