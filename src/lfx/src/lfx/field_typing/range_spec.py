"""Range specification for field types copied from langflow for lfx package."""

from typing import Literal

from pydantic import BaseModel, field_validator


class RangeSpec(BaseModel):
    step_type: Literal["int", "float"] = "float"
    min: float = -1.0
    max: float = 1.0
    step: float = 0.1

    @field_validator("max")
    @classmethod
    def max_must_be_greater_than_min(cls, v, values):
        if "min" in values.data and v <= values.data["min"]:
            msg = "Max must be greater than min"
            raise ValueError(msg)
        return v

    @field_validator("step")
    @classmethod
    def step_must_be_positive(cls, v, values):
        if v <= 0:
            msg = "Step must be positive"
            raise ValueError(msg)
        if values.data["step_type"] == "int" and isinstance(v, float) and not v.is_integer():
            msg = "When step_type is int, step must be an integer"
            raise ValueError(msg)
        return v

    @classmethod
    def set_step_type(cls, step_type: Literal["int", "float"], range_spec: "RangeSpec") -> "RangeSpec":
        return cls(min=range_spec.min, max=range_spec.max, step=range_spec.step, step_type=step_type)
