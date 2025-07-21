from enum import Enum


class ArtifactType(str, Enum):
    TEXT = "text"
    DATA = "data"
    OBJECT = "object"
    ARRAY = "array"
    STREAM = "stream"
    UNKNOWN = "unknown"
    MESSAGE = "message"
    RECORD = "record"
