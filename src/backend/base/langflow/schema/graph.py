from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, RootModel

from langflow.schema.schema import InputType


class InputValue(BaseModel):
    components: Optional[List[str]] = []
    input_value: Optional[str] = None
    type: Optional[InputType] = Field(
        "any",
        description="Defines on which components the input value should be applied. 'any' applies to all input components.",
    )


class Tweaks(RootModel):
    root: dict[str, Union[str, dict[str, Any]]] = Field(
        description="A dictionary of tweaks to adjust the flow's execution. Allows customizing flow behavior dynamically. All tweaks are overridden by the input values.",
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "parameter_name": "value",
                    "Component Name": {"parameter_name": "value"},
                    "component_id": {"parameter_name": "value"},
                }
            ]
        }
    }

    # This should behave like a dict
    def __getitem__(self, key):
        return self.root[key]

    def __setitem__(self, key, value):
        self.root[key] = value

    def __delitem__(self, key):
        del self.root[key]

    def items(self):
        return self.root.items()
