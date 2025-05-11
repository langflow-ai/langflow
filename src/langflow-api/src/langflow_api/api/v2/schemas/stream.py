from pydantic import BaseModel

class StreamData(BaseModel):
    event: str
    data: dict 