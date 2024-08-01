from typing import Any, List, Optional

from pydantic import Field, field_validator
from typing_extensions import TypedDict

from langflow.helpers.base_model import BaseModel


class ResultPair(BaseModel):
    result: Any
    extra: Any


class Payload(BaseModel):
    result_pairs: List[ResultPair] = []

    def __iter__(self):
        return iter(self.result_pairs)

    def add_result_pair(self, result: Any, extra: Optional[Any] = None) -> None:
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
    field_name: str = Field(..., alias="fieldName", description="Field name for the target handle.")
    id: str = Field(..., description="Unique identifier for the target handle.")
    input_types: List[str] = Field(
        default_factory=list, alias="inputTypes", description="List of input types for the target handle."
    )
    type: str = Field(..., description="Type of the target handle.")


class SourceHandle(BaseModel):
    base_classes: list[str] = Field(
        default_factory=list, alias="baseClasses", description="List of base classes for the source handle."
    )
    data_type: str = Field(..., alias="dataType", description="Data type for the source handle.")
    id: str = Field(..., description="Unique identifier for the source handle.")
    name: Optional[str] = Field(None, description="Name of the source handle.")
    output_types: List[str] = Field(default_factory=list, description="List of output types for the source handle.")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v, _info):
        if _info.data["data_type"] == "GroupNode":
            # 'OpenAIModel-u4iGV_text_output'
            splits = v.split("_", 1)
            if len(splits) != 2:
                raise ValueError(f"Invalid source handle name {v}")
            v = splits[1]
        return v


class SourceHandleDict(TypedDict, total=False):
    baseClasses: list[str]
    dataType: str
    id: str
    name: Optional[str]
    output_types: List[str]


class TargetHandleDict(TypedDict):
    fieldName: str
    id: str
    inputTypes: Optional[List[str]]
    type: str


class EdgeDataDetails(TypedDict):
    sourceHandle: SourceHandleDict
    targetHandle: TargetHandleDict


class EdgeData(TypedDict, total=False):
    source: str
    target: str
    data: EdgeDataDetails
