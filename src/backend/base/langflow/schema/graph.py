from typing import Any

from pydantic import BaseModel, Field, RootModel

from langflow.schema.schema import InputType


class InputValue(BaseModel):
    components: list[str] | None = []
    input_value: str | None = None
    type: InputType | None = Field(
        "any",
        description="Defines on which components the input value should be applied. "
        "'any' applies to all input components.",
    )


class Tweaks(RootModel):
    root: dict[str, str | dict[str, Any] | list[Any]] = Field(
        description="A dictionary of tweaks to adjust the flow's execution. "
        "Allows customizing flow behavior dynamically. "
        "All tweaks are overridden by the input values.",
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "parameter_name": "value",
                    "Component Name": {"parameter_name": "value"},
                    "component_id": {"parameter_name": "value"},
                    "upload_files": [
            			{
            				"file_id": "252991ae3dc74347a96a3494f943e374",
            				"file_name": "knowledges.txt"
            			}
            		]
                }
            ]
        }
    }

    # This should behave like a dict
    def __getitem__(self, key):
        return self.root[key]

    def __setitem__(self, key, value) -> None:
        self.root[key] = value

    def __delitem__(self, key) -> None:
        del self.root[key]

    def items(self):
        return self.root.items()
