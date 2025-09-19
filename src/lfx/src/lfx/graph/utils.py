from __future__ import annotations

from collections.abc import Generator
from enum import Enum
from typing import TYPE_CHECKING, Any

from lfx.interface.utils import extract_input_variables_from_prompt
from lfx.schema.data import Data
from lfx.schema.message import Message

if TYPE_CHECKING:
    from lfx.graph.vertex.base import Vertex


class UnbuiltObject:
    pass


class UnbuiltResult:
    pass


class ArtifactType(str, Enum):
    TEXT = "text"
    RECORD = "record"
    OBJECT = "object"
    ARRAY = "array"
    STREAM = "stream"
    UNKNOWN = "unknown"
    MESSAGE = "message"


def validate_prompt(prompt: str):
    """Validate prompt."""
    if extract_input_variables_from_prompt(prompt):
        return prompt

    return fix_prompt(prompt)


def fix_prompt(prompt: str):
    """Fix prompt."""
    return prompt + " {input}"


def flatten_list(list_of_lists: list[list | Any]) -> list:
    """Flatten list of lists."""
    new_list = []
    for item in list_of_lists:
        if isinstance(item, list):
            new_list.extend(item)
        else:
            new_list.append(item)
    return new_list


def get_artifact_type(value, build_result) -> str:
    result = ArtifactType.UNKNOWN
    match value:
        case Data():
            result = ArtifactType.RECORD

        case str():
            result = ArtifactType.TEXT

        case dict():
            result = ArtifactType.OBJECT

        case list():
            result = ArtifactType.ARRAY

        case Message():
            result = ArtifactType.MESSAGE

    if result == ArtifactType.UNKNOWN and (
        isinstance(build_result, Generator) or (isinstance(value, Message) and isinstance(value.text, Generator))
    ):
        result = ArtifactType.STREAM

    return result.value


def post_process_raw(raw, artifact_type: str):
    if artifact_type == ArtifactType.STREAM.value:
        raw = ""

    return raw


def rewrite_file_path(file_path: str):
    file_path = file_path.replace("\\", "/")

    if ":" in file_path:
        file_path = file_path.split(":", 1)[-1]

    file_path_split = [part for part in file_path.split("/") if part]

    if len(file_path_split) > 1:
        consistent_file_path = f"{file_path_split[-2]}/{file_path_split[-1]}"
    else:
        consistent_file_path = "/".join(file_path_split)

    return [consistent_file_path]


def has_output_vertex(vertices: dict[Vertex, int]):
    return any(vertex.is_output for vertex in vertices)


def has_chat_output(vertices: dict[Vertex, int]):
    from lfx.graph.schema import InterfaceComponentTypes

    return any(InterfaceComponentTypes.ChatOutput in vertex.id for vertex in vertices)
