from pydantic import BaseModel


class StreamData(BaseModel):
    event: str
    data: dict

    def __str__(self) -> str:
        from langflow.services.database.models.base import orjson_dumps

        return f"event: {self.event}\ndata: {orjson_dumps(self.data, indent_2=False)}\n\n"
