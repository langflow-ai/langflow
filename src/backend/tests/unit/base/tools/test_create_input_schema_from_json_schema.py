from datetime import date
from enum import Enum

from langflow.base.mcp.util import create_input_schema_from_json_schema
from pydantic import BaseModel, Field


def test_create_input_schema_from_json_schema():
    # Define extremely obfuscated BaseModel class aka arrange
    class EnumA(Enum):
        vala1 = "valA1"
        vala2 = "valA2"
        vala3 = "valA3"

    class EnumB(Enum):
        valb1 = "valB1"
        valb2 = "valB2"
        valb3 = "valB3"

    class StrangeSubThing(BaseModel):
        list_field: list[EnumB] = Field(
            description="Cool description of the list field",
            required=True,
        )
        tuple_field: tuple[str, int, EnumA, tuple[int, date]] | None = Field(
            description="Cool description of the tuple field",
            required=False,
            default=[],
        )
        date_field: date | None = Field(
            description="Cool description of the date field",
            required=False,
            default=date.today(),  # noqa: DTZ011
        )
        enuma_field: EnumA | None = Field(
            description="Cool description of the enum field",
            required=False,
            default=EnumA.vala1,
        )

    class StrangeSubThingTheSecond(BaseModel):
        strange_sub_thing: StrangeSubThing | None = Field(
            description="Not cool description of the strange sub thing",
            required=False,
            default=None,
        )
        cool_field: str = Field(
            description="Not cool description of the cool field",
            required=True,
        )

    class InputSchema(BaseModel):
        the_first_sub_thing: StrangeSubThing | None = Field(
            description="Kinda okay description of the first sub thing",
            required=False,
            default=None,
        )
        the_second_sub_thing: StrangeSubThingTheSecond = Field(
            description="Kinda okay description of the second sub thing",
            required=True,
        )
        the_enum: EnumB | None = Field(
            description="Kinda okay description of the enum field",
            required=False,
            default=EnumB.valb3,
        )

    # act
    recreated_json_schema = create_input_schema_from_json_schema(
        InputSchema.model_json_schema(),
    ).model_json_schema()

    # assert
    assert InputSchema.model_json_schema() == recreated_json_schema
