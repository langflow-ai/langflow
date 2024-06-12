from typing import Annotated

from pydantic import PlainValidator

StrictBoolean = Annotated[bool, PlainValidator(lambda v: v is True or v is False)]
