from typing import Annotated

from pydantic import PlainValidator


def validate_boolean(value: bool) -> bool:  # noqa: FBT001
    valid_trues = ["True", "true", "1", "yes"]
    valid_falses = ["False", "false", "0", "no"]
    if value in valid_trues:
        return True
    if value in valid_falses:
        return False
    if isinstance(value, bool):
        return value
    msg = "Value must be a boolean"
    raise ValueError(msg)


CoalesceBool = Annotated[bool, PlainValidator(validate_boolean)]
