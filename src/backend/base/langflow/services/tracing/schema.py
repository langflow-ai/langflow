from langflow.schema.log import LoggableType
from langflow.schema.secrets_sanitizer import DataRedactionModel


class Log(DataRedactionModel):
    name: str
    message: LoggableType
    type: str
