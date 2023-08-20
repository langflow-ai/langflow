from sqlmodel import SQLModel
import orjson
from pydantic import ConfigDict


def orjson_dumps(v, *, default):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default).decode()


class SQLModelSerializable(SQLModel):
    # TODO[pydantic]: The following keys were removed: `json_loads`, `json_dumps`.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    model_config = ConfigDict(
        from_attributes=True, json_loads=orjson.loads, json_dumps=orjson_dumps
    )
