from pydantic import field_validator, BaseModel
from typing import Any


class Decision(BaseModel):
    """
    Represents a decision made in the Graph.

    Attributes:
        path (str): The path to take as a result of the decision.
        result (dict): The result of the decision.
    """

    path: str
    result: Any

    @field_validator("path")
    def validate_path(cls, value: str) -> str:
        """
        Validates the path.

        Args:
            value (str): The path to validate.

        Returns:
            str: The validated path.
        """
        if isinstance(value, str):
            return value
        return str(value)
