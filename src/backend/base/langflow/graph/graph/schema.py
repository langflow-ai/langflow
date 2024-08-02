from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from langflow.graph.schema import ResultData
    from langflow.graph.vertex.base import Vertex


class VertexBuildResult(NamedTuple):
    result_dict: "ResultData"
    params: str
    valid: bool
    artifacts: dict
    vertex: "Vertex"
