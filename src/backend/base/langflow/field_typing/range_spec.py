from typing import Literal

from pydantic import BaseModel, field_validator


class RangeSpec(BaseModel):
    step_type: Literal["int", "float"] = "float"
    min: float = -1.0
    max: float = 1.0
    step: float = 0.1

    @field_validator("max")
    @classmethod
    def max_must_be_greater_than_min(cls, v, values, **kwargs):
        if "min" in values.data and v <= values.data["min"]:
            raise ValueError("Max must be greater than min")
        return v

    @field_validator("step")
    @classmethod
    def step_must_be_positive(cls, v, values, **kwargs):
        if v <= 0:
            raise ValueError("Step must be positive")
        if values.data["step_type"] == "int" and isinstance(v, float) and not v.is_integer():
            raise ValueError("When step_type is int, step must be an integer")
        return v

    @classmethod
    def set_step_type(cls, step_type: Literal["int", "float"], range_spec: "RangeSpec") -> "RangeSpec":
        return cls(min=range_spec.min, max=range_spec.max, step=range_spec.step, step_type=step_type)
