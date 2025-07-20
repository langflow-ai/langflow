from typing import Any

from pydantic import ConfigDict, Field, field_validator
from typing_extensions import TypedDict

from langflow.helpers.base_model import BaseModel


class SourceHandleDict(TypedDict, total=False):
    baseClasses: list[str]
    dataType: str
    id: str
    name: str | None
    output_types: list[str]


class TargetHandleDict(TypedDict):
    fieldName: str
    id: str
    inputTypes: list[str] | None
    type: str


class LoopTargetHandleDict(TypedDict):
    dataType: str
    id: str
    name: str
    output_types: list[str]


class EdgeDataDetails(TypedDict):
    sourceHandle: SourceHandleDict
    targetHandle: TargetHandleDict | LoopTargetHandleDict


class EdgeData(TypedDict, total=False):
    source: str
    target: str
    data: EdgeDataDetails


class ResultPair(BaseModel):
    result: Any
    extra: Any


class Payload(BaseModel):
    result_pairs: list[ResultPair] = []

    def __iter__(self):
        return iter(self.result_pairs)

    def add_result_pair(self, result: Any, extra: Any | None = None) -> None:
        self.result_pairs.append(ResultPair(result=result, extra=extra))

    def get_last_result_pair(self) -> ResultPair:
        return self.result_pairs[-1]

    # format all but the last result pair
    # into a string
    def format(self, sep: str = "\n") -> str:
        # Result: the result
        # Extra: the extra if it exists don't show if it doesn't
        return sep.join(
            [
                f"Result: {result_pair.result}\nExtra: {result_pair.extra}"
                if result_pair.extra is not None
                else f"Result: {result_pair.result}"
                for result_pair in self.result_pairs[:-1]
            ]
        )


class TargetHandle(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    field_name: str = Field(..., alias="fieldName", description="Field name for the target handle.")
    id: str = Field(..., description="Unique identifier for the target handle.")
    input_types: list[str] = Field(
        default_factory=list, alias="inputTypes", description="List of input types for the target handle."
    )
    type: str = Field(None, description="Type of the target handle.")

    @classmethod
    def from_loop_target_handle(cls, target_handle: LoopTargetHandleDict) -> "TargetHandle":
        # The target handle is a loop edge
        # The target handle is a dict with the following keys:
        # - name: str
        # - id: str
        # - inputTypes: list[str]
        # - type: str
        # It is built from an Output, which is why it has a different structure
        return cls(
            field_name=target_handle.get("name"),
            id=target_handle.get("id"),
            input_types=target_handle.get("output_types"),
        )


class SourceHandle(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    base_classes: list[str] = Field(
        default_factory=list, alias="baseClasses", description="List of base classes for the source handle."
    )
    data_type: str = Field(..., alias="dataType", description="Data type for the source handle.")
    id: str = Field(..., description="Unique identifier for the source handle.")
    name: str | None = Field(None, description="Name of the source handle.")
    output_types: list[str] = Field(default_factory=list, description="List of output types for the source handle.")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v, info):
        if info.data["data_type"] == "GroupNode":
            # 'OpenAIModel-u4iGV_text_output'
            splits = v.split("_", 1)
            if len(splits) != 2:  # noqa: PLR2004
                msg = f"Invalid source handle name {v}"
                raise ValueError(msg)
            v = splits[1]
        return v
